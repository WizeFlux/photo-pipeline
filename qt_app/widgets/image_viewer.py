"""Image display widget with aspect-ratio-preserving scaling."""

from __future__ import annotations

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QLabel


class ImageViewer(QLabel):
    """A labeled frame that displays a numpy/PIL image, scaled to fit.

    Holds the latest array so it can be re-scaled when the widget is resized.
    """

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._arr: np.ndarray | None = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(240, 180)
        self.setStyleSheet(
            "QLabel { background-color: #141414; border: 1px solid #2a2a2a;"
            "  border-radius: 4px; color: #666; }"
        )
        self.setText(title or "—")
        self._show_title()

    def set_title(self, title: str) -> None:
        self._title = title
        self._show_title()

    def _show_title(self) -> None:
        if self._arr is None:
            self.setText(self._title or "—")

    def set_array(self, arr: np.ndarray | None) -> None:
        """Display a (H, W, 3) uint8/float array. None clears the viewer."""
        if arr is None:
            self._arr = None
            self.clear()
            self._show_title()
            return
        self._arr = np.asarray(arr, dtype=np.uint8)
        self._render()

    def set_pil(self, img: Image.Image) -> None:
        arr = np.array(img)
        self.set_array(arr)

    def _render(self) -> None:
        if self._arr is None:
            return
        h, w = self._arr.shape[:2]
        bytes_per_line = 3 * w
        qimg = QImage(self._arr.tobytes(), w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        # Scale to fit while keeping aspect ratio
        scaled = pix.scaled(
            self.size() - self.contentsMargins(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        super().setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render()