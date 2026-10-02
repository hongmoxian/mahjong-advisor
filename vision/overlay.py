"""画面叠加: ROI 框、牌标签(ASCII)与中文信息面板(PIL 渲染)。"""

from typing import List, Tuple

import cv2
import numpy as np

_FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    # Linux
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]

_font_cache = {}


def _get_font(size: int):
    if size in _font_cache:
        return _font_cache[size]
    font = None
    try:
        from PIL import ImageFont
        for path in _FONT_CANDIDATES:
            try:
                font = ImageFont.truetype(path, size)
                break
            except Exception:
                continue
    except ImportError:
        pass
    _font_cache[size] = font
    return font


def draw_roi(img: np.ndarray, roi: List[int], color: Tuple[int, int, int], label: str):
    x, y, w, h = [int(v) for v in roi]
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
    cv2.putText(img, label, (x + 4, y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def draw_tile_boxes(img: np.ndarray, detections, color=(0, 255, 128)):
    from mjengine.tiles import tile_short
    for d in detections:
        x, y, w, h = d.box
        c = color if d.tid is not None else (0, 0, 255)
        cv2.rectangle(img, (x, y), (x + w, y + h), c, 2)
        code = "?" if d.tid is None else tile_short(d.tid)
        cv2.putText(img, code, (x + 2, y + h - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1)


def draw_panel(img: np.ndarray, lines: List[Tuple[str, Tuple[int, int, int]]],
               origin: Tuple[int, int] = (12, 14), font_size: int = 22,
               line_gap: int = 8, bg_alpha: float = 0.55) -> np.ndarray:
    """在画面上绘制中文多行文本面板; 若无 CJK 字体则用 ASCII 退化绘制。"""
    font = _get_font(font_size)
    if font is None:
        y = origin[1] + font_size
        for text, color in lines:
            ascii_text = text.encode("ascii", "ignore").decode()
            cv2.putText(img, ascii_text, (origin[0], y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, color, 1, cv2.LINE_AA)
            y += font_size + line_gap
        return img

    from PIL import Image, ImageDraw
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil, "RGBA")

    text_sizes = [draw.textbbox((0, 0), t, font=font) for t, _ in lines]
    panel_w = max((bb[2] for bb in text_sizes), default=0) + origin[0] * 2
    panel_h = origin[1] + sum(font_size + line_gap for _ in lines) + origin[1]
    overlay = Image.new("RGBA", pil.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle([0, 0, panel_w, panel_h], radius=10, fill=(0, 0, 0, int(bg_alpha * 255)))
    pil = Image.alpha_composite(pil.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(pil)

    x, y = origin[0], origin[1]
    for (text, color), _ in zip(lines, text_sizes):
        rgb = (color[2], color[1], color[0])  # BGR -> RGB
        draw.text((x, y), text, font=font, fill=rgb)
        y += font_size + line_gap
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
