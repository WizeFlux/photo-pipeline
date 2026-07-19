"""Interactive S-Curve editor widget — draggable control points.

Renders a tone curve on a matplotlib canvas with 5 draggable control points.
The user drags points up/down to shape the curve; the widget emits the
resulting curve as 256 y-values via `curveChanged`.

Used as the 6th column in the adjustments row (after LUT).
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


# Dark theme
_BG = "#1e1e1e"
_PANEL = "#232323"
_GRID = "#3a3a3a"
_TEXT = "#b0b0b0"
_CURVE_COLOR = "#6fbfa8"       # teal — curve line
_POINT_COLOR = "#6fbfa8"       # teal — inactive control points
_POINT_ACTIVE = "#ff8c00"      # orange — active control point
_POINT_EDGE = "#4a9888"        # teal edge for inactive points


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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._fig = Figure(figsize=(2.5, 1.4), facecolor=_BG)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setMinimumHeight(55)
        # Enable mouse tracking so motion_notify_event fires during drag
        # (otherwise matplotlib only reports motion when no button is held).
        self._canvas.setMouseTracking(True)
        self._canvas.mpl_connect("button_press_event", self._on_press)
        self._canvas.mpl_connect("button_release_event", self._on_release)
        self._canvas.mpl_connect("motion_notify_event", self._on_motion)
        # Install event filter on canvas to intercept wheel events —
        # matplotlib's FigureCanvasQTAgg consumes wheel events for zooming
        # and does not forward them to the parent widget.
        self._canvas.installEventFilter(self)
        layout.addWidget(self._canvas, 1)
        self._redraw()

    def eventFilter(self, obj, event):
        """Intercept wheel events on the canvas and forward to self."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.Wheel:
            self.wheelEvent(event)
            return True  # consume — don't let matplotlib zoom
        return False

    def _redraw(self) -> None:
        self._fig.clear()
        self._fig.set_facecolor(_BG)
        ax = self._fig.add_subplot(111)
        # Tight margins — minimize top/bottom padding so the curve fills
        # the available canvas height.
        self._fig.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
        ax.set_facecolor(_PANEL)
        ax.set_xlim(-5, 260)
        ax.set_ylim(-5, 260)
        # Identity dashed line
        x = np.linspace(0, 255, 256)
        ax.plot(x, x, color="#666", linewidth=0.8, linestyle="--", alpha=0.5)
        # The curve
        y = self._compute_curve()
        ax.plot(x, y, color=_CURVE_COLOR, linewidth=2.0)
        # Control points — teal inactive, orange active
        for i, (px, py) in enumerate(zip(self.POINT_X, self._points_y)):
            is_active = i == self._active_idx
            color = _POINT_ACTIVE if is_active else _POINT_COLOR
            edge = "#cc7000" if is_active else _POINT_EDGE
            ax.plot(px, py, "o", color=color, markersize=6,
                    markeredgecolor=edge, markeredgewidth=1.0, picker=5)
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
        """Find the nearest control point within a threshold.

        Threshold is in data coordinates (0-255 range). We use a generous
        threshold so small canvases are still usable.
        """
        dists = np.sqrt((self.POINT_X - x)**2 + (self._points_y - y)**2)
        idx = int(np.argmin(dists))
        if dists[idx] < 40:  # data-coord threshold
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
            # Keep _active_idx so the point stays orange after release.
            # The point only deactivates when another point is grabbed or
            # the editor loses focus.
            self._redraw()
            self.curveChanged.emit(self._compute_curve())

    def _on_motion(self, event) -> None:
        # Only move when dragging (mouse button held + active point)
        if not self._dragging or self._active_idx is None:
            return
        if event.ydata is None:
            return
        # Clamp y to [0, 255]
        new_y = max(0, min(255, event.ydata))
        if new_y != self._points_y[self._active_idx]:
            self._points_y[self._active_idx] = new_y
            self._redraw()
            self.curveChanged.emit(self._compute_curve())

    def wheelEvent(self, event) -> None:
        """Mouse wheel moves the active control point (or nearest by x).

        Scroll up = increase y, scroll down = decrease y.
        """
        ax = self._fig.axes[0] if self._fig.axes else None
        if ax is None:
            event.ignore()
            return
        # Determine which point to move: the active one, or the middle.
        # (Coordinate mapping from widget→data is fragile across matplotlib
        # versions; using the active point is robust and matches user intent.)
        if self._active_idx is None:
            # Pick middle point as default
            self._active_idx = 2
            self.activated.emit(self)
        idx = self._active_idx
        # Move point: scroll up = decrease y, scroll down = increase y (inverted)
        delta = event.angleDelta().y()
        step = 1  # 1 IRE unit per notch for fine control
        new_y = max(0, min(255, self._points_y[idx] + (-step if delta > 0 else step)))
        if new_y != self._points_y[idx]:
            self._points_y[idx] = new_y
            self._redraw()
            self.curveChanged.emit(self._compute_curve())
        event.accept()

    def get_curve(self) -> np.ndarray:
        """Return the current curve as 256 y-values."""
        return self._compute_curve()

    def set_curve_from_y(self, curve: np.ndarray) -> None:
        """Set control points to best-match a 256-value curve.

        Samples the curve at the fixed x positions (0, 64, 128, 192, 255)
        and updates the control points. This is used when loading a profile.
        """
        curve = np.asarray(curve, dtype=np.float64)
        for i, x in enumerate(self.POINT_X):
            xi = int(round(x))
            xi = max(0, min(255, xi))
            self._points_y[i] = max(0, min(255, float(curve[xi])))
        self._redraw()

    def reset(self) -> None:
        """Reset to identity curve."""
        self._points_y = self.POINT_X.copy().astype(np.float64)
        self._redraw()
        self.curveChanged.emit(self._compute_curve())

    def set_active(self, active: bool) -> None:
        """Subtle highlight when active — no border, just tint the curve."""
        # No-op: the active point is already highlighted in _redraw.
        # Intentionally no orange border per user request.
        pass