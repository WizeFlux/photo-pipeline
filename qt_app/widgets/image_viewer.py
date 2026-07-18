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
    Keeps a reference to the raw bytes backing the QImage to prevent GC
    from freeing the buffer while Qt still references it (causes segfault).
    """

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._arr: np.ndarray | None = None
        self._qimage: QImage | None = None  # keeps the bytes buffer alive
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
            self._qimage = None
            self._image_bytes = None
            self.clear()
            self._show_title()
            return
        self._arr = np.ascontiguousarray(arr, dtype=np.uint8)
        self._build_qimage()
        self._render()

    def set_pil(self, img: Image.Image) -> None:
        arr = np.array(img)
        self.set_array(arr)

    def _build_qimage(self) -> None:
        """Build the QImage and keep a reference to prevent GC of the buffer.

        QImage does not copy the bytes buffer — if Python GC frees it while
        Qt still references the memory, the app segfaults on repaint/resize.
        Storing it as an attribute keeps it alive until the next image.
        """
        h, w = self._arr.shape[:2]
        bytes_per_line = 3 * w
        self._image_bytes = self._arr.tobytes()
        self._qimage = QImage(
            self._image_bytes, w, h, bytes_per_line, QImage.Format_RGB888
        )

    def _render(self) -> None:
        if self._qimage is None:
            return
        pix = QPixmap.fromImage(self._qimage)
        # Scale to fit the content rect (already accounts for margins)
        rect = self.contentsRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return
        scaled = pix.scaled(
            rect.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        super().setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render()