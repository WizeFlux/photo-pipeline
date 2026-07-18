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
from matplotlib.ticker import MaxNLocator

from qt_app.state import curve_from_params


# ─── Dark theme constants ────────────────────────────────────────────────────

_BG = "#1e1e1e"
_PANEL = "#232323"
_GRID = "#3a3a3a"
_TEXT = "#b0b0b0"
_MUTED = "#666666"

# Muted channel colors (softer than pure R/G/B)
_CHANNEL_COLORS = {
    "R": "#c67878",
    "G": "#7ec678",
    "B": "#7898c6",
    "Lum": "#888888",
}
_CHANNEL_FILLS = {
    "R": (0.78, 0.47, 0.47, 0.12),
    "G": (0.49, 0.78, 0.47, 0.12),
    "B": (0.47, 0.59, 0.78, 0.12),
}

# Muted curve colors for tone curve
_CURVE_ORIGINAL = "#666666"
_CURVE_LIVE = "#6fbfa8"
_CURVE_PROFILE = "#c6995a"


def _style_axes(ax, title: str = "") -> None:
    ax.set_facecolor(_PANEL)
    ax.set_title(title, color=_TEXT, fontsize=9, pad=4)
    # No tick labels, no axis labels — clean visual
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_color(_GRID)
        spine.set_linewidth(0.5)
    ax.grid(True, color=_GRID, linewidth=0.5, alpha=0.8)
    # Twice as many grid lines via MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(nbins=36))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=24))


def _hist_uint8(ch: np.ndarray, bins: int = 256) -> np.ndarray:
    """Fast histogram for uint8 channel using bincount (10x faster than np.histogram)."""
    ch = ch.astype(np.uint8).ravel()
    return np.bincount(ch, minlength=bins)[:bins]


def _draw_histograms_on_ax(ax, arr: np.ndarray) -> None:
    """Draw R/G/B/Lum histograms on a given axes.

    Optimized: uses bincount, uint8, downsampling, and fill (not fill_between).
    """
    arr = np.asarray(arr, dtype=np.uint8)
    h, w = arr.shape[:2]
    if h * w > 100_000:  # tighter threshold — 100K pixels is plenty
        step = int((h * w / 100_000) ** 0.5)
        arr = arr[::step, ::step]
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    bins = np.arange(256)
    for ch, name in [(r, "R"), (g, "G"), (b, "B")]:
        h = _hist_uint8(ch)
        # Use fill (polygon) instead of fill_between — faster
        ax.fill(np.append(bins, bins[::-1]),
                np.append(h, np.zeros_like(h)),
                color=_CHANNEL_FILLS[name], linewidth=0, zorder=1)
        ax.plot(bins, h, color=_CHANNEL_COLORS[name], linewidth=0.7, zorder=2)
    lum = (0.299 * r + 0.587 * g + 0.114 * b).astype(np.uint8)
    lh = _hist_uint8(lum)
    ax.plot(bins, lh, color=_CHANNEL_COLORS["Lum"], linewidth=0.9, linestyle="--")


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
    titles = ["Original", "Sliders"]
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
    orig_arr = np.asarray(orig, dtype=np.uint8)
    bins = np.arange(256)

    # Downsample orig once if large
    h, w = orig_arr.shape[:2]
    if h * w > 200_000:
        step = int((h * w / 200_000) ** 0.5)
        orig_arr = orig_arr[::step, ::step]
    orig_hists = [_hist_uint8(orig_arr[..., i]) for i in range(3)]

    def _draw_deltas(ax, after_arr, title):
        after_arr = np.asarray(after_arr, dtype=np.uint8)
        if after_arr.shape[:2] != orig_arr.shape[:2]:
            # Different size — downsample to same pixel count
            h2, w2 = after_arr.shape[:2]
            if h2 * w2 > 200_000:
                step2 = int((h2 * w2 / 200_000) ** 0.5)
                after_arr = after_arr[::step2, ::step2]
        for i, name in enumerate(["R", "G", "B"]):
            a_h = _hist_uint8(after_arr[..., i])
            delta = a_h.astype(np.float32) - orig_hists[i].astype(np.float32)
            bins_d = np.append(bins, bins[::-1])
            delta_d = np.append(delta, delta[::-1])
            ax.fill(bins_d, delta_d, color=_CHANNEL_FILLS[name], linewidth=0)
            ax.plot(bins, delta, color=_CHANNEL_COLORS[name], linewidth=1.2,
                    label=name)
        ax.axhline(0, color=_MUTED, linewidth=0.5)
        ax.legend(loc="upper right", framealpha=0.2, fontsize=7,
                  labelcolor=_TEXT, edgecolor=_GRID)

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
    ax.plot(x, x, color=_CURVE_ORIGINAL, linewidth=1.0, linestyle="--", label="Original")

    _, y_live = curve_from_params(params)
    ax.plot(x, y_live, color=_CURVE_LIVE, linewidth=2.0, label="Sliders")

    if third_params is not None:
        _, y_prof = curve_from_params(third_params)
        ax.plot(x, y_prof, color=_CURVE_PROFILE, linewidth=1.5, linestyle="--",
                label=profile_name if profile_name else "Profile")

    ax.set_xlim(0, 255)
    ax.set_ylim(0, 255)
    ax.legend(loc="upper left", framealpha=0.2, fontsize=7, labelcolor=_TEXT,
              edgecolor=_GRID)
    fig.tight_layout(pad=0.5)