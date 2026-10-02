"""配置读写: config.json 保存摄像头、识别区域、模板与阈值。"""

import json
import os
from typing import Optional

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")

DEFAULT_CONFIG = {
    "game": "sichuan",           # sichuan: 血战(只有万筒条, 需缺一门) / full: 34种牌
    "source": {"type": "camera", "index": 0},
    "hand_roi": None,            # [x, y, w, h] 手牌区域
    "discard_roi": None,         # [x, y, w, h] 全部牌河区域
    "threshold": 0.62,           # 模板匹配置信度阈值
    "min_tile_area": 300,        # 牌面轮廓最小面积(像素)
    "max_tile_area": 80000,      # 牌面轮廓最大面积
    "templates": {},             # {"5m": "templates/5m.png", ...}
}


def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
        cfg.update({k: v for k, v in user.items() if v is not None})
    return cfg


def save_config(cfg: dict, path: str = DEFAULT_CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def templates_dir(cfg: dict, config_path: str = DEFAULT_CONFIG_PATH) -> str:
    d = os.path.join(os.path.dirname(os.path.abspath(config_path)), "templates")
    os.makedirs(d, exist_ok=True)
    return d


def missing_settings(cfg: dict) -> Optional[str]:
    """返回第一条尚未完成的配置提示, 全部就绪返回 None。"""
    if cfg.get("hand_roi") is None:
        return "尚未标定手牌区域 (按 h)"
    if cfg.get("discard_roi") is None:
        return "尚未标定牌河区域 (按 d)"
    if not cfg.get("templates"):
        return "尚未截取任何牌面模板 (按 t)"
    return None
