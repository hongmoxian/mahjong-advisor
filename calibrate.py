"""交互式标定工具: 设定手牌/牌河区域, 并从实际游戏画面截取每种牌的模板。

用法:
    python calibrate.py                    # 用 config.json 里的摄像头
    python calibrate.py --source cam:1     # 指定摄像头
    python calibrate.py --source shot.png  # 用截图标定(推荐先拍一张游戏截图)

快捷键:
    c  冻结/继续画面   (标定前先按 c 冻结, 手机画面不动才好框选)
    h  框选手牌区域    (拖拽后回车确认)
    d  框选牌河区域    (能完整看到各家打出的牌)
    t  截取牌面模板    (框住一张牌, 回车后在终端输入牌代码, 如 5m / 1p / z1)
    l  列出已有模板
    s  保存配置
    q  退出
"""

import argparse
import os
import re

import cv2

from mjengine.tiles import tid_from_short, tile_name
from vision.capture import FrameSource
from vision.config import DEFAULT_CONFIG_PATH, load_config, save_config, templates_dir
from vision.overlay import draw_panel

LABEL_RE = re.compile(r"^([1-9])([mps])$|^([1-7])z$")

HELP_LINES = [
    ("=== 麻将助手标定工具 ===", (0, 255, 255)),
    ("c:冻结/继续  h:手牌区域  d:牌河区域", (255, 255, 255)),
    ("t:截取模板  l:模板列表  s:保存  q:退出", (255, 255, 255)),
    ("标定前先按 c 冻结画面!", (0, 200, 255)),
]


def main():
    ap = argparse.ArgumentParser(description="麻将助手标定工具")
    ap.add_argument("--source", default=None, help='cam:0 / cam:1 / 图片路径 / 视频路径')
    ap.add_argument("--config", default=DEFAULT_CONFIG_PATH)
    args = ap.parse_args()

    cfg = load_config(args.config)
    source = args.source or (f"cam:{cfg['source'].get('index', 0)}" if cfg["source"]["type"] == "camera" else cfg["source"].get("path"))
    src = FrameSource(source)
    tdir = templates_dir(cfg, args.config)

    frozen = None
    win = "calibrate"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    while True:
        if frozen is None:
            frame = src.read()
            if frame is None:
                print("画面读取结束")
                break
        else:
            frame = frozen

        lines = list(HELP_LINES)
        lines.append((f"手牌区域: {cfg.get('hand_roi')}", (0, 255, 0)))
        lines.append((f"牌河区域: {cfg.get('discard_roi')}", (0, 255, 0)))
        lines.append((f"模板: {len(cfg.get('templates', {}))} 个 -> {tdir}", (0, 255, 0)))
        if frozen is not None:
            lines.append(("[已冻结] 可以框选了", (0, 165, 255)))
        show = draw_panel(frame.copy(), lines)
        for key, roi in (("HAND", cfg.get("hand_roi")), ("RIVER", cfg.get("discard_roi"))):
            if roi:
                x, y, w, h = [int(v) for v in roi]
                cv2.rectangle(show, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(show, key, (x + 4, y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow(win, show)

        k = cv2.waitKey(30) & 0xFF
        if k == ord("q"):
            break
        elif k == ord("c"):
            frozen = None if frozen is not None else src.read()
        elif k in (ord("h"), ord("d")) and frozen is not None:
            r = cv2.selectROI(win, show, showCrosshair=True)
            if r != (0, 0, 0, 0):
                key = "hand_roi" if k == ord("h") else "discard_roi"
                cfg[key] = list(r)
                save_config(cfg, args.config)
                print(f"已保存 {key} = {list(r)}")
        elif k == ord("t") and frozen is not None:
            r = cv2.selectROI(win, show, showCrosshair=True)
            if r == (0, 0, 0, 0):
                continue
            x, y, w, h = [int(v) for v in r]
            crop = frozen[y:y + h, x:x + w]
            if crop.size == 0:
                continue
            label = input("这张牌的代码 (如 5m/1p/9s/z1, q 取消): ").strip()
            if not label or label == "q":
                continue
            try:
                name = tile_name(tid_from_short(label))
            except ValueError as e:
                print(f"无效代码: {e}")
                continue
            path = os.path.join(tdir, f"{label}.png")
            cv2.imwrite(path, crop)
            cfg.setdefault("templates", {})[label] = path
            save_config(cfg, args.config)
            print(f"模板 {label}({name}) 已保存: {path}")
        elif k == ord("l"):
            for code, path in cfg.get("templates", {}).items():
                print(f"  {code}: {path} {'OK' if os.path.exists(path) else '缺失!'}")
            if not cfg.get("templates"):
                print("  (空)")
        elif k in (ord("h"), ord("d")):
            print("请先按 c 冻结画面再框选!")
        elif k == ord("s"):
            save_config(cfg, args.config)
            print(f"配置已保存到 {args.config}")

    src.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
