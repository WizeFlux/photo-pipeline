"""Adjustment sliders panel — exposure, contrast, white balance, saturation, LUT.

Emits `paramsChanged(dict)` whenever any slider changes. The dict contains
all 14 processing parameters in canonical order.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider,
    QVBoxLayout, QWidget,
)

from qt_app.state import PARAM_DEFAULTS, list_luts


class _LabeledSlider(QWidget):
    """A slider with a name label on the left and a value label on the right."""

    valueChanged = Signal(float)

    def __init__(self, name: str, vmin, vmax, default, step: float = 1.0,
                 fmt: str = "{:.2f}", parent=None):
        super().__init__(parent)
        self._step = step
        self._fmt = fmt
        self._vmin = float(vmin)
        self._vmax = float(vmax)
        self._is_float = isinstance(default, float) or step < 1.0

        # Scale to integer slider range
        self._scale = 1.0 / step if self._is_float else 1.0
        int_min = int(vmin * self._scale)
        int_max = int(vmax * self._scale)
        int_default = int(round(float(default) * self._scale))

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(int_min, int_max)
        self.slider.setValue(int_default)

        self.name_label = QLabel(name)
        self.name_label.setMinimumWidth(100)
        self.value_label = QLabel(self._format(default))
        self.value_label.setMinimumWidth(48)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setObjectName("value-label")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
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


class AdjustmentsPanel(QWidget):
    """All processing sliders grouped into semantic sections.

    Signals:
        paramsChanged(dict): emitted with all 14 params on any change.
    """

    paramsChanged = Signal(dict)

    # Slider specs in canonical param order: (key, label, min, max, default, step, fmt)
    SPECS: list[tuple] = [
        # Exposure
        ("ev", "EV", -3, 3, 0.0, 0.01, "{:+.2f}"),
        ("gamma", "Gamma", 0.5, 2.5, 1.0, 0.01, "{:.2f}"),
        ("highlights", "Highlights", -100, 100, 0, 1, "{:+d}"),
        ("shadows", "Shadows", -100, 100, 0, 1, "{:+d}"),
        # Contrast
        ("contrast_amount", "Amount", -100, 100, 0, 1, "{:+d}"),
        ("s_curve", "S-Curve", 0, 100, 0, 1, "{:d}"),
        ("black_point", "Black Point", 0, 50, 0, 1, "{:d}"),
        ("white_point", "White Point", 205, 255, 255, 1, "{:d}"),
        # White balance
        ("temperature", "Temperature", -100, 100, 0, 1, "{:+d}"),
        ("tint", "Tint", -100, 100, 0, 1, "{:+d}"),
        # Saturation
        ("saturation", "Saturation", -100, 100, 0, 1, "{:+d}"),
        ("vibrance", "Vibrance", -100, 100, 0, 1, "{:+d}"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sliders: dict[str, _LabeledSlider] = {}
        self._lut_combo: QComboBox = QComboBox()
        self._lut_intensity: _LabeledSlider | None = None
        self._build()
        self._emit_params()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Exposure ──
        exp_group = QGroupBox("☀️ Exposure")
        exp_layout = QVBoxLayout(exp_group)
        for key, label, vmin, vmax, default, step, fmt in self.SPECS[:4]:
            slider = _LabeledSlider(label, vmin, vmax, default, step, fmt)
            slider.valueChanged.connect(self._on_slider_changed)
            self._sliders[key] = slider
            exp_layout.addWidget(slider)
        exp_layout.addStretch()
        layout.addWidget(exp_group)

        # ── Contrast ──
        con_group = QGroupBox("📊 Contrast")
        con_layout = QVBoxLayout(con_group)
        for key, label, vmin, vmax, default, step, fmt in self.SPECS[4:8]:
            slider = _LabeledSlider(label, vmin, vmax, default, step, fmt)
            slider.valueChanged.connect(self._on_slider_changed)
            self._sliders[key] = slider
            con_layout.addWidget(slider)
        con_layout.addStretch()
        layout.addWidget(con_group)

        # ── White balance + Saturation ──
        wb_group = QGroupBox("🌡️ White Balance")
        wb_layout = QVBoxLayout(wb_group)
        for key, label, vmin, vmax, default, step, fmt in self.SPECS[8:10]:
            slider = _LabeledSlider(label, vmin, vmax, default, step, fmt)
            slider.valueChanged.connect(self._on_slider_changed)
            self._sliders[key] = slider
            wb_layout.addWidget(slider)
        wb_layout.addStretch()
        layout.addWidget(wb_group)

        sat_group = QGroupBox("🎨 Saturation")
        sat_layout = QVBoxLayout(sat_group)
        for key, label, vmin, vmax, default, step, fmt in self.SPECS[10:12]:
            slider = _LabeledSlider(label, vmin, vmax, default, step, fmt)
            slider.valueChanged.connect(self._on_slider_changed)
            self._sliders[key] = slider
            sat_layout.addWidget(slider)
        sat_layout.addStretch()
        layout.addWidget(sat_group)

        # ── LUT ──
        lut_group = QGroupBox("🎭 LUT")
        lut_layout = QVBoxLayout(lut_group)
        luts = list_luts()
        self._lut_combo = QComboBox()
        self._lut_combo.addItems(luts)
        self._lut_combo.currentTextChanged.connect(self._on_slider_changed)
        lut_layout.addWidget(QLabel("LUT File"))
        lut_layout.addWidget(self._lut_combo)
        self._lut_intensity = _LabeledSlider("Intensity", 0, 1, 1.0, 0.01, "{:.2f}")
        self._lut_intensity.valueChanged.connect(self._on_slider_changed)
        lut_layout.addWidget(self._lut_intensity)
        lut_layout.addStretch()
        layout.addWidget(lut_group)

        layout.addStretch()

    def _on_slider_changed(self, *_args) -> None:
        self._emit_params()

    def _emit_params(self) -> None:
        params = {}
        for key, slider in self._sliders.items():
            params[key] = slider.value()
        params["lut_path"] = self._lut_combo.currentText()
        params["lut_intensity"] = self._lut_intensity.value()
        self.paramsChanged.emit(params)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_params(self) -> dict:
        params = {}
        for key, slider in self._sliders.items():
            params[key] = slider.value()
        params["lut_path"] = self._lut_combo.currentText()
        params["lut_intensity"] = self._lut_intensity.value()
        return params

    def set_params(self, params: dict) -> None:
        """Apply a params dict to the sliders (no signal emitted)."""
        for key, slider in self._sliders.items():
            if key in params:
                slider.set_value(params[key])
        lut = params.get("lut_path") or "None"
        idx = self._lut_combo.findText(lut)
        self._lut_combo.blockSignals(True)
        self._lut_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._lut_combo.blockSignals(False)
        if "lut_intensity" in params:
            self._lut_intensity.set_value(params["lut_intensity"])

    def reset(self) -> None:
        self.set_params(PARAM_DEFAULTS)
        self._emit_params()

    def refresh_luts(self) -> None:
        current = self._lut_combo.currentText()
        self._lut_combo.blockSignals(True)
        self._lut_combo.clear()
        self._lut_combo.addItems(list_luts())
        idx = self._lut_combo.findText(current)
        self._lut_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._lut_combo.blockSignals(False)