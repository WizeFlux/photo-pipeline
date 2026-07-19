"""Interactive S-Curve editor widget — draggable control points.

Renders a tone curve on a matplotlib canvas with 5 draggable control points.
The user drags points up/down to shape the curve; the widget emits the
resulting curve as 256 y-values via `curveChanged`.

Used as the 6th column in the adjustments row (after LUT).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget, QLabel, QHBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


# Dark theme
_BG = "#1e1e1e"
_PANEL = "#232323"
_GRID = "#3a3a3a"
_TEXT = "#b0b0b0"
_CURVE_COLOR = "#6fbfa8"
_POINT_COLOR = "#ff8c00"
_POINT_ACTIVE = "#ffaa44"


class SCurveEditor(QWidget):
    """Interactive tone-curve editor with draggable control points.

    Control points are at x = 0, 64, 128, 192, 255 (evenly spaced).
    The curve is a Catmull-Rom spline through the points.
    Emits `curveChanged(np.ndarray)` with 256 y-values when points move.
    """

    curveChanged = Signal(np.ndarray)
    activated = Signal(object)  # emits self when user grabs a point

    # Fixed x positions of control points (evenly spaced)
    POINT_X = np.array([0, 64, 128, 192, 255], dtype=np.float64)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._points_y = self.POINT_X.copy().astype(np.float64)  # identity
        self._active_idx: int | None = None
        self._dragging = False
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(2)

        title = QLabel("S-Curve")
        title.setStyleSheet("color: #b0b0b0; font-weight: bold;")
        layout.addWidget(title)

        self._fig = Figure(figsize=(3, 3), facecolor=_BG)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(140)
        self._canvas.mpl_connect("button_press_event", self._on_press)
        self._canvas.mpl_connect("button_release_event", self._on_release)
        self._canvas.mpl_connect("motion_notify_event", self._on_motion)
        layout.addWidget(self._canvas, 1)
        self._redraw()

    def _redraw(self) -> None:
        self._fig.clear()
        self._fig.set_facecolor(_BG)
        ax = self._fig.add_subplot(111)
        ax.set_facecolor(_PANEL)
        ax.set_xlim(-5, 260)
        ax.set_ylim(-5, 260)
        # Grid
        ax.grid(True, color=_GRID, linewidth=0.5, alpha=0.6)
        # Identity dashed line
        x = np.linspace(0, 255, 256)
        ax.plot(x, x, color="#666", linewidth=0.8, linestyle="--", alpha=0.5)
        # The curve
        y = self._compute_curve()
        ax.plot(x, y, color=_CURVE_COLOR, linewidth=2.0)
        # Control points
        for i, (px, py) in enumerate(zip(self.POINT_X, self._points_y)):
            color = _POINT_ACTIVE if i == self._active_idx else _POINT_COLOR
            ax.plot(px, py, "o", color=color, markersize=7,
                    markeredgecolor="#cc7000", markeredgewidth=1.0, picker=5)
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_color(_GRID)
            sp.set_linewidth(0.5)
        self._canvas.draw_idle()

    def _compute_curve(self) -> np.ndarray:
        """Catmull-Rom spline through the 5 control points → 256 y-values."""
        xs = self.POINT_X
        ys = self._points_y
        # Catmull-Rom needs phantom points at both ends
        xs_ext = np.concatenate([[-xs[1] + xs[0] * 2], xs, [xs[-1] * 2 - xs[-2]]])
        ys_ext = np.concatenate([[ys[0] * 2 - ys[1]], ys, [ys[-1] * 2 - ys[-2]]])
        x_out = np.linspace(0, 255, 256)
        y_out = np.zeros(256)
        for i in range(len(xs_ext) - 3):
            p0, p1, p2, p3 = ys_ext[i], ys_ext[i+1], ys_ext[i+2], ys_ext[i+3]
            x0, x1, x2, x3 = xs_ext[i], xs_ext[i+1], xs_ext[i+2], xs_ext[i+3]
            # For each output x in [x1, x2]
            mask = (x_out >= x1 - 0.5) & (x_out <= x2 + 0.5)
            if not mask.any():
                continue
            t = (x_out[mask] - x1) / max(x2 - x1, 1e-6)
            # Catmull-Rom interpolation
            y_out[mask] = (
                0.5 * ((2 * p1) +
                       (-p0 + p2) * t +
                       (2 * p0 - 5 * p1 + 4 * p2 - p3) * t**2 +
                       (-p0 + 3 * p1 - 3 * p2 + p3) * t**3)
            )
        return np.clip(y_out, 0, 255)

    def _nearest_point(self, x: float, y: float) -> int | None:
        """Find the nearest control point within a threshold."""
        dists = np.sqrt((self.POINT_X - x)**2 + (self._points_y - y)**2)
        idx = int(np.argmin(dists))
        if dists[idx] < 25:  # pixel threshold (in data coords)
            return idx
        return None

    def _on_press(self, event) -> None:
        if event.xdata is None or event.ydata is None:
            return
        idx = self._nearest_point(event.xdata, event.ydata)
        if idx is not None:
            self._active_idx = idx
            self._dragging = True
            self.activated.emit(self)
            self._redraw()

    def _on_release(self, event) -> None:
        if self._dragging:
            self._dragging = False
            self._active_idx = None
            self._redraw()
            self.curveChanged.emit(self._compute_curve())

    def _on_motion(self, event) -> None:
        if not self._dragging or self._active_idx is None:
            return
        if event.ydata is None:
            return
        # Clamp y to [0, 255]
        new_y = max(0, min(255, event.ydata))
        self._points_y[self._active_idx] = new_y
        self._redraw()
        self.curveChanged.emit(self._compute_curve())

    def get_curve(self) -> np.ndarray:
        """Return the current curve as 256 y-values."""
        return self._compute_curve()

    def reset(self) -> None:
        """Reset to identity curve."""
        self._points_y = self.POINT_X.copy().astype(np.float64)
        self._redraw()
        self.curveChanged.emit(self._compute_curve())

    def set_active(self, active: bool) -> None:
        """Highlight the editor (orange border) when active."""
        if active:
            self.setStyleSheet("border: 1px solid #ff8c00; border-radius: 3px;")
        else:
            self.setStyleSheet("")