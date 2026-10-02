"""建议引擎测试: 向听、进张、缺一门、防守、和牌判定。"""

from mjengine import Advisor, parse_hand


def test_shanten_known_values():
    a = Advisor(game="sichuan")
    # 听牌: 四个面子 + 单张 9s
    assert a.shanten(parse_hand("123456789m123p9s")) == 0
    # 两向听: 三个面子 + 三个孤张
    assert a.shanten(parse_hand("123m456m789m1p9p5s")) == 2
    # 七对: 6 对 + 1 单张 -> 听牌; 5 对 + 3 单张 -> 1 向听
    assert a.shanten(parse_hand("1122334455m66p7s")) == 0
    assert a.shanten(parse_hand("1122334455m67p8s")) == 1


def test_win_detection():
    a = Advisor(game="sichuan")
    # 111m 234m 567m 999m + 55m
    assert a.can_win_sichuan(parse_hand("1112345678999m5m")) is True
    # 三门牌即使牌形完整也不能胡(未打缺)
    assert a.can_win_sichuan(parse_hand("123m456m123p789s55m")) is False


def test_advise_discard_picks_efficient_tile():
    a = Advisor(game="sichuan")
    counts = parse_hand("123m456m789m12p999p")  # 14张, 两门牌
    result = a.advise_discard(counts)
    assert result["type"] == "discard"
    best = result["options"][0]
    assert best["discard"] == 17          # 打 9p
    assert best["shanten_after"] == 0     # 打完即听牌(12p 听 3p)
    assert best["waits"] == ["3p"]
    assert best["ukeire_total"] == 4


def test_advise_discard_reports_win():
    a = Advisor(game="sichuan")
    counts = parse_hand("1112345678999m5m")  # 14张已和
    assert a.advise_discard(counts)["type"] == "win"


def test_que_suit_restriction():
    a = Advisor(game="sichuan")
    # 万6张 筒3张 条5张 -> 缺筒
    counts = parse_hand("123m456m789p123s55s")
    result = a.advise_discard(counts)
    assert result["que_suit"] == 1
    assert result["que_name"] == "筒"
    for o in result["options"]:
        assert 9 <= o["discard"] <= 17  # 只建议打筒


def test_ukeire_counts():
    a = Advisor(game="sichuan")
    counts = parse_hand("123m456m789m1122p")  # 13张, 1p/2p 双碰听
    assert a.shanten(counts) == 0
    uk = a.ukeire(counts)
    tiles = {r["tile"] for r in uk}
    assert tiles == {9, 10}  # 1p, 2p
    assert all(r["remaining"] == 2 for r in uk)
    assert sum(r["remaining"] for r in uk) == 4


def test_ukeire_respects_visible():
    a = Advisor(game="sichuan")
    counts = parse_hand("123m456m789m1122p")
    visible = [0] * 34
    visible[9] = 4  # 1p 全部现过
    uk = a.ukeire(counts, visible)
    by_tile = {r["tile"]: r["remaining"] for r in uk}
    assert by_tile[9] == 0
    assert by_tile[10] == 2


def test_defense_flips_choice():
    a = Advisor(game="sichuan")
    counts = parse_hand("123m456m789m12p999p")  # 14张, 两门牌
    visible = [0] * 34
    visible[11] = 4  # 3p 全部现过: 打 9p 后没有任何进张
    visible[17] = 1  # 9p 别人打过 1 张
    normal = a.advise_discard(counts, visible, defense=False)
    defense = a.advise_discard(counts, visible, defense=True)
    assert normal["options"][0]["discard"] == 9    # 进攻: 打 1p 保留 2p 进张
    assert defense["options"][0]["discard"] == 17  # 防守: 优先打现过的 9p


def test_wait_advice():
    a = Advisor(game="sichuan")
    result = a.advise_wait(parse_hand("123456789m123p9s"))
    assert result["tenpai"] is True
    assert [r["tile"] for r in result["ukeire"]] == [26]
    assert result["ukeire"][0]["remaining"] == 3


def test_invalid_hand():
    a = Advisor(game="sichuan")
    assert a.advise_discard(parse_hand("123m456p789s"))["type"] == "invalid"  # 9张
    assert a.advise_wait(parse_hand("123m456p789s"))["type"] == "invalid"
