"""Tests for slider wheel events and active-highlight behavior.

Wheel step scheme (updated):
  • Normal scroll     — 1 internal unit (finest)
  • Ctrl + scroll     — 1% of range
  • Shift + scroll    — 2% of range
"""

import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from qt_app.widgets.adjustments import _LabeledSlider, _Slider


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _wheel(slider, delta=120, modifiers=Qt.NoModifier):
    """Send a QWheelEvent directly to the slider."""
    pos = QPointF(slider.rect().center())
    global_pos = QPointF(slider.mapToGlobal(slider.rect().center()))
    pixel = QPoint(0, 0)
    angle = QPoint(0, delta)
    we = QWheelEvent(pos, global_pos, pixel, angle, Qt.NoButton, modifiers,
                     Qt.ScrollBegin, False)
    slider.wheelEvent(we)


def test_slider_is_custom_subclass(app):
    s = _LabeledSlider("X", 0, 100, 50, 1, "{:d}")
    assert isinstance(s.slider, _Slider)


def test_wheel_activates_highlight(app):
    s = _LabeledSlider("X", 0, 100, 50, 1, "{:d}")
    activated = []
    s.activated.connect(lambda sl: activated.append(sl))
    _wheel(s.slider)
    assert activated == [s]


def test_wheel_up_increases_value(app):
    s = _LabeledSlider("X", 0, 100, 50, 1, "{:d}")
    _wheel(s.slider, delta=120)
    assert s.value() > 50


def test_wheel_down_decreases_value(app):
    s = _LabeledSlider("X", 0, 100, 50, 1, "{:d}")
    _wheel(s.slider, delta=-120)
    assert s.value() < 50


def test_normal_wheel_is_finest(app):
    """Normal wheel moves 1 internal unit (finest possible)."""
    s = _LabeledSlider("X", -100, 100, 0, 1, "{:d}")
    _wheel(s.slider)
    assert s.value() == 1


def test_ctrl_wheel_is_range_percent(app):
    """Ctrl+wheel moves 1% of range per notch."""
    # Range 200 → 200//100 = 2
    s = _LabeledSlider("X", -100, 100, 0, 1, "{:d}")
    _wheel(s.slider, modifiers=Qt.ControlModifier)
    assert s.value() == 2


def test_shift_wheel_is_two_percent(app):
    """Shift+wheel moves 2% of range per notch."""
    # Range 200 → 200//50 = 4
    s = _LabeledSlider("X", -100, 100, 0, 1, "{:d}")
    _wheel(s.slider, modifiers=Qt.ShiftModifier)
    assert s.value() == 4


def test_float_slider_normal_wheel_is_finest(app):
    """EV slider (step=0.01) → normal wheel moves 0.01 (finest)."""
    s = _LabeledSlider("EV", -3, 3, 0.0, 0.01, "{:.2f}")
    _wheel(s.slider)
    assert abs(s.value() - 0.01) < 1e-9


def test_float_slider_ctrl_wheel(app):
    """EV range=6, internal=600 → Ctrl = 600//100 = 6 → 0.06."""
    s = _LabeledSlider("EV", -3, 3, 0.0, 0.01, "{:.2f}")
    _wheel(s.slider, modifiers=Qt.ControlModifier)
    assert abs(s.value() - 0.06) < 1e-9


def test_float_slider_shift_wheel(app):
    """EV range=600 internal → Shift = 600//50 = 12 → 0.12."""
    s = _LabeledSlider("EV", -3, 3, 0.0, 0.01, "{:.2f}")
    _wheel(s.slider, modifiers=Qt.ShiftModifier)
    assert abs(s.value() - 0.12) < 1e-9


def test_wheel_does_not_exceed_range(app):
    s = _LabeledSlider("X", 0, 10, 9, 1, "{:d}")
    _wheel(s.slider, delta=120 * 1000)  # huge positive
    assert s.value() == 10
    s2 = _LabeledSlider("X", 0, 10, 1, 1, "{:d}")
    _wheel(s2.slider, delta=-120 * 1000)  # huge negative
    assert s2.value() == 0


def test_panel_active_slider_switches_on_wheel(app):
    """Wheeling slider B after slider A should switch highlight to B."""
    from qt_app.widgets.adjustments import AdjustmentsPanel
    panel = AdjustmentsPanel()
    ev = panel._sliders["ev"]
    sat = panel._sliders["saturation"]

    _wheel(ev.slider)
    assert panel._active_slider is ev
    assert ev.slider.styleSheet() != ""  # orange
    assert sat.slider.styleSheet() == ""  # not highlighted

    _wheel(sat.slider)
    assert panel._active_slider is sat
    assert sat.slider.styleSheet() != ""  # orange
    assert ev.slider.styleSheet() == ""  # de-highlighted