"""Analysis panel — 2 selectable plots in a row (no stats).

Right selector includes 'None' — when selected, the right canvas is hidden
and the left canvas expands to full width (no splitter handle).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from qt_app.plots import (
    draw_channel_deltas, draw_clipping_map, draw_histograms_row,
    draw_rgb_waveform, draw_saturation_hist, draw_tone_curve,
    draw_vectorscope, draw_zone_system, make_empty_figure,
)
from qt_app.state import load_profile_params


# Throttle: plots only re-render after the user stops changing sliders for
# this many ms. Heavy plots (RGB Waveform, Vectorscope) take ~900ms to
# render on the UI thread, so rendering on every slider tick would freeze
# the UI. The timer is restarted on every update_all() call, so only the
# final state is rendered.
_PLOTS_THROTTLE_MS = 350


PLOT_TYPES = [
    "None",
    "Histograms",
    "Channel Deltas",
    "Tone Curve",
    "RGB Waveform",
    "Vectorscope",
    "Saturation Dist",
    "Zone System",
    "Clipping Map",
]


def _draw_plot(fig: Figure, plot_type: str, data: dict) -> bool:
    """Render `plot_type` onto `fig`. Returns True if drawn, False if 'None'."""
    if plot_type == "None":
        fig.clear()
        return False
    if plot_type == "Histograms":
        draw_histograms_row(
            fig, data["orig"], data["live"], data["profile"], data["profile_name"]
        )
    elif plot_type == "Channel Deltas":
        draw_channel_deltas(
            fig, data["orig"], data["live"], data["profile"], data["profile_name"]
        )
    elif plot_type == "Tone Curve":
        draw_tone_curve(
            fig, data["params"], data["third_params"], data["profile_name"]
        )
    elif plot_type == "RGB Waveform":
        draw_rgb_waveform(
            fig, data["orig"], data["live"], data["profile"], data["profile_name"]
        )
    elif plot_type == "Vectorscope":
        draw_vectorscope(
            fig, data["orig"], data["live"], data["profile"], data["profile_name"]
        )
    elif plot_type == "Saturation Dist":
        draw_saturation_hist(
            fig, data["orig"], data["live"], data["profile"], data["profile_name"]
        )
    elif plot_type == "Zone System":
        draw_zone_system(
            fig, data["orig"], data["live"], data["profile"], data["profile_name"]
        )
    elif plot_type == "Clipping Map":
        draw_clipping_map(
            fig, data["orig"], data["live"], data["profile"], data["profile_name"]
        )
    return True


# ─── Plot canvas ─────────────────────────────────────────────────────────────

class _PlotCanvas(QWidget):
    def __init__(self, min_height: int = 120, parent=None):
        super().__init__(parent)
        self._figure = make_empty_figure()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.canvas = FigureCanvasQTAgg(self._figure)
        self.canvas.setMinimumHeight(min_height)
        layout.addWidget(self.canvas)

    @property
    def figure(self) -> Figure:
        return self._figure

    def clear(self) -> None:
        self._figure.clear()
        self.canvas.draw()


# ─── Panel ───────────────────────────────────────────────────────────────────

class PlotsPanel(QWidget):
    """Left + Right selectable plots. Right='None' → left spans full width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict | None = None
        # Coalescing throttle timer — only the latest data gets rendered.
        # Restarted on every update_all(); fires _redraw_plots once after
        # the user stops dragging for _PLOTS_THROTTLE_MS.
        from PySide6.QtCore import QTimer
        self._plots_timer = QTimer(self)
        self._plots_timer.setSingleShot(True)
        self._plots_timer.timeout.connect(self._redraw_plots)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Selector row
        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        selector_row.addWidget(QLabel("Left:"))
        self.selector_left = QComboBox()
        self.selector_left.addItems(PLOT_TYPES)
        self.selector_left.setCurrentText("Histograms")
        self.selector_left.currentTextChanged.connect(lambda _: self._on_selection_changed())
        selector_row.addWidget(self.selector_left, 1)

        self._right_label = QLabel("Right:")
        selector_row.addSpacing(12)
        selector_row.addWidget(self._right_label)
        self.selector_right = QComboBox()
        self.selector_right.addItems(PLOT_TYPES)
        self.selector_right.setCurrentText("Tone Curve")
        self.selector_right.currentTextChanged.connect(lambda _: self._on_selection_changed())
        selector_row.addWidget(self.selector_right, 1)
        layout.addLayout(selector_row)

        # Horizontal splitter — drag to resize left/right plots
        self.plot_splitter = QSplitter(Qt.Horizontal)
        self.plot_splitter.setHandleWidth(8)
        self.canvas_left = _PlotCanvas(min_height=140)
        self.canvas_right = _PlotCanvas(min_height=140)
        self.plot_splitter.addWidget(self.canvas_left)
        self.plot_splitter.addWidget(self.canvas_right)
        self.plot_splitter.setStretchFactor(0, 1)
        self.plot_splitter.setStretchFactor(1, 1)
        self.plot_splitter.setSizes([400, 400])
        layout.addWidget(self.plot_splitter, 1)

    def _on_selection_changed(self) -> None:
        """Show/hide right canvas depending on 'None' selection.

        The right selector stays visible so the user can switch back from
        'None' to a real plot. Only the canvas and its label are hidden.
        """
        right_is_none = self.selector_right.currentText() == "None"
        if right_is_none:
            self.canvas_right.hide()
            self._right_label.hide()
            self.plot_splitter.setHandleWidth(0)
        else:
            self.canvas_right.show()
            self._right_label.show()
            self.plot_splitter.setHandleWidth(8)
        self._redraw_plots()

    def _redraw_plots(self) -> None:
        if self._data is None:
            return
        # Only draw left — right is drawn separately to avoid blocking.
        _draw_plot(self.canvas_left.figure, self.selector_left.currentText(), self._data)
        self.canvas_left.canvas.draw_idle()
        if self.selector_right.currentText() != "None":
            _draw_plot(self.canvas_right.figure, self.selector_right.currentText(), self._data)
            self.canvas_right.canvas.draw_idle()
        else:
            self.canvas_right.clear()

    def update_all(
        self,
        orig: np.ndarray | None,
        live: np.ndarray | None,
        profile: np.ndarray | None,
        profile_name: str | None,
        params: dict,
    ) -> None:
        if orig is None:
            self._clear_all()
            return
        third_params = None
        if profile_name and profile_name != "None":
            third_params = load_profile_params(profile_name)
        self._data = {
            "orig": orig, "live": live, "profile": profile,
            "profile_name": profile_name, "params": params,
            "third_params": third_params,
        }
        # Coalesce: restart the throttle timer on every update. Only the
        # latest data gets rendered, after the user stops changing sliders
        # for _PLOTS_THROTTLE_MS. This prevents the UI from blocking on
        # ~900ms matplotlib renders during rapid slider dragging.
        self._plots_timer.start(_PLOTS_THROTTLE_MS)

    def _clear_all(self) -> None:
        self._data = None
        self._plots_timer.stop()
        self.canvas_left.clear()
        self.canvas_right.clear()