"""Adjustment sliders — 5 groups in a single row.

Groups: Exposure | Contrast | White Balance | Saturation | LUT
All emit `paramsChanged(dict)` with the full 14-param set.

The most recently moved slider is highlighted orange (`set_active`).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider,
    QVBoxLayout, QWidget,
)

from qt_app.state import PARAM_DEFAULTS, list_luts
from qt_app.widgets.scurve_editor import SCurveEditor


# ─── Compact QSS ─────────────────────────────────────────────────────────────

_COMPACT_QSS = """
QGroupBox { margin-top: 11px; padding: 10px 6px 6px 6px; }
"""

# Orange highlight applied to the most-recently moved slider's handle.
_ACTIVE_SLIDER_QSS = """
QSlider::handle:horizontal {
    background: #ff8c00;
    border: 1px solid #cc7000;
    width: 12px;
    height: 12px;
    margin: -6px 0;
    border-radius: 6px;
}
QSlider::sub-page:horizontal {
    background: #ff8c00;
    border-radius: 3px;
}
"""


# ─── Custom slider with wheel support ────────────────────────────────────────

class _Slider(QSlider):
    """QSlider with finer wheel control and wheel-activated signal.

    Wheel behavior:
      • Normal scroll     — 1 internal unit (finest possible)
      • Ctrl + scroll     — 1% of range per notch (moderate navigation)
      • Shift + scroll    — 2% of range per notch (fast large moves)
    All wheel events emit `wheelActivated` so the parent can highlight the slider.
    """

    wheelActivated = Signal()

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._single_step = 1

    def set_single_step(self, step: int) -> None:
        self._single_step = max(1, step)
        self.setSingleStep(step)

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Don't let Qt's default handle it — we want custom step sizes and
        # we must emit wheelActivated regardless of direction.
        notches = event.angleDelta().y() / 120.0
        if notches == 0:
            event.ignore()
            return

        rng = self.maximum() - self.minimum()
        # Normal: finest (1). Ctrl: 1% of range. Shift: 2% of range.
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            step = max(1, rng // 100)
        elif modifiers & Qt.ShiftModifier:
            step = max(1, rng // 50)  # 2%
        else:
            step = 1  # finest

        delta = int(step * (-1 if notches > 0 else 1))  # inverted: scroll up = decrease
        self.setValue(self.value() + delta)
        self.wheelActivated.emit()
        event.accept()


# ─── Labeled slider ──────────────────────────────────────────────────────────

class _LabeledSlider(QWidget):
    """Compact slider: name label | slider | value label, on one line."""

    valueChanged = Signal(float)
    activated = Signal(object)  # emits self when the user grabs this slider

    def __init__(self, name: str, vmin, vmax, default, step: float = 1.0,
                 fmt: str = "{:.2f}", parent=None):
        super().__init__(parent)
        self._step = step
        self._fmt = fmt
        self._is_float = isinstance(default, float) or step < 1.0
        self._scale = 1.0 / step if self._is_float else 1.0
        int_min = int(vmin * self._scale)
        int_max = int(vmax * self._scale)
        int_default = int(round(float(default) * self._scale))

        self.slider = _Slider(Qt.Horizontal)
        self.slider.setRange(int_min, int_max)
        self.slider.setValue(int_default)
        self.slider.set_single_step(1)

        self.name_label = QLabel(name)
        self.name_label.setMinimumWidth(62)
        self.name_label.setMaximumWidth(62)
        self.value_label = QLabel(self._format(default))
        self.value_label.setMinimumWidth(34)
        self.value_label.setMaximumWidth(34)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setObjectName("value-label")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(4)
        layout.addWidget(self.name_label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.value_label)

        # sliderPressed → this slider becomes the "active" (orange) one.
        # sliderMoved gives live updates during drag (before mouse release).
        # wheelActivated → same activation path for mouse-wheel adjustments.
        self.slider.sliderPressed.connect(self._on_pressed)
        self.slider.wheelActivated.connect(self._on_pressed)
        self.slider.valueChanged.connect(self._on_changed)

    # ── Active-highlight API ──────────────────────────────────────────────

    def set_active(self, active: bool) -> None:
        """Apply or remove the orange highlight on this slider."""
        if active:
            self.slider.setStyleSheet(_ACTIVE_SLIDER_QSS)
            self.name_label.setStyleSheet("color: #ff8c00; font-weight: bold;")
        else:
            self.slider.setStyleSheet("")
            self.name_label.setStyleSheet("")

    def _on_pressed(self) -> None:
        self.activated.emit(self)

    def _format(self, value) -> str:
        if self._is_float:
            return self._fmt.format(float(value))
        return str(int(value))

    def _on_changed(self, int_val: int) -> None:
        value = int_val / self._scale if self._is_float else int_val
        self.value_label.setText(self._format(value))
        self.valueChanged.emit(value)

    def value(self):
        int_val = self.slider.value()
        return int_val / self._scale if self._is_float else int_val

    def set_value(self, value) -> None:
        int_val = int(round(float(value) * self._scale))
        self.slider.blockSignals(True)
        self.slider.setValue(int_val)
        self.value_label.setText(self._format(value))
        self.slider.blockSignals(False)


# ─── Slider spec tables ──────────────────────────────────────────────────────
# (key, label, min, max, default, step, fmt)

_EXPOSURE_SPECS = [
    ("ev", "EV", -3, 3, 0.0, 0.01, "{:+.2f}"),
    ("highlights", "Highlights", -100, 100, 0, 1, "{:+d}"),
    ("shadows", "Shadows", -100, 100, 0, 1, "{:+d}"),
]

# Contrast group removed — the interactive S-Curve editor (6th column)
# replaces gamma, contrast_amount, s_curve, black_point, white_point.
# gamma is also handled by the S-Curve (tone shaping).
_CONTRAST_SPECS: list[tuple] = []

_WB_SPECS = [
    ("temperature", "Temp", -100, 100, 0, 1, "{:+d}"),
    ("tint", "Tint", -100, 100, 0, 1, "{:+d}"),
]

_SAT_SPECS = [
    ("saturation", "Sat", -100, 100, 0, 1, "{:+d}"),
    ("vibrance", "Vibrance", -100, 100, 0, 1, "{:+d}"),
]


def _build_slider_group(title: str, specs: list[tuple], panel) -> QGroupBox:
    """Build a compact QGroupBox with one slider per spec."""
    group = QGroupBox(title)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(6, 10, 6, 6)
    layout.setSpacing(2)
    for key, label, vmin, vmax, default, step, fmt in specs:
        slider = _LabeledSlider(label, vmin, vmax, default, step, fmt)
        slider.valueChanged.connect(panel._on_param_changed)
        slider.activated.connect(panel._set_active_slider)
        panel._sliders[key] = slider
        layout.addWidget(slider)
    layout.addStretch()
    return group


def _build_lut_group(panel) -> QGroupBox:
    """Build the LUT group: file dropdown + pick button + intensity slider."""
    group = QGroupBox("LUT")
    layout = QVBoxLayout(group)
    layout.setContentsMargins(6, 10, 6, 6)
    layout.setSpacing(2)

    row = QHBoxLayout()
    row.setSpacing(4)
    row.addWidget(QLabel("File"))
    panel._lut_combo = QComboBox()
    panel._lut_combo.addItems(list_luts())
    panel._lut_combo.currentTextChanged.connect(lambda *_: panel._on_param_changed())
    row.addWidget(panel._lut_combo, 1)
    # Pick button — opens LUT picker dialog with visual previews
    pick_btn = QPushButton("…")
    pick_btn.setFixedWidth(28)
    pick_btn.setToolTip("Pick LUT from visual previews")
    pick_btn.clicked.connect(panel._show_lut_picker)
    row.addWidget(pick_btn)
    layout.addLayout(row)

    panel._intensity_slider = _LabeledSlider("Intensity", 0, 1, 1.0, 0.01, "{:.2f}")
    panel._intensity_slider.valueChanged.connect(lambda *_: panel._on_param_changed())
    panel._intensity_slider.activated.connect(panel._set_active_slider)
    panel._sliders["lut_intensity"] = panel._intensity_slider
    layout.addWidget(panel._intensity_slider)
    layout.addStretch()
    return group


# ─── Adjustments panel (5 groups in a row) ───────────────────────────────────

class AdjustmentsPanel(QWidget):
    """Exposure | Contrast | WB | Saturation | LUT — one horizontal row."""

    paramsChanged = Signal(dict)
    lutPickerRequested = Signal()  # user clicked the LUT pick button

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_COMPACT_QSS)
        self._sliders: dict[str, _LabeledSlider] = {}
        self._lut_combo: QComboBox | None = None
        self._intensity_slider: _LabeledSlider | None = None
        self._active_slider: _LabeledSlider | None = None
        self._active_scurve: SCurveEditor | None = None
        self._scurve_y: np.ndarray | None = None  # custom curve, None = use params
        self._build()
        # Connect S-Curve editor: store custom curve + emit params
        self.scurve.curveChanged.connect(self._on_scurve_changed)
        self._emit_params()

    def _on_scurve_changed(self, curve_y: np.ndarray) -> None:
        """Store the custom S-Curve and emit updated params."""
        self._scurve_y = curve_y
        self._emit_params()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(_build_slider_group("Exposure", _EXPOSURE_SPECS, self), 1)
        # Contrast group removed — replaced by interactive S-Curve editor.
        # gamma is also handled by the S-Curve (tone shaping).
        layout.addWidget(_build_slider_group("WB", _WB_SPECS, self), 1)
        layout.addWidget(_build_slider_group("Saturation", _SAT_SPECS, self), 1)
        layout.addWidget(_build_lut_group(self), 1)
        # 5th column: interactive S-Curve editor (replaces Contrast sliders)
        self.scurve = SCurveEditor()
        self.scurve.activated.connect(self._set_active_widget)
        layout.addWidget(self.scurve, 1)

    def _on_param_changed(self, *_args) -> None:
        self._emit_params()

    def _set_active_slider(self, slider: _LabeledSlider) -> None:
        """Highlight the most-recently grabbed slider in orange."""
        self._clear_active()
        self._active_slider = slider
        self._active_scurve = None
        slider.set_active(True)

    def _set_active_widget(self, widget) -> None:
        """Highlight either a slider or the S-Curve editor."""
        self._clear_active()
        if isinstance(widget, _LabeledSlider):
            self._active_slider = widget
            self._active_scurve = None
        else:
            self._active_scurve = widget
            self._active_slider = None
        widget.set_active(True)

    def _clear_active(self) -> None:
        if self._active_slider is not None:
            self._active_slider.set_active(False)
            self._active_slider = None
        if self._active_scurve is not None:
            self._active_scurve.set_active(False)
            self._active_scurve = None

    def _emit_params(self) -> None:
        params = {key: slider.value() for key, slider in self._sliders.items()}
        params["lut_path"] = self._lut_combo.currentText()
        params["lut_intensity"] = self._intensity_slider.value()
        params["scurve_custom"] = self._scurve_y  # None or 256 y-values
        self.paramsChanged.emit(params)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        params = {key: slider.value() for key, slider in self._sliders.items()}
        params["lut_path"] = self._lut_combo.currentText()
        params["lut_intensity"] = self._intensity_slider.value()
        params["scurve_custom"] = self._scurve_y
        return params

    def set_params(self, params: dict) -> None:
        for key, slider in self._sliders.items():
            if key in params:
                slider.set_value(params[key])
        lut = params.get("lut_path") or "None"
        idx = self._lut_combo.findText(lut)
        self._lut_combo.blockSignals(True)
        self._lut_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._lut_combo.blockSignals(False)
        if "lut_intensity" in params:
            self._intensity_slider.set_value(params["lut_intensity"])
        # Restore custom S-Curve if present
        scurve = params.get("scurve_custom")
        if scurve is not None:
            arr = np.asarray(scurve, dtype=np.float32)
            self._scurve_y = arr
            # Update editor control points to match the curve
            self.scurve.set_curve_from_y(arr)
        else:
            self._scurve_y = None
            self.scurve.reset()

    def reset(self) -> None:
        self.set_params(PARAM_DEFAULTS)
        self._scurve_y = None
        self.scurve.reset()
        self._emit_params()

    def refresh_luts(self) -> None:
        current = self._lut_combo.currentText()
        self._lut_combo.blockSignals(True)
        self._lut_combo.clear()
        self._lut_combo.addItems(list_luts())
        idx = self._lut_combo.findText(current)
        self._lut_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._lut_combo.blockSignals(False)

    def _show_lut_picker(self) -> None:
        """Emit signal — MainWindow opens the LUT picker with the live image."""
        self.lutPickerRequested.emit()

    def set_lut(self, lut_path: str) -> None:
        """Set the LUT combo to the given path (called after picker selection)."""
        if lut_path == "None":
            self._lut_combo.setCurrentText("None")
        else:
            idx = self._lut_combo.findText(lut_path)
            if idx >= 0:
                self._lut_combo.setCurrentIndex(idx)
            else:
                # LUT not in list — add it
                self._lut_combo.addItem(lut_path)
                self._lut_combo.setCurrentText(lut_path)