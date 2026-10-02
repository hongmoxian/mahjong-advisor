"""麻将出牌助手主程序。

摄像头对着手机上的麻将游戏画面, 识别你的手牌和场上牌河,
提示下一步怎么打。

用法:
    python main.py                        # 摄像头模式(需要先标定)
    python main.py --source cam:1
    python main.py --source shot.png      # 分析一张截图
    python main.py --manual               # 终端手动输牌(不需要标定, 立即可用)
    python main.py --manual --hand 1112345678999m
    python main.py --source shot.png --analyze-only   # 只输出文字, 不开窗口

窗口快捷键:
    空格  立即分析当前画面
    a     连续自动分析 开/关
    d     防守模式 开/关 (有人快胡时用, 优先打牌河现过的牌)
    e     终端手动输入手牌(识别不准时兜底)
    x     清除手动输入, 回到摄像头识别
    q     退出
"""

import argparse
import sys

import cv2

from mjengine import Advisor, parse_hand, hand_to_display, hand_to_string
from mjengine.tiles import tile_name
from vision.capture import FrameSource
from vision.config import DEFAULT_CONFIG_PATH, load_config, missing_settings
from vision.detector import TileDetector, load_templates
from vision.overlay import draw_panel, draw_roi, draw_tile_boxes


def fmt_waits(options):
    return "、".join(options["waits_name"]) if options.get("waits_name") else "无"


def build_advice_lines(result, game):
    """把建议结果转为面板文本行 (text, BGR color)。"""
    lines = []
    if result.get("type") == "win":
        lines.append(("★ 可以胡牌! 直接点胡/自摸!", (0, 255, 255)))
        return lines
    if result.get("type") == "invalid":
        lines.append((f"!! {result['message']}", (0, 165, 255)))
        return lines

    if result.get("type") == "discard":
        que = result.get("que_suit")
        if que is not None:
            lines.append((f"缺一门: 还在打缺 [{result['que_name']}] (只能从这门出)", (0, 200, 255)))
        if result.get("defense"):
            lines.append(("[防守模式] 优先打别人现过的牌", (255, 200, 0)))
        opts = result["options"]
        if not opts:
            lines.append(("没有可选出牌", (0, 165, 255)))
            return lines
        best = opts[0]
        lines.append((f"★ 建议打: {tile_name(best['discard'])}", (0, 255, 255)))
        lines.append((f"   打后向听 {max(best['shanten_after'], 0)}, 进张 {best['ukeire_total']} 张: {fmt_waits(best)}",
                      (255, 255, 255)))
        for o in opts[1:3]:
            lines.append((f"备选: 打 {tile_name(o['discard'])} (向听 {max(o['shanten_after'], 0)}, "
                          f"进张 {o['ukeire_total']}, 现过 {o['safety']})", (180, 180, 180)))
    elif result.get("type") == "wait":
        s = result["shanten"]
        state = "听牌!" if result["tenpai"] else f"向听数 {s}"
        lines.append((f"等待摸牌 ({state}), 有效进张 {result['ukeire_total']} 张", (0, 255, 255)))
        if result["tenpai"]:
            waits = "、".join(tile_name(r["tile"]) for r in result["ukeire"])
            lines.append((f"   听: {waits}", (255, 255, 255)))
        else:
            tops = "、".join(tile_name(r["tile"]) for r in result["ukeire"][:6])
            lines.append((f"   好牌: {tops}", (255, 255, 255)))
    return lines


def analyze_hand(advisor, counts, visible, defense, auto_que):
    n = sum(counts)
    if n == 14:
        return advisor.advise_discard(counts, visible, defense=defense, auto_que=auto_que)
    if n == 13:
        return advisor.advise_wait(counts, visible)
    return {"type": "invalid", "count": n, "message": f"手牌张数 {n} 不对, 需要 13 或 14 张"}


def print_advice(counts, visible, advisor, defense, auto_que):
    n = sum(counts)
    print(f"\n手牌 ({n}张): {hand_to_display(counts)}")
    if visible is not None and sum(visible):
        print("牌河已现牌计入进张统计")
    result = analyze_hand(advisor, list(counts), visible, defense, auto_que)
    for text, _ in build_advice_lines(result, advisor.game):
        print("  " + text)
    return result


def manual_mode(args):
    advisor = Advisor(game=args.game or "sichuan")
    defense = args.defense
    auto_que = not args.no_que
    if args.hand:
        counts = parse_hand(args.hand)
        print_advice(parse_hand(args.hand), None, advisor, defense, auto_que)
        return

    print("手动模式: 输入手牌字符串 (如 1112345678999m / 123m456p78s99z), 13或14张, q 退出")
    while True:
        try:
            text = input("手牌> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text in ("q", "quit", "exit", ""):
            break
        if text == "d":
            defense = not defense
            print(f"防守模式: {'开' if defense else '关'}")
            continue
        try:
            counts = parse_hand(text)
        except ValueError as e:
            print(f"  输入有误: {e}")
            continue
        try:
            print_advice(counts, None, advisor, defense, auto_que)
        except Exception as e:
            print(f"  计算出错: {e}")


class App:
    def __init__(self, args):
        self.args = args
        self.cfg = load_config(args.config)
        game = args.game or self.cfg.get("game", "sichuan")
        self.advisor = Advisor(game=game)
        self.auto_que = not args.no_que
        self.defense = args.defense
        self.auto = False
        self.frozen = None
        self.last_result = None
        self.last_counts = None
        self.manual_counts = None
        self.detector = None
        templates = load_templates(self.cfg)
        if templates:
            self.detector = TileDetector(templates, self.cfg)
        self.not_ready = missing_settings(self.cfg) if self.detector is None else (
            missing_settings(self.cfg) if (self.cfg.get("hand_roi") is None or self.cfg.get("discard_roi") is None) else None)

    def analyze_frame(self, frame):
        if self.manual_counts is not None:
            counts = list(self.manual_counts)
            visible = None
        elif self.detector is None or self.cfg.get("hand_roi") is None:
            return
        else:
            dets, codes = self.detector.detect_hand(frame, self.cfg["hand_roi"])
            visible = None
            if self.cfg.get("discard_roi") is not None:
                visible, _ = self.detector.detect_discards(frame, self.cfg["discard_roi"])
            if "?" in codes:
                self.last_result = {"type": "invalid", "count": codes.count("?"),
                                    "message": f"有 {codes.count('?')} 张牌认不出, 按 e 手动输入或补模板"}
                self.last_dets = dets
                return
            counts = [0] * 34
            for d in dets:
                counts[d.tid] += 1
            self.last_counts = counts
            self.last_dets = dets
        self.last_counts = counts
        self.last_result = analyze_hand(self.advisor, counts, visible, self.defense, self.auto_que)

    def render(self, frame):
        show = frame.copy()
        if self.cfg.get("hand_roi"):
            draw_roi(show, self.cfg["hand_roi"], (0, 255, 0), "HAND")
        if self.cfg.get("discard_roi"):
            draw_roi(show, self.cfg["discard_roi"], (255, 200, 0), "RIVER")
        if getattr(self, "last_dets", None) is not None and self.manual_counts is None:
            draw_tile_boxes(show, self.last_dets)

        lines = []
        n = sum(self.last_counts) if self.last_counts else 0
        src_desc = "手动输入" if self.manual_counts is not None else "摄像头识别"
        lines.append((f"手牌({n}张/{src_desc}): {hand_to_display(self.last_counts) if self.last_counts else '-'}",
                      (255, 255, 255)))
        lines += build_advice_lines(self.last_result, self.advisor.game) if self.last_result else []
        mode = "防守" if self.defense else "进攻"
        lines.append((f"[{mode}] 空格:分析  a:连拍{('开' if self.auto else '关')}  d:防守  e:手动输牌  x:清除  q:退出",
                      (160, 160, 160)))
        if self.not_ready and self.manual_counts is None:
            lines.append((f"未就绪: {self.not_ready}, 先运行 python calibrate.py", (0, 165, 255)))
        return draw_panel(show, lines)

    def run(self):
        src = FrameSource(self.args.source or (
            f"cam:{self.cfg['source'].get('index', 0)}" if self.cfg["source"]["type"] == "camera" else "cam:0"))
        win = "mahjong-advisor"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        while True:
            frame = self.frozen if self.frozen is not None else src.read()
            if frame is None:
                print("画面读取结束")
                break
            if self.auto or (self.args.analyze_only and self.last_result is None):
                self.analyze_frame(frame)
            show = self.render(frame)
            cv2.imshow(win, show)
            k = cv2.waitKey(30) & 0xFF
            if k == ord("q"):
                break
            elif k == ord(" "):
                self.analyze_frame(frame)
            elif k == ord("a"):
                self.auto = not self.auto
            elif k == ord("d"):
                self.defense = not self.defense
                if self.last_counts:
                    self.analyze_frame(frame)
            elif k == ord("e"):
                cv2.destroyAllWindows()
                text = input("输入手牌 (如 123m456p78s99z, 13或14张, 回车确认): ").strip()
                try:
                    self.manual_counts = parse_hand(text)
                    self.analyze_frame(frame)
                except ValueError as e:
                    print(f"输入有误: {e}")
                cv2.namedWindow(win, cv2.WINDOW_NORMAL)
            elif k == ord("x"):
                self.manual_counts = None
                self.last_result = None
            elif k == ord("f"):
                self.frozen = None if self.frozen is not None else src.read()
        src.release()
        cv2.destroyAllWindows()


def resolve_source(args, cfg):
    """优先命令行 --source, 其次配置文件。"""
    if args.source:
        return args.source
    s = cfg.get("source", {})
    if s.get("type") == "camera":
        return f"cam:{s.get('index', 0)}"
    return s.get("path") or "cam:0"


def main():
    ap = argparse.ArgumentParser(description="麻将出牌助手")
    ap.add_argument("--source", default=None, help="cam:0 / 图片路径 / 视频路径")
    ap.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    ap.add_argument("--game", default=None, choices=["sichuan", "full"], help="覆盖配置里的规则")
    ap.add_argument("--manual", action="store_true", help="终端手动输牌模式(无需标定)")
    ap.add_argument("--hand", default=None, help="配合 --manual 直接分析这手牌")
    ap.add_argument("--analyze-only", dest="analyze_only", action="store_true",
                    help="分析一帧后输出文字即退出(不开窗口)")
    ap.add_argument("--defense", action="store_true", help="启动时开启防守模式")
    ap.add_argument("--no-que", action="store_true", help="关闭自动缺一门策略")
    args = ap.parse_args()

    if args.manual:
        manual_mode(args)
        return

    app = App(args)
    if args.analyze_only:
        if not args.source and app.cfg.get("source", {}).get("type") != "image":
            print("--analyze-only 需要 --source 指向图片/视频, 或用 --manual")
            sys.exit(1)
        frame = FrameSource(resolve_source(args, app.cfg)).read()
        if frame is None:
            print("无法读取画面")
            sys.exit(1)
        app.analyze_frame(frame)
        counts = app.last_counts
        if counts is None:
            print("识别失败:", app.last_result.get("message") if app.last_result else "未知原因")
            sys.exit(2)
        print(f"识别到手牌: {hand_to_string(counts)}")
        visible = None
        if app.cfg.get("discard_roi") and app.detector:
            visible, _ = app.detector.detect_discards(frame, app.cfg["discard_roi"])
        print_advice(counts, visible, app.advisor, app.defense, app.auto_que)
        return

    app.run()


if __name__ == "__main__":
    main()
