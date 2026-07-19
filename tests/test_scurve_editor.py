"""Tests for the interactive S-Curve editor widget."""

import numpy as np
import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from qt_app.widgets.scurve_editor import SCurveEditor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_identity_curve(app):
    """Fresh editor should produce an identity curve."""
    ed = SCurveEditor()
    curve = ed.get_curve()
    assert curve.shape == (256,)
    assert abs(curve[0] - 0) < 2
    assert abs(curve[128] - 128) < 2
    assert abs(curve[255] - 255) < 2


def test_curve_clipped_to_range(app):
    ed = SCurveEditor()
    curve = ed.get_curve()
    assert curve.min() >= 0
    assert curve.max() <= 255


def test_dragging_point_changes_curve(app):
    ed = SCurveEditor()
    before = ed.get_curve()[128]
    # Drag the middle point (index 2) up
    ed._points_y[2] = 180
    after = ed.get_curve()[128]
    assert after > before


def test_dragging_point_down_changes_curve(app):
    ed = SCurveEditor()
    before = ed.get_curve()[128]
    ed._points_y[2] = 80
    after = ed.get_curve()[128]
    assert after < before


def test_reset_returns_identity(app):
    ed = SCurveEditor()
    ed._points_y[2] = 200
    ed.reset()
    curve = ed.get_curve()
    assert abs(curve[128] - 128) < 2


def test_curve_changed_signal(app):
    ed = SCurveEditor()
    received = []
    ed.curveChanged.connect(lambda c: received.append(c))
    ed._points_y[2] = 200
    ed.curveChanged.emit(ed.get_curve())
    assert len(received) == 1
    assert received[0].shape == (256,)


def test_activated_signal(app):
    ed = SCurveEditor()
    received = []
    ed.activated.connect(lambda w: received.append(w))
    ed.activated.emit(ed)
    assert received == [ed]


def test_set_active_highlight(app):
    ed = SCurveEditor()
    ed.set_active(True)
    assert "ff8c00" in ed.styleSheet()
    ed.set_active(False)
    assert "ff8c00" not in ed.styleSheet()


def test_nearest_point_finds_close(app):
    ed = SCurveEditor()
    # Middle point is at (128, 128)
    idx = ed._nearest_point(130, 130)
    assert idx == 2


def test_nearest_point_rejects_far(app):
    ed = SCurveEditor()
    # Far away from any point
    idx = ed._nearest_point(128, 200)
    assert idx is None


def test_control_points_x_fixed(app):
    ed = SCurveEditor()
    np.testing.assert_array_equal(
        ed.POINT_X, [0, 64, 128, 192, 255]
    )