"""Tests for PlotsPanel 'None' right-selector behaviour."""

import numpy as np
import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from qt_app.state import PARAM_DEFAULTS, params_from_values
from qt_app.widgets.plots_panel import PlotsPanel, _draw_plot


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(app):
    p = PlotsPanel()
    arr = (np.random.rand(100, 150, 3) * 255).astype(np.uint8)
    p.update_all(arr, arr, None, None, params_from_values(PARAM_DEFAULTS))
    return p


def test_none_in_plot_types(app):
    from qt_app.widgets.plots_panel import PLOT_TYPES
    assert "None" in PLOT_TYPES
    assert PLOT_TYPES[0] == "None"


def test_draw_plot_none_returns_false(app):
    from matplotlib.figure import Figure
    fig = Figure()
    result = _draw_plot(fig, "None", {})
    assert result is False
    assert len(fig.axes) == 0


def test_draw_plot_none_clears_figure(app):
    from matplotlib.figure import Figure
    fig = Figure()
    # Draw something first
    arr = (np.random.rand(50, 80, 3) * 255).astype(np.uint8)
    data = {"orig": arr, "live": arr, "profile": None, "profile_name": None,
            "params": params_from_values(PARAM_DEFAULTS), "third_params": None}
    _draw_plot(fig, "Histograms", data)
    assert len(fig.axes) > 0
    # Now None should clear
    _draw_plot(fig, "None", data)
    assert len(fig.axes) == 0


def test_right_none_hides_canvas(panel):
    panel.selector_right.setCurrentText("None")
    assert panel.canvas_right.isVisibleTo(panel) is False
    assert panel._right_label.isVisibleTo(panel) is False
    assert panel.selector_right.isVisibleTo(panel) is False
    assert panel.plot_splitter.handleWidth() == 0


def test_right_restore_shows_canvas(panel):
    panel.selector_right.setCurrentText("None")
    panel.selector_right.setCurrentText("Tone Curve")
    assert panel.canvas_right.isVisibleTo(panel) is True
    assert panel._right_label.isVisibleTo(panel) is True
    assert panel.selector_right.isVisibleTo(panel) is True
    assert panel.plot_splitter.handleWidth() == 8


def test_left_none_keeps_right_visible(panel):
    """Left='None' should not hide the right canvas."""
    panel.selector_left.setCurrentText("None")
    assert panel.canvas_right.isVisibleTo(panel) is True