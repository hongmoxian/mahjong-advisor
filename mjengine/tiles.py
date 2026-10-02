"""麻将牌的表示与转换。

使用 34 种牌型的整数编码(与 mahjong 库一致):
  0-8   一万..九万
  9-17  一筒..九筒
  18-26 一条..九条
  27-33 东 南 西 北 白 发 中
手牌用长度 34 的列表表示, 每项是该种牌的张数。
"""

import re
from typing import Iterable, List

SUIT_NAMES = ["万", "筒", "条", "字"]
SUIT_LETTERS = "mpsz"
HONOR_NAMES = ["东", "南", "西", "北", "白", "发", "中"]

SICHUAN_TILE_IDS = list(range(27))  # 血战/血流: 只有万筒条
FULL_TILE_IDS = list(range(34))

# 手动输入时支持的花色别名
_SUIT_ALIASES = {
    "万": "m",
    "筒": "p",
    "饼": "p",
    "条": "s",
    "索": "s",
    "東": "z",
}
_HONOR_ALIASES = {"东": "1", "南": "2", "西": "3", "北": "4", "白": "5", "发": "6", "财": "6", "中": "7"}

_TOKEN_RE = re.compile(r"([0-9]+)([mpsz])")


def tile_name(tid: int) -> str:
    """牌的中文短名, 如 '5万'、'东'。"""
    if tid < 27:
        return f"{tid % 9 + 1}{SUIT_NAMES[tid // 9]}"
    return HONOR_NAMES[tid - 27]


def tile_short(tid: int) -> str:
    """牌的 ASCII 短码, 如 '5m'、'1p'、'z1'。模板文件名也用它。"""
    if tid < 27:
        return f"{tid % 9 + 1}{SUIT_LETTERS[tid // 9]}"
    return f"z{tid - 26}"


def tid_from_short(short: str) -> int:
    """'5m'/'1p'/'z3' -> 编码; 非法输入抛 ValueError。"""
    m = re.fullmatch(r"([1-9])([mps])|z([1-7])", short.strip())
    if not m:
        raise ValueError(f"非法牌代码: {short!r}, 应形如 1m..9m / 1p..9p / 1s..9s / z1..z7")
    if m.group(1):
        return "mps".index(m.group(2)) * 9 + int(m.group(1)) - 1
    return 26 + int(m.group(3))


def _normalize(text: str) -> str:
    text = text.strip().replace(" ", "").replace(",", "")
    for cn, letter in _SUIT_ALIASES.items():
        text = text.replace(cn, letter)
    out = []
    for ch in text:
        if ch in _HONOR_ALIASES:
            # 中文字牌直接展开为 z<N>, 例如 东 -> z1
            out.append(f"z{_HONOR_ALIASES[ch]}")
        else:
            out.append(ch)
    text = "".join(out)
    # 统一 z 牌写法为"数字在前"(z1 -> 1z), 与 5m/3p 形式一致
    return re.sub(r"z([1-7])", r"\1z", text)


def parse_hand(text: str) -> List[int]:
    """解析手牌字符串为 34 长度计数列表。

    支持格式: '1112345678999m'、'123m456p78s'、'1万2万3万'、'东南西北' 等。
    """
    counts = [0] * 34
    text = _normalize(text)
    consumed = 0
    for m in _TOKEN_RE.finditer(text):
        nums, suit = m.group(1), m.group(2)
        if nums.startswith("0"):
            raise ValueError(f"牌号不能为 0: {nums}{suit}")
        for ch in nums:
            n = int(ch)
            if suit == "z":
                if n > 7:
                    raise ValueError(f"字牌只有 z1..z7: {nums}{suit}")
                tid = 26 + n
            else:
                tid = SUIT_LETTERS.index(suit) * 9 + n - 1
            counts[tid] += 1
            consumed += 1
    if consumed == 0:
        raise ValueError(f"无法从输入中解析出任何牌: {text!r}")
    if consumed > 14:
        raise ValueError(f"手牌张数超过 14: {consumed}")
    if any(c > 4 for c in counts):
        raise ValueError("同一种牌最多 4 张")
    return counts


def require_count(counts: Iterable[int]) -> int:
    return int(sum(counts))


def hand_to_string(counts: Iterable[int]) -> str:
    """转回紧凑字符串, 如 '1112345678999m'。"""
    counts = list(counts)
    parts = []
    for li, letter in enumerate("mps"):
        run = "".join(str(n + 1) * counts[li * 9 + n] for n in range(9))
        if run:
            parts.append(run + letter)
    zrun = "".join(str(n + 1) * counts[27 + n] for n in range(7))
    if zrun:
        parts.append(zrun + "z")
    return "".join(parts)


def hand_to_display(counts: Iterable[int]) -> str:
    """转成空格分隔的中文牌名, 如 '1万 1万 2万 ...'。"""
    counts = list(counts)
    tiles = [tile_name(t) for t in range(34) for _ in range(counts[t])]
    return " ".join(tiles) if tiles else "(空)"


def suits_present(counts: Iterable[int]) -> List[int]:
    """返回手牌中存在的花色列表: 0万 1筒 2条 (字牌返回 3)。"""
    counts = list(counts)
    present = []
    for s in range(3):
        if any(counts[s * 9 + n] for n in range(9)):
            present.append(s)
    if any(counts[26 + n] for n in range(7)):
        present.append(3)
    return present
