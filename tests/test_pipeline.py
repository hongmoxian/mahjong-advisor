"""端到端管线测试: 合成画面 -> 轮廓找牌 -> 模板匹配 -> 建议。"""

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from tests.synth import make_card, make_frame, codes_of
from mjengine import Advisor, parse_hand
from vision.detector import TileDetector

ALL_CODES = [f"{n}{s}" for s in "mps" for n in "123456789"]


@pytest.fixture(scope="module")
def detector():
    templates = {c: make_card(c) for c in ALL_CODES}
    cfg = {"threshold": 0.6, "min_tile_area": 300, "max_tile_area": 80000}
    return TileDetector(templates, cfg)


def test_detect_hand(detector):
    frame, hand_roi, _ = make_frame("123456789m123p9s")
    dets, codes = detector.detect_hand(frame, list(hand_roi))
    assert codes == "".join(codes_of("123456789m123p9s"))
    assert len(dets) == 13
    # 从左到右有序
    xs = [d.box[0] for d in dets]
    assert xs == sorted(xs)


def test_detect_discards(detector):
    frame, _, discard_roi = make_frame("123456789m123p9s", discards="55m1s3s1p5p9p")
    counts, dets = detector.detect_discards(frame, list(discard_roi))
    assert sum(counts) == 7
    assert counts[4] == 2            # 5m 两张
    assert counts[18] == 1 and counts[20] == 1  # 1s, 3s


def test_pipeline_advice(detector):
    """识别 -> 13张听牌分析 (等 9s)。"""
    hand13 = "123456789m123p9s"
    frame, hand_roi, _ = make_frame(hand13)
    dets, codes = detector.detect_hand(frame, list(hand_roi))
    assert codes == "".join(codes_of(hand13))
    counts = [0] * 34
    for d in dets:
        counts[d.tid] += 1
    advisor = Advisor(game="sichuan")
    result = advisor.advise_wait(counts)
    assert result["tenpai"] is True
    assert [r["tile"] for r in result["ukeire"]] == [26]

    # 14张时能给出打牌建议, 且最优打出后达到最小向听
    hand14 = "123456789m123p99s"
    frame2, hand_roi2, _ = make_frame(hand14)
    dets2, codes2 = detector.detect_hand(frame2, list(hand_roi2))
    assert codes2 == "".join(codes_of(hand14))
    counts2 = [0] * 34
    for d in dets2:
        counts2[d.tid] += 1
    assert sum(counts2) == 14
    result2 = advisor.advise_discard(counts2)
    assert result2["options"][0]["shanten_after"] == 0
