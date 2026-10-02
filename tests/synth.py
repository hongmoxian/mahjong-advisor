"""合成麻将画面与牌面模板, 用于无摄像头的端到端测试和演示。"""

from typing import List, Tuple

import cv2
import numpy as np

from mjengine.tiles import parse_hand, tile_short

CARD_W, CARD_H = 72, 100
GAP = 6
BG = (35, 35, 35)
CARD_BG = (245, 245, 245)
CARD_BORDER = (150, 150, 150)
TEXT = (25, 25, 25)

HAND_ROI = (40, 540, 1200, 130)
DISCARD_ROI = (40, 60, 560, 350)


def make_card(code: str) -> np.ndarray:
    """渲染一张牌面(白底 + 牌代码), 与真实模板同尺寸同风格。"""
    img = np.full((CARD_H, CARD_W, 3), CARD_BG, np.uint8)
    cv2.rectangle(img, (0, 0), (CARD_W - 1, CARD_H - 1), CARD_BORDER, 2)
    cv2.putText(img, code, (10, CARD_H // 2 + 12), cv2.FONT_HERSHEY_SIMPLEX,
                1.1, TEXT, 2, cv2.LINE_AA)
    return img


def codes_of(hand: str) -> List[str]:
    if not hand.strip():
        return []
    counts = parse_hand(hand)
    return [tile_short(t) for t in range(34) for _ in range(counts[t])]


def make_frame(hand: str, discards: str = "") -> Tuple[np.ndarray, Tuple[int, int, int, int], Tuple[int, int, int, int]]:
    """合成一张 1280x720 的'手机截图': 上方牌河网格, 下方手牌一行。"""
    frame = np.full((720, 1280, 3), BG, np.uint8)
    hx, hy, _, _ = HAND_ROI
    for i, code in enumerate(codes_of(hand)):
        x = hx + 10 + i * (CARD_W + GAP)
        frame[hy + 15:hy + 15 + CARD_H, x:x + CARD_W] = make_card(code)
    dx, dy, _, _ = DISCARD_ROI
    per_row = 6
    for i, code in enumerate(codes_of(discards)):
        row, col = divmod(i, per_row)
        x = dx + 10 + col * (CARD_W + GAP)
        y = dy + 10 + row * (CARD_H + GAP)
        frame[y:y + CARD_H, x:x + CARD_W] = make_card(code)
    return frame, HAND_ROI, DISCARD_ROI
