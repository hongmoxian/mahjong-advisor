"""画面来源抽象: 摄像头 / 图片文件 / 视频文件。"""

import os
from typing import Optional

import cv2


class FrameSource:
    """统一读取帧。用法:
      FrameSource("cam:0")   摄像头 0
      FrameSource("shot.png") 图片(每次 read 都返回同一帧)
      FrameSource("demo.mp4") 视频
    """

    def __init__(self, source: str = "cam:0"):
        self.is_image = False
        self._image = None
        self._cap = None
        src = source.strip()
        if src.startswith("cam:"):
            self._cap = cv2.VideoCapture(int(src[4:]))
            if not self._cap.isOpened():
                raise RuntimeError(f"无法打开摄像头 {src}, 试试 cam:1 (系统设置里给终端授权摄像头)")
        else:
            if not os.path.exists(src):
                raise FileNotFoundError(src)
            if src.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                self._image = cv2.imread(src)
                if self._image is None:
                    raise RuntimeError(f"图片读取失败: {src}")
                self.is_image = True
            else:
                self._cap = cv2.VideoCapture(src)
                if not self._cap.isOpened():
                    raise RuntimeError(f"无法打开视频: {src}")

    def read(self) -> Optional[any]:
        if self._image is not None:
            return self._image.copy()
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def release(self):
        if self._cap is not None:
            self._cap.release()
