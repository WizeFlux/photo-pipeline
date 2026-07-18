"""Image display widget with synchronized zoom and pan.

- Mouse wheel: zoom in/out (shared across all viewers in the group)
- Mouse drag: pan when zoomed in (shared across all viewers)
- Zoom and pan are synchronized via zoomChanged/panChanged signals
  connected by the parent (MainWindow).
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QImage, QPixmap, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QFrame, QLabel


class ImageViewer(QLabel):
    """A labeled frame that displays a numpy/PIL image with zoom + pan.

    Holds the latest array so it can be re-scaled when the widget is resized.
    Keeps a reference to the raw bytes backing the QImage to prevent GC
    from freeing the buffer while Qt still references it (causes segfault).

    Zoom/pan signals:
        zoomChanged(float)  — new zoom factor (1.0 = fit)
        panChanged(int, int) — pan offset in pixels (dx, dy)
    The parent connects these across all viewers for synchronization.
    """

    zoomChanged = Signal(float)
    panChanged = Signal(int, int)

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._arr: np.ndarray | None = None
        self._qimage: QImage | None = None
        self._zoom: float = 1.0
        self._pan: QPoint = QPoint(0, 0)
        self._drag_start: QPoint | None = None
        self._pan_start: QPoint | None = None
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(240, 180)
        self.setStyleSheet(
            "QLabel { background-color: #141414; border: 1px solid #2a2a2a;"
            "  border-radius: 4px; color: #666; }"
        )
        self.setText(title or "—")
        self._show_title()
        # Enable mouse tracking for drag
        self.setMouseTracking(False)

    def set_title(self, title: str) -> None:
        self._title = title
        self._show_title()

    def _show_title(self) -> None:
        if self._arr is None:
            self.setText(self._title or "—")

    # ── Public API ────────────────────────────────────────────────────────────

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

    def set_zoom(self, zoom: float) -> None:
        """Set zoom factor (1.0 = fit). Called by sync — no signal emitted."""
        self._zoom = max(0.1, min(zoom, 20.0))
        self._render()

    def set_pan(self, dx: int, dy: int) -> None:
        """Set pan offset. Called by sync — no signal emitted."""
        self._pan = QPoint(dx, dy)
        self._render()

    def reset_zoom_pan(self) -> None:
        """Reset to fit (zoom=1.0, pan=0,0). Emits signals for sync."""
        self._zoom = 1.0
        self._pan = QPoint(0, 0)
        self._render()
        self.zoomChanged.emit(self._zoom)
        self.panChanged.emit(0, 0)

    def get_zoom(self) -> float:
        return self._zoom

    def get_pan(self) -> tuple[int, int]:
        return self._pan.x(), self._pan.y()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_qimage(self) -> None:
        """Build the QImage and keep a reference to prevent GC of the buffer."""
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
        rect = self.contentsRect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        # Base size = fit-to-rect (aspect preserved)
        fit_pix = pix.scaled(
            rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        # Apply zoom on top of fit
        if self._zoom != 1.0:
            zw = max(1, int(fit_pix.width() * self._zoom))
            zh = max(1, int(fit_pix.height() * self._zoom))
            fit_pix = fit_pix.scaled(zw, zh, Qt.KeepAspectRatio,
                                     Qt.SmoothTransformation)

        # If the zoomed pixmap is larger than the rect, we need to crop.
        # Use a full-size pixmap and let QLabel handle it, or manually offset.
        # Simplest: create a pixmap the size of the widget, paint the zoomed
        # image at the pan offset, and set it.
        if fit_pix.width() <= rect.width() and fit_pix.height() <= rect.height():
            # Fits without panning — center it
            super().setPixmap(fit_pix)
        else:
            # Larger than widget — crop with pan offset
            from PySide6.QtGui import QPainter, QPixmap as QPM
            canvas = QPM(rect.size())
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas)
            # Center the image, then apply pan
            x = (rect.width() - fit_pix.width()) // 2 + self._pan.x()
            y = (rect.height() - fit_pix.height()) // 2 + self._pan.y()
            painter.drawPixmap(x, y, fit_pix)
            painter.end()
            super().setPixmap(canvas)

    # ── Events ────────────────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render()

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Mouse wheel zooms. Emits zoomChanged for synchronization."""
        if self._arr is None:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        # Zoom factor: each 120 delta = 1.25x
        factor = 1.25 if delta > 0 else 1 / 1.25
        self._zoom = max(0.1, min(self._zoom * factor, 20.0))
        self._render()
        self.zoomChanged.emit(self._zoom)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Start drag for panning."""
        if event.button() == Qt.LeftButton and self._zoom > 1.0:
            self._drag_start = event.position().toPoint()
            self._pan_start = QPoint(self._pan)
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Drag to pan when zoomed in. Emits panChanged for sync."""
        if self._drag_start is not None and self._pan_start is not None:
            delta = event.position().toPoint() - self._drag_start
            self._pan = self._pan_start + delta
            self._render()
            self.panChanged.emit(self._pan.x(), self._pan.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End drag."""
        if event.button() == Qt.LeftButton:
            self._drag_start = None
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double-click resets zoom and pan."""
        if event.button() == Qt.LeftButton:
            self.reset_zoom_pan()