"""牌面识别: 在标定区域内找出每张牌并分类。

流程: 区域裁剪 -> 灰度 -> OTSU 二值化(牌面亮于背景) -> 轮廓找牌 -> 逐张模板匹配。
模板由 calibrate.py 从实际游戏画面截取, 存于 templates/<code>.png (如 5m.png)。
"""

from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from mjengine.tiles import tid_from_short


class Detection:
    def __init__(self, tid: Optional[int], score: float, box: Tuple[int, int, int, int]):
        self.tid = tid          # None 表示低于阈值, 无法识别
        self.score = score
        self.box = box          # 相对整帧的 (x, y, w, h)


class TileDetector:
    def __init__(self, templates: Dict[str, np.ndarray], cfg: dict):
        """templates: {'5m': 灰度图, ...}"""
        if not templates:
            raise ValueError("没有任何模板, 请先用 calibrate.py 截取牌面模板")
        self.threshold = float(cfg.get("threshold", 0.62))
        self.min_area = int(cfg.get("min_tile_area", 300))
        self.max_area = int(cfg.get("max_tile_area", 80000))
        self._items = []
        for code, img in templates.items():
            if img.ndim == 3:  # 彩色模板自动转灰度
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            self._items.append((tid_from_short(code), img))
        self._items.sort(key=lambda it: it[0])

    # ---------- 对外接口 ----------

    def detect_hand(self, frame: np.ndarray, roi: List[int]) -> Tuple[List[Detection], str]:
        """返回按从左到右排序的识别结果与手牌短码串(含 '?')。"""
        dets = self._detect(frame, roi)
        codes = "".join(
            "?" if d.tid is None else _short_by_tid(d.tid) for d in dets
        )
        return dets, codes

    def detect_discards(self, frame: np.ndarray, roi: List[int]) -> Tuple[List[int], List[Detection]]:
        """返回 34 长度已现牌计数与全部识别结果。"""
        dets = self._detect(frame, roi)
        counts = [0] * 34
        for d in dets:
            if d.tid is not None:
                counts[d.tid] += 1
        return counts, dets

    # ---------- 内部实现 ----------

    def _detect(self, frame: np.ndarray, roi: List[int]) -> List[Detection]:
        x, y, w, h = [int(v) for v in roi]
        H, W = frame.shape[:2]
        x, y = max(x, 0), max(y, 0)
        w, h = min(w, W - x), min(h, H - y)
        if w <= 0 or h <= 0:
            return []
        region = frame[y:y + h, x:x + w]
        crops = self._tile_crops(region)
        out = []
        for cx, cy, cw, ch, crop in crops:
            tid, score = self._classify(crop)
            out.append(Detection(tid, score, (x + cx, y + cy, cw, ch)))
        out.sort(key=lambda d: d.box[0])
        return out

    def _tile_crops(self, region: np.ndarray) -> List[Tuple[int, int, int, int, np.ndarray]]:
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        crops = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.min_area or area > self.max_area:
                continue
            cx, cy, cw, ch = cv2.boundingRect(c)
            if ch == 0 or not 0.35 <= cw / ch <= 1.4:
                continue
            crops.append((cx, cy, cw, ch, region[cy:cy + ch, cx:cx + cw]))
        crops.sort(key=lambda t: t[0])
        return crops

    def _classify(self, crop: np.ndarray) -> Tuple[Optional[int], float]:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        best_tid, best_score = None, -1.0
        for tid, tmpl in self._items:
            th, tw = tmpl.shape[:2]
            resized = cv2.resize(gray, (tw, th), interpolation=cv2.INTER_AREA)
            score = float(cv2.matchTemplate(resized, tmpl, cv2.TM_CCOEFF_NORMED)[0, 0])
            if score > best_score:
                best_tid, best_score = tid, score
        if best_score < self.threshold:
            return None, max(best_score, 0.0)
        return best_tid, best_score


def _short_by_tid(tid: int) -> str:
    from mjengine.tiles import tile_short
    return tile_short(tid)


def load_templates(cfg: dict) -> Dict[str, np.ndarray]:
    """按配置读取模板文件。"""
    import os
    templates = {}
    for code, path in cfg.get("templates", {}).items():
        if not os.path.exists(path):
            continue
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            templates[code] = img
    return templates
