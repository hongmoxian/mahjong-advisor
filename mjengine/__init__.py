"""麻将出牌建议引擎(纯算法层, 不依赖摄像头)。"""

from .tiles import (
    tile_name,
    tile_short,
    parse_hand,
    hand_to_string,
    hand_to_display,
    suits_present,
    SICHUAN_TILE_IDS,
    FULL_TILE_IDS,
    SUIT_NAMES,
)
from .advisor import Advisor

__all__ = [
    "Advisor",
    "tile_name",
    "tile_short",
    "parse_hand",
    "hand_to_string",
    "hand_to_display",
    "suits_present",
    "SICHUAN_TILE_IDS",
    "FULL_TILE_IDS",
    "SUIT_NAMES",
]
