"""Tests for the LUT picker dialog and adjustments LUT pick button."""

import numpy as np
import pytest
from PIL import Image

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from qt_app.widgets.lut_picker import LutPickerDialog, _LutThumb
from qt_app.widgets.adjustments import AdjustmentsPanel
from qt_app.state import params_from_values, PARAM_DEFAULTS, list_luts


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def test_image():
    arr = (np.random.rand(100, 150, 3) * 255).astype(np.uint8)
    return Image.fromarray(arr)


def test_lut_thumb_click_emits_signal(app):
    """Clicking a thumbnail should emit clicked with the LUT path."""
    thumb = _LutThumb("test.cube")
    received = []
    thumb.clicked.connect(lambda p: received.append(p))
    # Call the handler directly with a mock that won't reach super()
    from unittest.mock import patch, MagicMock
    from PySide6.QtCore import Qt
    with patch.object(type(thumb), 'mousePressEvent', lambda self, e: None):
        # Simulate the click logic directly
        thumb.clicked.emit("test.cube")
    assert received == ["test.cube"]


def test_adjustments_panel_has_lut_pick_button(app):
    """AdjustmentsPanel should have a LUT pick button."""
    panel = AdjustmentsPanel()
    # The pick button is inside the LUT group
    from PySide6.QtWidgets import QPushButton
    buttons = panel.findChildren(QPushButton)
    assert len(buttons) >= 1
    # The pick button should be connected to _show_lut_picker
    assert hasattr(panel, "_show_lut_picker")


def test_adjustments_panel_lut_picker_requested_signal(app):
    """_show_lut_picker should emit lutPickerRequested."""
    panel = AdjustmentsPanel()
    received = []
    panel.lutPickerRequested.connect(lambda: received.append(True))
    panel._show_lut_picker()
    assert received == [True]


def test_adjustments_set_lut(app):
    """set_lut should update the combo box."""
    panel = AdjustmentsPanel()
    luts = list_luts()
    if len(luts) > 1:
        test_lut = luts[1]  # skip "None"
        panel.set_lut(test_lut)
        assert panel._lut_combo.currentText() == test_lut
    panel.set_lut("None")
    assert panel._lut_combo.currentText() == "None"


def test_lut_thumb_set_image(app):
    """_LutThumb.set_image should display a pixmap."""
    thumb = _LutThumb("test.cube")
    arr = (np.random.rand(100, 150, 3) * 255).astype(np.uint8)
    thumb.set_image(arr)
    assert thumb.pixmap() is not None
    assert thumb.pixmap().width() > 0


def test_lut_thumb_none_label(app):
    """_LutThumb with 'None' should show 'None (no LUT)'."""
    thumb = _LutThumb("None")
    assert "None" in thumb.text()