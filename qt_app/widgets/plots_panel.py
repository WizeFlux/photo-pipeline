"""Analysis panel — transposed stats table + scrollable resizable plots.

Layout:
  ┌──────────────────────────────────────────────────────────┐
  │ Stats (transposed: rows=images, cols=metrics, small font)│
  ├──────────────────────────────────────────────────────────┤
  │ QSplitter (vertical, resizable)                          │
  │   ├─ Histograms   (matplotlib canvas)                    │
  │   ├─ Channel Deltas                                       │
  │   └─ Tone Curve                                           │
  └──────────────────────────────────────────────────────────┘

The plots area is wrapped in a QScrollArea and split with a QSplitter so
each plot's height can be dragged, and the whole block scrolls vertically.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QScrollArea, QSizePolicy,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from qt_app.plots import (
    draw_channel_deltas, draw_histograms_row, draw_tone_curve, make_empty_figure,
)
from qt_app.state import load_profile_params, stats_rows


# ─── Stats table (transposed) ────────────────────────────────────────────────

# Metric display order — one column per metric.
_METRIC_ORDER = [
    "Brightness", "B_median", "B_std", "B_min", "B_max", "Range",
    "R_mean", "G_mean", "B_mean",
    "R_std", "G_std", "B_std",
    "R/B", "R/G", "G/B",
    "Saturation", "SNR",
    "Shadows%", "Midtones%", "Highlights%",
    "Clip_S%", "Clip_H%",
]

_STATS_QSS = """
QTableWidget {
    font-size: 9px;
    background-color: #1a1a1a;
}
QTableWidget::item { padding: 1px 4px; }
QHeaderView::section {
    background-color: #2a2a2a;
    color: #00d4aa;
    font-size: 9px;
    padding: 2px 4px;
    border: 1px solid #333;
}
"""


class StatsTable(QTableWidget):
    """Transposed stats: rows = images, columns = metrics, tiny font."""

    def __init__(self, parent=None):
        super().__init__(0, len(_METRIC_ORDER), parent)
        self.setStyleSheet(_STATS_QSS)
        self.setHorizontalHeaderLabels(_METRIC_ORDER)
        self.verticalHeader().setVisible(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        header = self.horizontalHeader()
        header.setDefaultSectionSize(52)
        header.setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(18)
        self.verticalHeader().setStyleSheet(
            "QHeaderView::section { background:#2a2a2a; color:#00d4aa;"
            "  font-size:9px; padding:1px 4px; border:1px solid #333; }"
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(18 * 3 + 28)  # 3 image rows + header

    def update_stats(self, orig: np.ndarray, live: np.ndarray | None,
                     profile: np.ndarray | None) -> None:
        rows_data = stats_rows(orig, live, profile)
        # rows_data is a list of {Metric, Original, Live, Profile?}
        by_metric = {r["Metric"]: r for r in rows_data}
        has_profile = profile is not None

        self.setRowCount(3 if has_profile else 2)
        self.setVerticalHeaderLabels(
            ["Original", "Live", "Profile"] if has_profile else ["Original", "Live"]
        )
        for col, metric in enumerate(_METRIC_ORDER):
            row = by_metric.get(metric)
            if row is None:
                continue
            self.setItem(0, col, QTableWidgetItem(self._fmt(row["Original"])))
            self.setItem(1, col, QTableWidgetItem(self._fmt(row["Live"])))
            if has_profile:
                self.setItem(2, col, QTableWidgetItem(self._fmt(row["Profile"])))

    @staticmethod
    def _fmt(v) -> str:
        try:
            f = float(v)
            if abs(f) >= 100:
                return f"{f:.0f}"
            return f"{f:.1f}"
        except (TypeError, ValueError):
            return str(v)


# ─── Plot canvas ─────────────────────────────────────────────────────────────

class _PlotCanvas(QWidget):
    """A matplotlib canvas with a persistent Figure, resizable height."""

    def __init__(self, title: str, min_height: int = 120, parent=None):
        super().__init__(parent)
        self._figure = make_empty_figure()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = QLabel(title)
        label.setObjectName("section-title")
        label.setStyleSheet("font-size: 11px;")
        layout.addWidget(label)
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
    """Stats table on top + scrollable/resizable plots below."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Stats (transposed, compact) ──
        stats_group = QGroupBox("📊 Statistics")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.setContentsMargins(4, 8, 4, 4)
        self.stats_table = StatsTable()
        stats_layout.addWidget(self.stats_table)
        layout.addWidget(stats_group)

        # ── Plots: vertical splitter inside a scroll area ──
        plots_label = QLabel("📈 Plots  (drag dividers to resize · scroll if needed)")
        plots_label.setObjectName("value-label")
        layout.addWidget(plots_label)

        self.hist_canvas = _PlotCanvas("Histograms", min_height=140)
        self.deltas_canvas = _PlotCanvas("Channel Deltas", min_height=140)
        self.curve_canvas = _PlotCanvas("Tone Curve", min_height=140)

        # Splitter lets the user drag each plot's height
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.addWidget(self.hist_canvas)
        self.splitter.addWidget(self.deltas_canvas)
        self.splitter.addWidget(self.curve_canvas)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setHandleWidth(6)

        # Scroll area wraps the splitter — scroll if total height exceeds space
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.splitter)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        layout.addWidget(self.scroll, 1)

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

        # Stats
        self.stats_table.update_stats(orig, live, profile)

        # Plots — draw on persistent figures
        draw_histograms_row(
            self.hist_canvas.figure, orig, live, profile, profile_name
        )
        draw_channel_deltas(
            self.deltas_canvas.figure, orig, live, profile, profile_name
        )
        third_params = None
        if profile_name and profile_name != "None":
            third_params = load_profile_params(profile_name)
        draw_tone_curve(
            self.curve_canvas.figure, params, third_params, profile_name
        )
        self.hist_canvas.canvas.draw()
        self.deltas_canvas.canvas.draw()
        self.curve_canvas.canvas.draw()

    def _clear_all(self) -> None:
        self.stats_table.setRowCount(0)
        self.hist_canvas.clear()
        self.deltas_canvas.clear()
        self.curve_canvas.clear()