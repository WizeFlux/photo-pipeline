"""Adjustment sliders — 4 groups in a single row (compact) + separate LUT panel.

AdjustmentsPanel: Exposure, Contrast, White Balance, Saturation — horizontal.
LutPanel:         LUT file + intensity (placed in the second control row).

Both emit `paramsChanged(dict)` with their subset of params. The main window
merges them into the full 14-param dict.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider,
    QVBoxLayout, QWidget,
)

from qt_app.state import PARAM_DEFAULTS, list_luts


# ─── Compact slider ──────────────────────────────────────────────────────────

_COMPACT_QSS = """
QLabel { font-size: 10px; }
QSlider::groove:horizontal { height: 3px; background: #3a3a3a; border-radius: 1px; }
QSlider::handle:horizontal {
    background: #00d4aa; width: 10px; height: 10px;
    margin: -4px 0; border-radius: 5px;
}
QSlider::handle:horizontal:hover { background: #00f0c0; }
QSlider::sub-page:horizontal { background: #00705a; border-radius: 1px; }
QGroupBox { font-size: 11px; }
"""


class _LabeledSlider(QWidget):
    """Compact slider: name label | slider | value label, on one line."""

    valueChanged = Signal(float)

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

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(int_min, int_max)
        self.slider.setValue(int_default)

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

        self.slider.valueChanged.connect(self._on_changed)

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


# ─── Slider spec table ───────────────────────────────────────────────────────
# (key, label, min, max, default, step, fmt)

_EXPOSURE_SPECS = [
    ("ev", "EV", -3, 3, 0.0, 0.01, "{:+.2f}"),
    ("gamma", "Gamma", 0.5, 2.5, 1.0, 0.01, "{:.2f}"),
    ("highlights", "Highlights", -100, 100, 0, 1, "{:+d}"),
    ("shadows", "Shadows", -100, 100, 0, 1, "{:+d}"),
]

_CONTRAST_SPECS = [
    ("contrast_amount", "Amount", -100, 100, 0, 1, "{:+d}"),
    ("s_curve", "S-Curve", 0, 100, 0, 1, "{:d}"),
    ("black_point", "Black Point", 0, 50, 0, 1, "{:d}"),
    ("white_point", "White Point", 205, 255, 255, 1, "{:d}"),
]

_WB_SPECS = [
    ("temperature", "Temp", -100, 100, 0, 1, "{:+d}"),
    ("tint", "Tint", -100, 100, 0, 1, "{:+d}"),
]

_SAT_SPECS = [
    ("saturation", "Sat", -100, 100, 0, 1, "{:+d}"),
    ("vibrance", "Vibrance", -100, 100, 0, 1, "{:+d}"),
]


def _build_group(title: str, specs: list[tuple], parent_widget) -> QGroupBox:
    """Build a compact QGroupBox with one slider per spec."""
    group = QGroupBox(title)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(6, 10, 6, 6)
    layout.setSpacing(2)
    sliders: dict[str, _LabeledSlider] = {}
    for key, label, vmin, vmax, default, step, fmt in specs:
        slider = _LabeledSlider(label, vmin, vmax, default, step, fmt)
        slider.valueChanged.connect(parent_widget._on_slider_changed)
        sliders[key] = slider
        layout.addWidget(slider)
    layout.addStretch()
    parent_widget._sliders.update(sliders)
    return group


# ─── Adjustments panel (4 groups in a row) ───────────────────────────────────

class AdjustmentsPanel(QWidget):
    """Exposure | Contrast | White Balance | Saturation — one horizontal row."""

    paramsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_COMPACT_QSS)
        self._sliders: dict[str, _LabeledSlider] = {}
        self._build()
        self._emit_params()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(_build_group("☀️ Exposure", _EXPOSURE_SPECS, self), 1)
        layout.addWidget(_build_group("📊 Contrast", _CONTRAST_SPECS, self), 1)
        layout.addWidget(_build_group("🌡️ WB", _WB_SPECS, self), 1)
        layout.addWidget(_build_group("🎨 Saturation", _SAT_SPECS, self), 1)

    def _on_slider_changed(self, *_args) -> None:
        self._emit_params()

    def _emit_params(self) -> None:
        params = {key: slider.value() for key, slider in self._sliders.items()}
        self.paramsChanged.emit(params)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        return {key: slider.value() for key, slider in self._sliders.items()}

    def set_params(self, params: dict) -> None:
        for key, slider in self._sliders.items():
            if key in params:
                slider.set_value(params[key])

    def reset(self) -> None:
        self.set_params(PARAM_DEFAULTS)
        self._emit_params()


# ─── LUT panel (separate — lives in the second control row) ──────────────────

class LutPanel(QWidget):
    """LUT file dropdown + intensity slider."""

    paramsChanged = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_COMPACT_QSS)
        self._build()
        self._emit_params()

    def _build(self) -> None:
        group = QGroupBox("🎭 LUT")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(4)

        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(QLabel("File"))
        self._lut_combo = QComboBox()
        self._lut_combo.addItems(list_luts())
        self._lut_combo.currentTextChanged.connect(self._emit_params)
        row.addWidget(self._lut_combo, 1)
        layout.addLayout(row)

        self._intensity = _LabeledSlider("Intensity", 0, 1, 1.0, 0.01, "{:.2f}")
        self._intensity.valueChanged.connect(lambda *_: self._emit_params())
        layout.addWidget(self._intensity)
        layout.addStretch()

    def _emit_params(self, *_args) -> None:
        self.paramsChanged.emit({
            "lut_path": self._lut_combo.currentText(),
            "lut_intensity": self._intensity.value(),
        })

    def get_params(self) -> dict:
        return {
            "lut_path": self._lut_combo.currentText(),
            "lut_intensity": self._intensity.value(),
        }

    def set_params(self, params: dict) -> None:
        lut = params.get("lut_path") or "None"
        idx = self._lut_combo.findText(lut)
        self._lut_combo.blockSignals(True)
        self._lut_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._lut_combo.blockSignals(False)
        if "lut_intensity" in params:
            self._intensity.set_value(params["lut_intensity"])

    def refresh_luts(self) -> None:
        current = self._lut_combo.currentText()
        self._lut_combo.blockSignals(True)
        self._lut_combo.clear()
        self._lut_combo.addItems(list_luts())
        idx = self._lut_combo.findText(current)
        self._lut_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._lut_combo.blockSignals(False)