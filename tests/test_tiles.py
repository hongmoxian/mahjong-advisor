from mjengine.tiles import (
    parse_hand, hand_to_string, hand_to_display, tile_name, tile_short,
    tid_from_short, suits_present,
)


def test_parse_and_roundtrip():
    counts = parse_hand("1112345678999m")
    assert sum(counts) == 13
    assert hand_to_string(counts) == "1112345678999m"


def test_parse_multi_suit_and_honors():
    counts = parse_hand("123m456p78s11z")
    assert hand_to_string(counts) == "123m456p78s11z"
    assert suits_present(counts) == [0, 1, 2, 3]


def test_parse_chinese_aliases():
    assert hand_to_string(parse_hand("1万2万3万")) == "123m"
    assert hand_to_string(parse_hand("1筒2饼3条4索")) == "12p34s"
    assert hand_to_string(parse_hand("东南西北中")) == "12347z"


def test_tile_names():
    assert tile_name(0) == "1万"
    assert tile_name(17) == "9筒"
    assert tile_name(26) == "9条"
    assert tile_name(27) == "东"
    assert tile_name(33) == "中"
    assert tile_short(4) == "5m"
    assert tid_from_short("5m") == 4
    assert tid_from_short("z1") == 27


def test_parse_errors():
    import pytest
    with pytest.raises(ValueError):
        parse_hand("0m")
    with pytest.raises(ValueError):
        parse_hand("55555m")
    with pytest.raises(ValueError):
        parse_hand("99z")  # 字牌只有 z1..z7
    with pytest.raises(ValueError):
        parse_hand("hello")
