"""Tests for the interactive S-Curve editor widget."""

import numpy as np
import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
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


def test_set_active_is_noop(app):
    """set_active is a no-op (no orange border per user request)."""
    ed = SCurveEditor()
    ed.set_active(True)
    assert ed.styleSheet() == ""
    ed.set_active(False)
    assert ed.styleSheet() == ""


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


def test_no_title_label(app):
    """Editor should not have a title label (removed per user request)."""
    from PySide6.QtWidgets import QLabel
    ed = SCurveEditor()
    labels = ed.findChildren(QLabel)
    assert len(labels) == 0, f"Found {len(labels)} labels, expected 0"


def test_canvas_min_height_compact(app):
    """Canvas should be compact (min height ≤ 80)."""
    ed = SCurveEditor()
    assert ed._canvas.minimumHeight() <= 80


def test_layout_margins_compact(app):
    """Layout margins should be zero (minimal padding)."""
    ed = SCurveEditor()
    layout = ed.layout()
    margins = layout.contentsMargins()
    assert margins.left() == 0 and margins.top() == 0
    assert margins.right() == 0 and margins.bottom() == 0


def test_figure_subplots_adjust_tight(app):
    """Figure subplots_adjust should have minimal top/bottom margins."""
    ed = SCurveEditor()
    fig = ed._fig
    # After _redraw, subplots_adjust was called with tight margins
    assert fig.subplotpars.top >= 0.95
    assert fig.subplotpars.bottom <= 0.05


def test_wheel_moves_point_up(app):
    """Scroll up should increase the active point's y value."""
    ed = SCurveEditor()
    ed._active_idx = 2  # middle point
    before = ed._points_y[2]
    pos = QPointF(ed._canvas.rect().center())
    global_pos = QPointF(ed._canvas.mapToGlobal(ed._canvas.rect().center()))
    we = QWheelEvent(pos, global_pos, QPoint(0, 0), QPoint(0, 120),
                     Qt.NoButton, Qt.NoModifier, Qt.ScrollBegin, False)
    ed.wheelEvent(we)
    assert ed._points_y[2] > before


def test_wheel_moves_point_down(app):
    """Scroll down should decrease the active point's y value."""
    ed = SCurveEditor()
    ed._active_idx = 2
    ed._points_y[2] = 150  # start above identity
    before = ed._points_y[2]
    pos = QPointF(ed._canvas.rect().center())
    global_pos = QPointF(ed._canvas.mapToGlobal(ed._canvas.rect().center()))
    we = QWheelEvent(pos, global_pos, QPoint(0, 0), QPoint(0, -120),
                     Qt.NoButton, Qt.NoModifier, Qt.ScrollBegin, False)
    ed.wheelEvent(we)
    assert ed._points_y[2] < before


def test_wheel_clamps_to_range(app):
    """Wheel should not move points outside [0, 255]."""
    ed = SCurveEditor()
    ed._active_idx = 0
    ed._points_y[0] = 0
    pos = QPointF(ed._canvas.rect().center())
    global_pos = QPointF(ed._canvas.mapToGlobal(ed._canvas.rect().center()))
    we = QWheelEvent(pos, global_pos, QPoint(0, 0), QPoint(0, -120 * 100),
                     Qt.NoButton, Qt.NoModifier, Qt.ScrollBegin, False)
    ed.wheelEvent(we)
    assert ed._points_y[0] == 0


def test_wheel_activates_point(app):
    """Wheel over a point should activate it (emit activated signal)."""
    ed = SCurveEditor()
    received = []
    ed.activated.connect(lambda w: received.append(w))
    pos = QPointF(ed._canvas.rect().center())
    global_pos = QPointF(ed._canvas.mapToGlobal(ed._canvas.rect().center()))
    we = QWheelEvent(pos, global_pos, QPoint(0, 0), QPoint(0, 120),
                     Qt.NoButton, Qt.NoModifier, Qt.ScrollBegin, False)
    ed.wheelEvent(we)
    assert len(received) >= 1
    assert ed._active_idx is not None


def test_inactive_point_color_is_teal():
    """Inactive control point color constant should be teal."""
    from qt_app.widgets.scurve_editor import _POINT_COLOR, _POINT_EDGE
    assert _POINT_COLOR == "#6fbfa8"  # teal


def test_active_point_color_is_orange():
    """Active control point color constant should be orange."""
    from qt_app.widgets.scurve_editor import _POINT_ACTIVE
    assert _POINT_ACTIVE == "#ff8c00"  # orange