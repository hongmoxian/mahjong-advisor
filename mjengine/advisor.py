"""出牌建议引擎。

核心思路:
- 向听数 (shanten): 距离听牌还差几次换牌, 越小越好, 和牌 = -1。
- 进张 (ukeire): 打出某张后, 有哪些牌能进一步减小向听数, 以及还剩多少张。
- 缺一门 (血战/血流规则): 三门牌时必须先打缺, 打缺前只考虑从最弱的一门里出。
- 简单防守: 某张牌在牌河里出现得越多, 打出去越安全(别人已现过该牌)。

向听/和牌判定使用 mahjong 库 (MahjongRepository), 包含标准型与七对子。
"""

from typing import Dict, List, Optional

from mahjong.agari import Agari
from mahjong.shanten import Shanten

from .tiles import SICHUAN_TILE_IDS, FULL_TILE_IDS, SUIT_NAMES, tile_name, tile_short

AGARI = -1  # mahjong 库约定: 和牌形的向听数为 -1


class Advisor:
    def __init__(self, game: str = "sichuan"):
        if game not in ("sichuan", "full"):
            raise ValueError(f"未知规则: {game!r}, 可选 sichuan / full")
        self.game = game
        self.tile_ids = SICHUAN_TILE_IDS if game == "sichuan" else FULL_TILE_IDS
        self._shanten = Shanten()
        self._agari = Agari()

    # ---------- 基础计算 ----------

    def shanten(self, counts: List[int]) -> int:
        """13 或 14 张手牌的向听数(含七对), 和牌形返回 -1。"""
        return self._shanten.calculate_shanten(list(counts))

    def can_win(self, counts: List[int]) -> bool:
        """14 张是否为和牌形。(缺一门等规则限制由调用方判断)"""
        return self._agari.is_agari(list(counts))

    def can_win_sichuan(self, counts: List[int]) -> bool:
        """14 张且缺一门时是否为和牌形。"""
        suits = [s for s in range(3) if any(counts[s * 9 + n] for n in range(9))]
        if len(suits) > 2 or any(counts[26 + n] for n in range(7)):
            return False
        return self.can_win(counts)

    def ukeire(self, counts13: List[int], visible: Optional[List[int]] = None) -> List[Dict]:
        """13 张手牌的有效进张。

        返回 [{'tile': id, 'remaining': 剩余张数, 'gain': 向听改善量}, ...],
        按剩余张数降序。visible 为全场已现牌(牌河/副露)计数, 用于扣除张数。
        """
        if sum(counts13) != 13:
            raise ValueError("ukeire 只接受 13 张手牌")
        base = self.shanten(counts13)
        result = []
        for t in self.tile_ids:
            if counts13[t] >= 4:
                continue
            counts13[t] += 1
            s = self.shanten(counts13)
            counts13[t] -= 1
            if s < base:
                remaining = 4 - counts13[t]
                if visible is not None:
                    remaining -= visible[t]
                result.append({"tile": t, "remaining": max(remaining, 0), "gain": base - s})
        result.sort(key=lambda r: (-r["remaining"], r["tile"]))
        return result

    # ---------- 缺一门策略 ----------

    def choose_missing_suit(self, counts: List[int]) -> Optional[int]:
        """三门牌时选择应打缺的花色(张数最少的一门); 已不超过两门则返回 None。"""
        suit_counts = {s: sum(counts[s * 9:(s + 1) * 9]) for s in range(3)}
        present = [s for s, c in suit_counts.items() if c > 0]
        if len(present) <= 2:
            return None
        return min(present, key=lambda s: suit_counts[s])

    # ---------- 建议 ----------

    def advise_discard(self, counts14: List[int], visible: Optional[List[int]] = None,
                       defense: bool = False, auto_que: bool = True) -> Dict:
        """对 14 张手牌(摸牌后)给出打哪张的建议。

        返回 {'type': 'win'|'discard'|'invalid', ...}
        """
        n = sum(counts14)
        if n != 14:
            return {"type": "invalid", "count": n,
                    "message": f"手牌识别为 {n} 张, 需要 14 张(摸牌后)才能给出打牌建议"}

        if self.can_win_sichuan(counts14) if self.game == "sichuan" else self.can_win(counts14):
            return {"type": "win", "message": "可以胡牌! 直接点胡/自摸!"}

        que = self.choose_missing_suit(counts14) if (auto_que and self.game == "sichuan") else None

        options = []
        for d in self.tile_ids:
            if counts14[d] == 0:
                continue
            if que is not None and d // 9 != que:
                continue  # 缺门前只考虑从缺的那门出
            counts14[d] -= 1
            s_after = self.shanten(counts14)
            uk = self.ukeire(counts14, visible) if s_after > AGARI else []
            counts14[d] += 1
            options.append({
                "discard": d,
                "shanten_after": s_after,
                "ukeire_total": sum(r["remaining"] for r in uk),
                "waits": [tile_short(r["tile"]) for r in uk[:6]],
                "waits_name": [tile_name(r["tile"]) for r in uk[:6]],
                "safety": visible[d] if visible is not None else 0,
            })

        # 排序: 先向听数小; 防守模式优先打牌河现过的牌, 否则先进张多的优先
        if defense:
            options.sort(key=lambda o: (o["shanten_after"], -o["safety"], -o["ukeire_total"]))
        else:
            options.sort(key=lambda o: (o["shanten_after"], -o["ukeire_total"], -o["safety"]))

        return {
            "type": "discard",
            "que_suit": que,
            "que_name": SUIT_NAMES[que] if que is not None else None,
            "defense": defense,
            "options": options,
        }

    def advise_wait(self, counts13: List[int], visible: Optional[List[int]] = None) -> Dict:
        """对 13 张手牌(等待摸牌)给出分析: 向听数与有效进张。"""
        n = sum(counts13)
        if n != 13:
            return {"type": "invalid", "count": n, "message": f"手牌识别为 {n} 张, 需要 13 张"}
        s = self.shanten(counts13)
        uk = self.ukeire(counts13, visible) if s > AGARI else []
        return {
            "type": "wait",
            "shanten": s,
            "tenpai": s == 0,
            "ukeire": uk,
            "ukeire_total": sum(r["remaining"] for r in uk),
        }
