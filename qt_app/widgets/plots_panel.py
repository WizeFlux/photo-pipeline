"""Analysis panel — stats as text + 2 selectable plots in a row."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from qt_app.plots import (
    draw_channel_deltas, draw_histograms_row, draw_tone_curve, make_empty_figure,
)
from qt_app.state import load_profile_params, stats_rows


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


# ─── Stats as text ───────────────────────────────────────────────────────────

_STATS_QSS = """
QLabel#stats-text {
    font-family: "SF Mono", "Menlo", "Consolas", monospace;
    font-size: 10px;
    color: #c0c0c0;
    background-color: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 3px;
    padding: 6px 8px;
}
"""


def _fmt_value(v) -> str:
    try:
        f = float(v)
        if abs(f) >= 100:
            return f"{f:7.0f}"
        return f"{f:7.1f}"
    except (TypeError, ValueError):
        return str(v)


def _build_stats_text(orig: np.ndarray, live: np.ndarray | None,
                      profile: np.ndarray | None) -> str:
    """Build a monospace text block: metric | Original | Live | Profile."""
    rows = stats_rows(orig, live, profile)
    has_profile = profile is not None

    metric_w = max(len("Metric"), max(len(str(r["Metric"])) for r in rows))
    header = f"{'Metric':<{metric_w}}  {'Original':>9}  {'Live':>9}"
    if has_profile:
        header += f"  {'Profile':>9}"
    sep = "─" * len(header)

    lines = [header, sep]
    for r in rows:
        line = f"{str(r['Metric']):<{metric_w}}  {_fmt_value(r['Original'])}  {_fmt_value(r['Live'])}"
        if has_profile:
            line += f"  {_fmt_value(r['Profile'])}"
        lines.append(line)
    return "\n".join(lines)


class StatsTextWidget(QScrollArea):
    """Scrollable monospace text showing all stats, fixed height."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_STATS_QSS)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.NoFrame)
        self.setFixedHeight(150)

        self._label = QLabel("—")
        self._label.setObjectName("stats-text")
        self._label.setTextFormat(Qt.PlainText)
        self._label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._label.setWordWrap(False)
        self.setWidget(self._label)

    def update_stats(self, orig: np.ndarray, live: np.ndarray | None,
                     profile: np.ndarray | None) -> None:
        self._label.setText(_build_stats_text(orig, live, profile))

    def clear(self) -> None:
        self._label.setText("—")


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
    """Stats text + 2 selectable plots in a row."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: dict | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Stats ──
        stats_group = QGroupBox("📊 Statistics")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setContentsMargins(4, 8, 4, 4)
        self.stats_widget = StatsTextWidget()
        stats_layout.addWidget(self.stats_widget)
        layout.addWidget(stats_group)

        # ── Plot selectors + canvases ──
        plots_group = QGroupBox("📈 Plots")
        plots_layout = QVBoxLayout(plots_group)
        plots_layout.setContentsMargins(4, 8, 4, 4)
        plots_layout.setSpacing(4)

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
        plots_layout.addLayout(selector_row)

        canvases_row = QHBoxLayout()
        canvases_row.setSpacing(4)
        self.canvas_left = _PlotCanvas(min_height=140)
        self.canvas_right = _PlotCanvas(min_height=140)
        canvases_row.addWidget(self.canvas_left, 1)
        canvases_row.addWidget(self.canvas_right, 1)
        plots_layout.addLayout(canvases_row, 1)

        layout.addWidget(plots_group, 1)

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
        self.stats_widget.update_stats(orig, live, profile)
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
        self.stats_widget.clear()
        self.canvas_left.clear()
        self.canvas_right.clear()