"""Matplotlib render functions for the analysis plots.

Each function draws onto an *existing* Figure (cleared first) rather than
creating a new one. This is the safe pattern for embedding matplotlib in Qt:
a single Figure lives for the lifetime of the canvas, and we only clear+redraw
its contents — no Figure object swapping, which can segfault when Python GC
collects the old figure while Qt still references it during draw.

Three plots, all dark-themed:
  • draw_histograms_row  — 2 or 3 RGB+luminance histograms side by side
  • draw_channel_deltas  — per-channel histogram diffs (After − Original)
  • draw_tone_curve      — identity / live / profile curves
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


def _style_axes(ax, title: str = "") -> None:
    ax.set_facecolor(_PANEL)
    ax.set_title(title, color=_TEXT, fontsize=10, pad=6)
    # No tick labels, no axis labels — clean visual
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.tick_params(length=0)  # hide tick marks too
    for spine in ax.spines.values():
        spine.set_color(_GRID)
    ax.grid(True, color=_GRID, linewidth=0.5, alpha=0.6)


def _draw_histograms_on_ax(ax, arr: np.ndarray) -> None:
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


def make_empty_figure(width=7, height=2.8) -> Figure:
    """Create a dark-themed empty figure for a canvas."""
    return Figure(figsize=(width, height), facecolor=_BG)


# ─── Public draw functions (mutate the given figure in place) ────────────────

def draw_histograms_row(
    fig: Figure,
    orig: np.ndarray,
    live: np.ndarray,
    profile: np.ndarray | None = None,
    profile_name: str | None = None,
) -> None:
    """Draw 2 or 3 histograms onto `fig` (cleared first)."""
    fig.clear()
    fig.set_facecolor(_BG)
    n = 3 if profile is not None else 2
    titles = ["Original", "Live Sliders"]
    arrays = [orig, live]
    if profile is not None:
        titles.append(profile_name or "Profile")
        arrays.append(profile)
    for i, (title, arr) in enumerate(zip(titles, arrays)):
        ax = fig.add_subplot(1, n, i + 1)
        _style_axes(ax, title)
        _draw_histograms_on_ax(ax, arr)
    fig.tight_layout(pad=0.5)


def draw_channel_deltas(
    fig: Figure,
    orig: np.ndarray,
    live: np.ndarray,
    profile: np.ndarray | None = None,
    profile_name: str | None = None,
) -> None:
    """Draw per-channel histogram deltas onto `fig` (cleared first)."""
    fig.clear()
    fig.set_facecolor(_BG)
    orig_arr = np.asarray(orig, dtype=np.float64)
    bins = np.arange(0, 257, 1)

    def _draw_deltas(ax, after_arr, title):
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
    ax1 = fig.add_subplot(1, n, 1)
    _style_axes(ax1, "Live − Original")
    _draw_deltas(ax1, live, "Live − Original")
    if profile is not None:
        ax2 = fig.add_subplot(1, n, 2)
        _style_axes(ax2, f"{profile_name} − Original")
        _draw_deltas(ax2, profile, f"{profile_name} − Original")
    fig.tight_layout(pad=0.5)


def draw_tone_curve(
    fig: Figure,
    params: dict,
    third_params: dict | None = None,
    profile_name: str | None = None,
) -> None:
    """Draw identity + live (+ profile) tone curves onto `fig` (cleared first)."""
    fig.clear()
    fig.set_facecolor(_BG)
    ax = fig.add_subplot(1, 1, 1)
    _style_axes(ax, "Tone Curve")

    x = np.linspace(0, 255, 256)
    ax.plot(x, x, color=_MUTED, linewidth=1.0, linestyle="--", label="Identity")

    _, y_live = curve_from_params(params)
    ax.plot(x, y_live, color="#00d4aa", linewidth=2.5, label="Live")

    if third_params is not None:
        _, y_prof = curve_from_params(third_params)
        ax.plot(x, y_prof, color="#ff9900", linewidth=2.0, linestyle="--",
                label=profile_name if profile_name else "Profile")

    ax.set_xlim(0, 255)
    ax.set_ylim(0, 255)
    ax.legend(loc="upper left", framealpha=0.3, fontsize=8, labelcolor=_TEXT)
    fig.tight_layout(pad=0.5)