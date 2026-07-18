"""Analysis panel — 2 selectable plots in a row (no stats)."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from qt_app.plots import (
    draw_channel_deltas, draw_histograms_row, draw_tone_curve, make_empty_figure,
)
from qt_app.state import load_profile_params


PLOT_TYPES = ["Histograms", "Channel Deltas", "Tone Curve"]


def _draw_plot(fig: Figure, plot_type: str, data: dict) -> None:
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
    """2 selectable plots in a row."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Selector row (no group box / title)
        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        selector_row.addWidget(QLabel("Left:"))
        self.selector_left = QComboBox()
        self.selector_left.addItems(PLOT_TYPES)
        self.selector_left.setCurrentText("Histograms")
        self.selector_left.currentTextChanged.connect(lambda _: self._redraw_plots())
        selector_row.addWidget(self.selector_left, 1)

        selector_row.addSpacing(12)
        selector_row.addWidget(QLabel("Right:"))
        self.selector_right = QComboBox()
        self.selector_right.addItems(PLOT_TYPES)
        self.selector_right.setCurrentText("Tone Curve")
        self.selector_right.currentTextChanged.connect(lambda _: self._redraw_plots())
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

    def _redraw_plots(self) -> None:
        if self._data is None:
            return
        _draw_plot(self.canvas_left.figure, self.selector_left.currentText(), self._data)
        _draw_plot(self.canvas_right.figure, self.selector_right.currentText(), self._data)
        self.canvas_left.canvas.draw()
        self.canvas_right.canvas.draw()

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
        self._redraw_plots()

    def _clear_all(self) -> None:
        self._data = None
        self.canvas_left.clear()
        self.canvas_right.clear()