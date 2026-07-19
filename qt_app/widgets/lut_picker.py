"""LUT picker dialog — shows preview thumbnails of all available LUTs.

Each thumbnail is the current image processed with all current slider
settings (including lut_intensity) + the given LUT applied. Clicking a
thumbnail closes the dialog and emits lutSelected with the chosen LUT path.
"""

from __future__ import annotations

import os
import numpy as np
from PIL import Image
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
    QPushButton, QHBoxLayout, QFrame,
)

from pipeline.gpu_ops import gpu_process_from_pil
from qt_app.state import list_luts


_THUMB_W = 320
_THUMB_H = 240
_LABEL_H = 22


class _LutThumbWorker(QThread):
    """Generate one LUT thumbnail in a background thread."""
    thumb_ready = Signal(str, object)  # lut_path, np.ndarray (or None on error)

    def __init__(self, image: Image.Image, base_params: dict, lut_path: str,
                 intensity: float, parent=None):
        super().__init__(parent)
        self._image = image
        self._base_params = dict(base_params)
        self._lut_path = lut_path
        self._intensity = intensity

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            params = dict(self._base_params)
            if self._lut_path and self._lut_path != "None":
                params["lut_path"] = self._lut_path
                params["lut_intensity"] = self._intensity
            else:
                params["lut_path"] = None
            result = gpu_process_from_pil(self._image, params)
            if self.isInterruptionRequested():
                return
            self.thumb_ready.emit(self._lut_path, np.array(result))
        except Exception:
            self.thumb_ready.emit(self._lut_path, None)


def _short_name(lut_path: str) -> str:
    """Short display name for a LUT path."""
    if lut_path == "None":
        return "None (no LUT)"
    return os.path.basename(lut_path)


class _LutThumb(QFrame):
    """A single LUT thumbnail — clickable, shows preview + name label below."""

    clicked = Signal(str)

    def __init__(self, lut_path: str, parent=None):
        super().__init__(parent)
        self._lut_path = lut_path
        self.setFixedSize(_THUMB_W, _THUMB_H + _LABEL_H)
        self.setStyleSheet(
            "QFrame { background-color: #1a1a1a; border: 2px solid #333;"
            "  border-radius: 4px; }"
            "QFrame:hover { border-color: #ff8c00; }"
            "QLabel { border: none; background: transparent; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Image label (top)
        self._image_label = QLabel()
        self._image_label.setFixedSize(_THUMB_W, _THUMB_H)
        self._image_label.setAlignment(Qt.AlignCenter)
        self._image_label.setText("⏳")
        self._image_label.setStyleSheet("color: #888; font-size: 16px;")
        layout.addWidget(self._image_label)

        # Name label (bottom, separate from image)
        self._name_label = QLabel(_short_name(lut_path))
        self._name_label.setFixedHeight(_LABEL_H)
        self._name_label.setAlignment(Qt.AlignCenter)
        self._name_label.setStyleSheet(
            "color: #ccc; font-size: 11px; font-weight: bold;"
            "  background-color: #222;"
        )
        layout.addWidget(self._name_label)

    def set_image(self, arr: np.ndarray) -> None:
        """Display the processed thumbnail at high quality (Retina-aware)."""
        arr = np.ascontiguousarray(arr, dtype=np.uint8)
        h, w = arr.shape[:2]
        # Center-crop to thumbnail aspect ratio
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
        # Render at device pixels for Retina/HiDPI sharpness.
        # CSS size is _THUMB_W × _THUMB_H; physical size is that × DPR.
        dpr = self._image_label.devicePixelRatio() or 1.0
        phys_w = int(_THUMB_W * dpr)
        phys_h = int(_THUMB_H * dpr)
        # High-quality resize (LANCZOS) at full physical resolution
        img = Image.fromarray(arr).resize((phys_w, phys_h), Image.LANCZOS)
        arr = np.ascontiguousarray(np.array(img), dtype=np.uint8)
        h, w = arr.shape[:2]
        bytes_per_line = 3 * w
        self._bytes = arr.tobytes()  # prevent GC
        qimg = QImage(self._bytes, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        # Tell Qt the pixmap is DPR× denser so it displays at CSS size
        pix.setDevicePixelRatio(dpr)
        self._image_label.setPixmap(pix)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._lut_path)
        super().mousePressEvent(event)


class LutPickerDialog(QDialog):
    """Grid of LUT preview thumbnails. Click to select."""

    lutSelected = Signal(str)

    def __init__(self, image: Image.Image, base_params: dict,
                 lut_intensity: float = 1.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pick LUT")
        self.setModal(True)
        self.setMinimumWidth(1000)
        self._image = image
        self._base_params = dict(base_params)
        self._lut_intensity = lut_intensity
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
        grid.setSpacing(8)
        grid.setContentsMargins(4, 4, 4, 4)

        luts = list_luts()
        cols = 4
        for i, lut in enumerate(luts):
            thumb = _LutThumb(lut)
            thumb.clicked.connect(self._on_thumb_clicked)
            grid.addWidget(thumb, i // cols, i % cols)
            self._thumbs[lut] = thumb
            # Start worker — pass current lut_intensity so it affects previews
            worker = _LutThumbWorker(
                self._image, self._base_params, lut, self._lut_intensity
            )
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