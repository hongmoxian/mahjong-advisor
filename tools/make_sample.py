"""生成演示素材: 合成'手机截图' + 全套模板 + 演示配置。

    python tools/make_sample.py --out demo

生成后可以不开摄像头直接体验:
    python main.py --source demo/sample.png --config demo/config.json --analyze-only
    python main.py --source demo/sample.png --config demo/config.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402

from tests.synth import DISCARD_ROI, HAND_ROI, make_card, make_frame  # noqa: E402

DEMO_HAND = "123m456m789m12p999s"
DEMO_DISCARDS = "3p9m1s5s1p9p3m6s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="demo")
    args = ap.parse_args()

    out = os.path.abspath(args.out)
    tdir = os.path.join(out, "templates")
    os.makedirs(tdir, exist_ok=True)

    all_codes = [f"{n}{s}" for s in "mps" for n in "123456789"]
    for code in all_codes:
        cv2.imwrite(os.path.join(tdir, f"{code}.png"), make_card(code))

    frame, _, _ = make_frame(DEMO_HAND, discards=DEMO_DISCARDS)
    cv2.imwrite(os.path.join(out, "sample.png"), frame)

    # 配置里写相对项目根目录的路径, 方便跨机器/跨系统使用(在项目根目录运行)
    project_root = os.path.dirname(out)
    rel = lambda p: os.path.relpath(p, project_root)
    cfg = {
        "game": "sichuan",
        "source": {"type": "image", "path": rel(os.path.join(out, "sample.png"))},
        "hand_roi": list(HAND_ROI),
        "discard_roi": list(DISCARD_ROI),
        "threshold": 0.6,
        "templates": {c: rel(os.path.join(tdir, f"{c}.png")) for c in all_codes},
    }
    with open(os.path.join(out, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    print(f"演示素材已生成到 {out}/")
    print(f"试一试: python main.py --source {out}/sample.png --config {out}/config.json --analyze-only")


if __name__ == "__main__":
    main()
