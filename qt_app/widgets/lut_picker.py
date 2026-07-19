"""LUT picker dialog — shows preview thumbnails of all available LUTs.

Each thumbnail is the current image processed with all current slider
settings + the given LUT applied. Clicking a thumbnail closes the dialog
and emits lutSelected with the chosen LUT path.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, Signal, QThread, Signal as _Sig
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
    QSizePolicy, QPushButton, QHBoxLayout,
)

from pipeline.gpu_ops import gpu_process_from_pil
from qt_app.state import list_luts, params_from_values


_THUMB_W = 200
_THUMB_H = 150


class _LutThumbWorker(QThread):
    """Generate one LUT thumbnail in a background thread."""
    thumb_ready = Signal(str, object)  # lut_path, np.ndarray (or None on error)

    def __init__(self, image: Image.Image, base_params: dict, lut_path: str, parent=None):
        super().__init__(parent)
        self._image = image
        self._base_params = dict(base_params)
        self._lut_path = lut_path

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            params = dict(self._base_params)
            if self._lut_path and self._lut_path != "None":
                params["lut_path"] = self._lut_path
                params["lut_intensity"] = 1.0
            else:
                params["lut_path"] = None
            result = gpu_process_from_pil(self._image, params)
            if self.isInterruptionRequested():
                return
            self.thumb_ready.emit(self._lut_path, np.array(result))
        except Exception:
            self.thumb_ready.emit(self._lut_path, None)


class _LutThumb(QLabel):
    """A single LUT thumbnail — clickable, shows name + preview."""

    clicked = Signal(str)

    def __init__(self, lut_path: str, parent=None):
        super().__init__(parent)
        self._lut_path = lut_path
        self.setFixedSize(_THUMB_W, _THUMB_H + 20)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "QLabel { background-color: #1a1a1a; border: 2px solid #333;"
            "  border-radius: 4px; color: #888; }"
            "QLabel:hover { border-color: #ff8c00; }"
        )
        name = lut_path if lut_path != "None" else "None (no LUT)"
        self.setText(f"⏳\n{name}")

    def set_image(self, arr: np.ndarray) -> None:
        """Display the processed thumbnail."""
        arr = np.ascontiguousarray(arr, dtype=np.uint8)
        h, w = arr.shape[:2]
        # Crop/resize to thumbnail aspect ratio
        target_ratio = _THUMB_W / _THUMB_H
        img_ratio = w / h
        if img_ratio > target_ratio:
            new_w = int(h * target_ratio)
            x0 = (w - new_w) // 2
            arr = arr[:, x0:x0+new_w]
        else:
            new_h = int(w / target_ratio)
            y0 = (h - new_h) // 2
            arr = arr[y0:y0+new_h, :]
        # Resize to thumbnail size
        img = Image.fromarray(arr).resize((_THUMB_W, _THUMB_H), Image.BILINEAR)
        arr = np.array(img)
        h, w = arr.shape[:2]
        bytes_per_line = 3 * w
        qimg = QImage(arr.tobytes(), w, h, bytes_per_line, QImage.Format_RGB888)
        self._bytes = arr.tobytes()  # prevent GC
        pix = QPixmap.fromImage(qimg)
        # Add name label at bottom
        from PySide6.QtGui import QPainter, QFont, QColor, QPen
        canvas = QPixmap(_THUMB_W, _THUMB_H + 20)
        canvas.fill(QColor("#1a1a1a"))
        painter = QPainter(canvas)
        painter.drawPixmap(0, 0, pix)
        painter.setPen(QColor("#ccc"))
        font = QFont("Sans", 8)
        painter.setFont(font)
        name = self._lut_path if self._lut_path != "None" else "None"
        # Shorten name
        if len(name) > 28:
            name = "..." + name[-25:]
        painter.drawText(4, _THUMB_H + 14, name)
        painter.end()
        self.setPixmap(canvas)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._lut_path)
        super().mousePressEvent(event)


class LutPickerDialog(QDialog):
    """Grid of LUT preview thumbnails. Click to select."""

    lutSelected = Signal(str)

    def __init__(self, image: Image.Image, base_params: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick LUT")
        self.setModal(True)
        self.setMinimumWidth(900)
        self._image = image
        self._base_params = dict(base_params)
        self._workers: list[_LutThumbWorker] = []
        self._thumbs: dict[str, _LutThumb] = {}
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Scroll area with grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        grid = QGridLayout(scroll_content)
        grid.setSpacing(6)
        grid.setContentsMargins(4, 4, 4, 4)

        luts = list_luts()
        cols = 4
        for i, lut in enumerate(luts):
            thumb = _LutThumb(lut)
            thumb.clicked.connect(self._on_thumb_clicked)
            grid.addWidget(thumb, i // cols, i % cols)
            self._thumbs[lut] = thumb
            # Start worker
            worker = _LutThumbWorker(self._image, self._base_params, lut)
            worker.thumb_ready.connect(self._on_thumb_ready)
            self._workers.append(worker)
            worker.start()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        # Cancel button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_thumb_ready(self, lut_path: str, arr: object) -> None:
        if arr is not None and lut_path in self._thumbs:
            self._thumbs[lut_path].set_image(arr)

    def _on_thumb_clicked(self, lut_path: str) -> None:
        self.lutSelected.emit(lut_path)
        self.accept()

    def closeEvent(self, event):
        # Stop all workers and wait for them to finish to avoid segfaults
        for w in self._workers:
            w.requestInterruption()
            w.wait(1000)
        self._workers.clear()
        super().closeEvent(event)