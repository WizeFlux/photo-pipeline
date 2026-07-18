"""Panel hosting the three analysis plots + stats table.

Embeds matplotlib canvases via FigureCanvasQTAgg and a QTableWidget for
the statistics comparison.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import (
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from qt_app.plots import channel_deltas, histograms_row, tone_curve
from qt_app.state import curve_from_params, load_profile_params, stats_rows


class _PlotCanvas(QWidget):
    """A titled matplotlib canvas that can swap its figure."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = QLabel(title)
        label.setObjectName("section-title")
        layout.addWidget(label)
        self.canvas = FigureCanvasQTAgg()
        layout.addWidget(self.canvas)

    def update_figure(self, fig) -> None:
        self.canvas.figure = fig
        self.canvas.draw()

    def clear(self) -> None:
        self.canvas.figure.clear()
        self.canvas.draw()


class PlotsPanel(QWidget):
    """Stats table + 3 plot canvases stacked vertically."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # ── Stats table ──
        stats_group = QGroupBox("📊 Statistics")
        stats_layout = QVBoxLayout(stats_group)
        self.stats_table = QTableWidget(0, 4)
        self.stats_table.setHorizontalHeaderLabels(
            ["Metric", "Original", "Live", "Profile"]
        )
        header = self.stats_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 4):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.stats_table.verticalHeader().setVisible(False)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        stats_layout.addWidget(self.stats_table)
        layout.addWidget(stats_group)

        # ── Plots ──
        self.hist_canvas = _PlotCanvas("📈 Histograms")
        layout.addWidget(self.hist_canvas)

        self.deltas_canvas = _PlotCanvas("📊 Channel Deltas")
        layout.addWidget(self.deltas_canvas)

        self.curve_canvas = _PlotCanvas("📈 Tone Curve")
        layout.addWidget(self.curve_canvas)

        layout.addStretch()

    def update_all(
        self,
        orig: np.ndarray | None,
        live: np.ndarray | None,
        profile: np.ndarray | None,
        profile_name: str | None,
        params: dict,
    ) -> None:
        """Refresh stats table and all three plots."""
        if orig is None:
            self._clear_all()
            return

        # Stats table
        rows = stats_rows(orig, live, profile)
        has_profile = profile is not None
        self.stats_table.setColumnCount(4 if has_profile else 3)
        self.stats_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.stats_table.setItem(r, 0, QTableWidgetItem(str(row["Metric"])))
            self.stats_table.setItem(r, 1, QTableWidgetItem(str(row["Original"])))
            self.stats_table.setItem(r, 2, QTableWidgetItem(str(row["Live"])))
            if has_profile:
                self.stats_table.setItem(r, 3, QTableWidgetItem(str(row["Profile"])))

        # Plots
        self.hist_canvas.update_figure(
            histograms_row(orig, live, profile, profile_name)
        )
        self.deltas_canvas.update_figure(
            channel_deltas(orig, live, profile, profile_name)
        )

        third_params = None
        if profile_name and profile_name != "None":
            third_params = load_profile_params(profile_name)
        self.curve_canvas.update_figure(
            tone_curve(params, third_params, profile_name)
        )

    def _clear_all(self) -> None:
        self.stats_table.setRowCount(0)
        self.hist_canvas.clear()
        self.deltas_canvas.clear()
        self.curve_canvas.clear()