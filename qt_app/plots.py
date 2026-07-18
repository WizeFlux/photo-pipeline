"""Matplotlib figure builders for the analysis plots.

Three figures, all dark-themed to match the app:
  • histograms_row  — 2 or 3 RGB+luminance histograms side by side
  • channel_deltas  — per-channel histogram diffs (After − Original)
  • tone_curve      — identity / live / profile curves

All functions return a `matplotlib.figure.Figure` ready to be embedded
via `FigureCanvasQTAgg`.
"""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from qt_app.state import curve_from_params


# ─── Dark theme constants ────────────────────────────────────────────────────

_BG = "#1e1e1e"
_PANEL = "#262626"
_GRID = "#333333"
_TEXT = "#e0e0e0"
_MUTED = "#888888"

_CHANNEL_COLORS = {
    "R": "#ff5555",
    "G": "#55ff88",
    "B": "#5588ff",
    "Lum": "#aaaaaa",
}
_CHANNEL_FILLS = {
    "R": (1.0, 0.33, 0.33, 0.15),
    "G": (0.33, 1.0, 0.53, 0.15),
    "B": (0.33, 0.53, 1.0, 0.15),
}


def _new_figure(width=7, height=2.6) -> Figure:
    fig = Figure(figsize=(width, height), facecolor=_BG)
    return fig


def _style_axes(ax, title: str = "") -> None:
    ax.set_facecolor(_PANEL)
    ax.set_title(title, color=_TEXT, fontsize=10, pad=6)
    ax.tick_params(colors=_MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(_GRID)
    ax.grid(True, color=_GRID, linewidth=0.5, alpha=0.6)
    ax.xaxis.label.set_color(_MUTED)
    ax.yaxis.label.set_color(_MUTED)


def _add_histograms_to_ax(ax, arr: np.ndarray) -> None:
    """Draw R/G/B/Lum histograms on a given axes."""
    arr = np.asarray(arr, dtype=np.float64)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    bins = np.arange(0, 257, 1)
    for ch, name in [(r, "R"), (g, "G"), (b, "B")]:
        h, _ = np.histogram(ch, bins=bins)
        ax.fill_between(bins[:-1], h, color=_CHANNEL_FILLS[name], linewidth=0)
        ax.plot(bins[:-1], h, color=_CHANNEL_COLORS[name], linewidth=0.8)
    lh, _ = np.histogram(lum, bins=bins)
    ax.plot(bins[:-1], lh, color=_CHANNEL_COLORS["Lum"], linewidth=1.0, linestyle="--")


# ─── Public figure builders ──────────────────────────────────────────────────

def histograms_row(
    orig: np.ndarray,
    live: np.ndarray,
    profile: np.ndarray | None = None,
    profile_name: str | None = None,
) -> Figure:
    """2 or 3 histograms in a row."""
    n = 3 if profile is not None else 2
    fig = _new_figure(height=2.8)
    titles = ["Original", "Live Sliders"]
    if profile is not None:
        titles.append(profile_name or "Profile")
    for i, (title, arr) in enumerate(
        zip(titles, [orig, live] + ([profile] if profile is not None else []))
    ):
        ax = fig.add_subplot(1, n, i + 1)
        _style_axes(ax, title)
        _add_histograms_to_ax(ax, arr)
        ax.set_xlabel("Value (0–255)")
        if i == 0:
            ax.set_ylabel("Pixel count")
    fig.tight_layout(pad=0.8)
    return fig


def channel_deltas(
    orig: np.ndarray,
    live: np.ndarray,
    profile: np.ndarray | None = None,
    profile_name: str | None = None,
) -> Figure:
    """Per-channel histogram deltas: After − Original."""
    orig_arr = np.asarray(orig, dtype=np.float64)
    bins = np.arange(0, 257, 1)

    def _add_deltas(ax, after_arr, title):
        after_arr = np.asarray(after_arr, dtype=np.float64)
        for i, name in enumerate(["R", "G", "B"]):
            o_h, _ = np.histogram(orig_arr[..., i], bins=bins)
            a_h, _ = np.histogram(after_arr[..., i], bins=bins)
            delta = a_h.astype(np.float64) - o_h.astype(np.float64)
            ax.fill_between(bins[:-1], delta, color=_CHANNEL_FILLS[name], linewidth=0)
            ax.plot(bins[:-1], delta, color=_CHANNEL_COLORS[name], linewidth=1.5,
                    label=name)
        ax.axhline(0, color=_MUTED, linewidth=0.6)
        ax.legend(loc="upper right", framealpha=0.3, fontsize=8,
                  labelcolor=_TEXT)

    n = 2 if profile is not None else 1
    fig = _new_figure(height=2.8)
    ax1 = fig.add_subplot(1, n, 1)
    _style_axes(ax1, "Live − Original")
    _add_deltas(ax1, live, "Live − Original")
    ax1.set_xlabel("Value")
    ax1.set_ylabel("Δ pixel count")
    if profile is not None:
        ax2 = fig.add_subplot(1, n, 2)
        _style_axes(ax2, f"{profile_name} − Original")
        _add_deltas(ax2, profile, f"{profile_name} − Original")
        ax2.set_xlabel("Value")
    fig.tight_layout(pad=0.8)
    return fig


def tone_curve(
    params: dict,
    third_params: dict | None = None,
    profile_name: str | None = None,
) -> Figure:
    """Identity + live (+ profile) tone curves."""
    fig = _new_figure(height=2.8)
    ax = fig.add_subplot(1, 1, 1)
    _style_axes(ax, "Tone Curve")

    x = np.linspace(0, 255, 256)
    ax.plot(x, x, color=_MUTED, linewidth=1.0, linestyle="--", label="Identity")

    _, y_live = curve_from_params(params)
    ax.plot(x, y_live, color="#00d4aa", linewidth=2.5, label="Live")

    if third_params is not None:
        _, y_prof = curve_from_params(third_params)
        ax.plot(x, y_prof, color="#ff9900", linewidth=2.0, linestyle="--",
                label=f"{profile_name}" if profile_name else "Profile")

    ax.set_xlabel("Input")
    ax.set_ylabel("Output")
    ax.set_xlim(0, 255)
    ax.set_ylim(0, 255)
    ax.legend(loc="upper left", framealpha=0.3, fontsize=8, labelcolor=_TEXT)
    fig.tight_layout(pad=0.8)
    return fig