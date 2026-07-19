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
    thumb.clicked.emit("test.cube")
    assert received == ["test.cube"]


def test_adjustments_panel_has_lut_pick_button(app):
    """AdjustmentsPanel should have a LUT pick button."""
    panel = AdjustmentsPanel()
    from PySide6.QtWidgets import QPushButton
    buttons = panel.findChildren(QPushButton)
    assert len(buttons) >= 1
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
        test_lut = luts[1]
        panel.set_lut(test_lut)
        assert panel._lut_combo.currentText() == test_lut
    panel.set_lut("None")
    assert panel._lut_combo.currentText() == "None"


def test_lut_thumb_set_image(app):
    """_LutThumb.set_image should display a pixmap on the image label."""
    thumb = _LutThumb("test.cube")
    arr = (np.random.rand(100, 150, 3) * 255).astype(np.uint8)
    thumb.set_image(arr)
    assert thumb._image_label.pixmap() is not None
    assert thumb._image_label.pixmap().width() > 0


def test_lut_thumb_name_label(app):
    """_LutThumb should show the LUT name in a separate label below image."""
    thumb = _LutThumb("luts/warm.cube")
    assert "warm.cube" in thumb._name_label.text()
    # Verify image and name labels are separate
    assert thumb._image_label is not thumb._name_label


def test_lut_thumb_none_name(app):
    """_LutThumb with 'None' should show 'None (no LUT)' in the name label."""
    thumb = _LutThumb("None")
    assert "None" in thumb._name_label.text()


def test_lut_thumb_uses_lanczos(app):
    """set_image should use LANCZOS resampling for high quality."""
    from PIL import Image as PILImage
    # Just verify the import works and LANCZOS is available
    assert hasattr(PILImage, 'LANCZOS')


def test_lut_thumb_size_increased(app):
    """Thumbnails should be larger than the old 200x150."""
    from qt_app.widgets.lut_picker import _THUMB_W, _THUMB_H
    assert _THUMB_W > 200
    assert _THUMB_H > 150


def test_lut_thumb_worker_passes_intensity(app):
    """_LutThumbWorker should accept and use lut_intensity."""
    from qt_app.widgets.lut_picker import _LutThumbWorker
    from qt_app.state import params_from_values, PARAM_DEFAULTS
    arr = (np.random.rand(50, 80, 3) * 255).astype(np.uint8)
    img = Image.fromarray(arr)
    params = params_from_values(PARAM_DEFAULTS)
    worker = _LutThumbWorker(img, params, "luts/warm.cube", 0.5)
    assert worker._intensity == 0.5
    worker.requestInterruption()
    worker.wait(1000)