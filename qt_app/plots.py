"""Matplotlib render functions for the analysis plots.

Each function draws onto an *existing* Figure (cleared first) rather than
creating a new one. This is the safe pattern for embedding matplotlib in Qt:
a single Figure lives for the lifetime of the canvas, and we only clear+redraw
its contents — no Figure object swapping, which can segfault when Python GC
collects the old figure while Qt still references it during draw.

Eight plots, all dark-themed:
  • draw_histograms_row  — 2 or 3 RGB+luminance histograms side by side
  • draw_channel_deltas  — per-channel histogram diffs (After − Original)
  • draw_tone_curve      — identity / live / profile curves
  • draw_rgb_waveform    — IRE waveforms per channel (video-style)
  • draw_vectorscope     — polar hue/saturation scope with skin-tone line
  • draw_saturation_hist — HSV saturation distribution
  • draw_zone_system     — Adams 11-zone tonal distribution bar chart
  • draw_clipping_map    — 2D clipping heat map (shadows / highlights)
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
    """Draw per-channel histogram deltas onto `fig` (cleared first).

    Two panels when a profile is present:
      • Left:  Sliders − Original  (effect of current adjustments vs source)
      • Right: Sliders − Profile   (how your adjustments differ from the
        saved profile — useful for matching a look)
    One panel when no profile: Sliders − Original only.
    """
    fig.clear()
    fig.set_facecolor(_BG)
    orig_arr = np.asarray(orig, dtype=np.uint8)
    bins = np.arange(256)

    def _downsample(arr: np.ndarray) -> np.ndarray:
        h, w = arr.shape[:2]
        if h * w > 200_000:
            step = int((h * w / 200_000) ** 0.5)
            arr = arr[::step, ::step]
        return arr

    orig_arr = _downsample(orig_arr)
    orig_hists = [_hist_uint8(orig_arr[..., i]) for i in range(3)]

    def _draw_deltas(ax, after_arr, baseline_hists, title):
        after_arr = np.asarray(after_arr, dtype=np.uint8)
        if after_arr.shape[:2] != orig_arr.shape[:2]:
            after_arr = _downsample(after_arr)
        for i, name in enumerate(["R", "G", "B"]):
            a_h = _hist_uint8(after_arr[..., i])
            delta = a_h.astype(np.float32) - baseline_hists[i].astype(np.float32)
            bins_d = np.append(bins, bins[::-1])
            delta_d = np.append(delta, delta[::-1])
            ax.fill(bins_d, delta_d, color=_CHANNEL_FILLS[name], linewidth=0)
            ax.plot(bins, delta, color=_CHANNEL_COLORS[name], linewidth=1.2,
                    label=name)
        ax.axhline(0, color=_MUTED, linewidth=0.5)
        ax.legend(loc="upper right", framealpha=0.2, fontsize=7,
                  labelcolor=_TEXT, edgecolor=_GRID)

    if profile is not None:
        # Two panels: Sliders−Original | Sliders−Profile
        prof_arr = _downsample(np.asarray(profile, dtype=np.uint8))
        prof_hists = [_hist_uint8(prof_arr[..., i]) for i in range(3)]

        ax1 = fig.add_subplot(1, 2, 1)
        _style_axes(ax1, "Sliders − Original")
        _draw_deltas(ax1, live, orig_hists, "Sliders − Original")

        ax2 = fig.add_subplot(1, 2, 2)
        _style_axes(ax2, f"Sliders − {profile_name or 'Profile'}")
        _draw_deltas(ax2, live, prof_hists, f"Sliders − {profile_name or 'Profile'}")
    else:
        # One panel: Sliders − Original
        ax1 = fig.add_subplot(1, 1, 1)
        _style_axes(ax1, "Sliders − Original")
        _draw_deltas(ax1, live, orig_hists, "Sliders − Original")
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


# ─── RGB Waveform (video-style IRE monitor) ──────────────────────────────────

def _rgb_to_hsv(arr: np.ndarray) -> np.ndarray:
    """RGB (H,W,3) uint8/float → HSV (H,W,3) float. Vectorized, no cv2 dep."""
    arr = np.asarray(arr, dtype=np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    maxc = arr.max(axis=-1)
    minc = arr.min(axis=-1)
    delta = maxc - minc

    # Value
    v = maxc
    # Saturation
    s = np.where(maxc > 0, delta / np.maximum(maxc, 1e-8), 0.0)
    # Hue — compute via safe division, then add offsets per dominant channel
    safe_delta = np.where(delta > 0, delta, 1.0)  # avoid /0; result ignored where delta==0
    rc = (maxc == r) & (delta > 0)
    gc = (maxc == g) & (delta > 0)
    bc = (maxc == b) & (delta > 0)
    hue = np.zeros_like(maxc)
    hue = np.where(rc, (g - b) / safe_delta, hue)
    hue = np.where(gc, (b - r) / safe_delta + 2.0, hue)
    hue = np.where(bc, (r - g) / safe_delta + 4.0, hue)
    hue = (hue / 6.0) % 1.0
    return np.stack([hue, s, v], axis=-1)


def _downsample_col(arr: np.ndarray, target_cols: int = 256) -> np.ndarray:
    """Downsample image columns by averaging — keeps spatial x-axis meaningful."""
    h, w = arr.shape[:2]
    if w <= target_cols:
        return arr
    # Average-pool along width
    step = w // target_cols
    return arr[:, :step * target_cols].reshape(h, target_cols, step, -1).mean(axis=2)


def draw_rgb_waveform(
    fig: Figure,
    orig: np.ndarray,
    live: np.ndarray,
    profile: np.ndarray | None = None,
    profile_name: str | None = None,
) -> None:
    """Draw per-channel IRE waveforms (video color-grading style).

    For each column of the image, plots the luminance distribution vertically
    (0 at bottom, 255 at top). Uses RGB parade layout: R | G | B side-by-side
    as separate panels so channels don't occlude each other. Brighter = more
    pixels at that IRE level for that column.
    """
    fig.clear()
    fig.set_facecolor(_BG)

    def _wave_on_ax(ax, arr: np.ndarray, title: str) -> None:
        arr = np.asarray(arr, dtype=np.float32)
        arr = _downsample_col(arr, 256)
        h, w = arr.shape[:2]
        if h > 100_000:
            arr = arr[::2]
            h = arr.shape[0]
        # RGB parade: 3 sub-panels within this axes's slot — R | G | B
        for ci, label in enumerate(["R", "G", "B"]):
            chan = arr[..., ci].astype(np.int32)
            # Build column-wise histogram intensity matrix (256 x W)
            intensity = np.zeros((256, w), dtype=np.float32)
            for x in range(w):
                h_x = np.bincount(chan[:, x], minlength=256)[:256]
                intensity[:, x] = h_x
            # Gamma-stretch for visibility: low counts become visible
            mx = intensity.max()
            if mx > 0:
                intensity = (intensity / mx) ** 0.5  # sqrt gamma → brighter lows
            # Sub-axes: 3 vertical strips inside this slot
            sub = ax.inset_axes([(ci / 3) + 0.005, 0.0, (1 / 3) - 0.01, 1.0])
            sub.imshow(intensity, aspect="auto", origin="lower",
                       extent=[0, w, 0, 255], cmap={"R": "magma", "G": "viridis",
                                                     "B": "cividis"}[label],
                       vmin=0, vmax=1.0)
            sub.set_xticklabels([])
            sub.set_yticklabels([])
            sub.tick_params(length=0)
            for sp in sub.spines.values():
                sp.set_color(_GRID)
                sp.set_linewidth(0.5)
            # Channel label at top of each strip
            sub.set_title(label, color=_CHANNEL_COLORS[label], fontsize=8,
                          pad=2, loc="left")
        # Parent axes: just frame + main title, no grid lines
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_color(_GRID)
            sp.set_linewidth(0.5)
        ax.set_facecolor(_PANEL)
        ax.set_title(title, color=_TEXT, fontsize=9, pad=4)
        ax.set_ylim(0, 255)

    n = 3 if profile is not None else 2
    titles = ["Original", "Sliders"]
    arrays = [orig, live]
    if profile is not None:
        titles.append(profile_name or "Profile")
        arrays.append(profile)
    for i, (title, arr) in enumerate(zip(titles, arrays)):
        ax = fig.add_subplot(1, n, i + 1)
        _wave_on_ax(ax, arr, title)
    fig.tight_layout(pad=0.5)


# ─── Vectorscope (polar hue/saturation with skin-tone line) ──────────────────

def draw_vectorscope(
    fig: Figure,
    orig: np.ndarray,
    live: np.ndarray,
    profile: np.ndarray | None = None,
    profile_name: str | None = None,
) -> None:
    """Draw polar vectorscopes (hue angle vs saturation radius).

    Skin tones cluster around the 'skin tone line' at ~123° (YB axis in YUV).
    Saturation increases outward; hue is the angle. Useful for matching color
    grading across images and detecting color casts.
    """
    fig.clear()
    fig.set_facecolor(_BG)

    def _scope_on_ax(ax, arr: np.ndarray, title: str) -> None:
        hsv = _rgb_to_hsv(arr)
        h, s = hsv[..., 0].ravel(), hsv[..., 1].ravel()
        # Downsample for performance
        if h.size > 60_000:
            idx = np.random.choice(h.size, 60_000, replace=False)
            h, s = h[idx], s[idx]
        # Filter out low-saturation pixels (gray noise in center)
        mask = s > 0.05
        h, s = h[mask], s[mask]
        # Angle in degrees, 0 at right, counterclockwise
        theta = h * 2 * np.pi
        r = s
        ax.scatter(theta, r, s=1.0, c=h, cmap="hsv", alpha=0.25, linewidths=0)
        # Skin tone line: ~123° in YUV ≈ hue ~0.07-0.12 (orange) in HSV
        skin_hue = 0.08  # approximate
        for ang in [skin_hue * 2 * np.pi]:
            ax.plot([ang, ang], [0, 1], color="#ffaa66", linewidth=1.0,
                    linestyle="--", alpha=0.7)
        ax.set_theta_zero_location("E")
        ax.set_theta_direction(1)
        ax.set_ylim(0, 1)
        ax.set_title(title, color=_TEXT, fontsize=9, pad=8)
        ax.set_facecolor(_PANEL)
        ax.tick_params(colors=_MUTED, labelsize=6)
        for spine in ax.spines.values():
            spine.set_color(_GRID)
            spine.set_linewidth(0.5)
        ax.grid(True, color=_GRID, linewidth=0.4, alpha=0.6)

    n = 3 if profile is not None else 2
    titles = ["Original", "Sliders"]
    arrays = [orig, live]
    if profile is not None:
        titles.append(profile_name or "Profile")
        arrays.append(profile)
    for i, (title, arr) in enumerate(zip(titles, arrays)):
        ax = fig.add_subplot(1, n, i + 1, projection="polar")
        _scope_on_ax(ax, arr, title)
    fig.tight_layout(pad=0.5)


# ─── Saturation histogram (HSV S-channel distribution) ───────────────────────

def draw_saturation_hist(
    fig: Figure,
    orig: np.ndarray,
    live: np.ndarray,
    profile: np.ndarray | None = None,
    profile_name: str | None = None,
) -> None:
    """Draw HSV saturation histograms (0 = gray, 1 = fully saturated)."""
    fig.clear()
    fig.set_facecolor(_BG)

    def _sat_hist(arr: np.ndarray) -> np.ndarray:
        hsv = _rgb_to_hsv(arr)
        s = hsv[..., 1].ravel()
        if s.size > 200_000:
            s = s[np.random.choice(s.size, 200_000, replace=False)]
        hist, _ = np.histogram(s, bins=50, range=(0, 1))
        return hist

    bins = np.linspace(0, 1, 50)
    ax = fig.add_subplot(1, 1, 1)
    _style_axes(ax, "Saturation Distribution")

    h_orig = _sat_hist(orig)
    ax.fill_between(bins, h_orig, alpha=0.25, color=_CURVE_ORIGINAL,
                    label="Original")
    ax.plot(bins, h_orig, color=_CURVE_ORIGINAL, linewidth=1.0)

    h_live = _sat_hist(live)
    ax.fill_between(bins, h_live, alpha=0.25, color=_CURVE_LIVE, label="Sliders")
    ax.plot(bins, h_live, color=_CURVE_LIVE, linewidth=1.2)

    if profile is not None:
        h_prof = _sat_hist(profile)
        ax.plot(bins, h_prof, color=_CURVE_PROFILE, linewidth=1.2,
                linestyle="--", label=profile_name or "Profile")

    ax.set_xlim(0, 1)
    ax.legend(loc="upper right", framealpha=0.2, fontsize=7,
              labelcolor=_TEXT, edgecolor=_GRID)
    fig.tight_layout(pad=0.5)


# ─── Zone System (Adams 11-zone tonal distribution) ──────────────────────────

_ZONE_NAMES = ["0", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
_ZONE_COLORS = [
    "#000000", "#1a1a1a", "#333333", "#4d4d4d", "#666666", "#808080",
    "#999999", "#b3b3b3", "#cccccc", "#e6e6e6", "#ffffff",
]


def draw_zone_system(
    fig: Figure,
    orig: np.ndarray,
    live: np.ndarray,
    profile: np.ndarray | None = None,
    profile_name: str | None = None,
) -> None:
    """Draw Adams 11-zone tonal distribution as grouped bar chart.

    Zone 0 = pure black, Zone X = pure white. Shows how tones are distributed
    across the dynamic range — classic photography tool.
    """
    fig.clear()
    fig.set_facecolor(_BG)

    def _zone_dist(arr: np.ndarray) -> np.ndarray:
        arr = np.asarray(arr, dtype=np.float32)
        lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]).ravel()
        # Map 0-255 → 11 zones (0-10)
        zones = np.clip((lum / 255.0 * 11).astype(int), 0, 10)
        counts = np.bincount(zones, minlength=11)
        return counts / counts.sum() * 100

    ax = fig.add_subplot(1, 1, 1)
    _style_axes(ax, "Zone System (Adams)")
    ax.set_facecolor(_PANEL)

    x = np.arange(11)
    width = 0.28

    z_orig = _zone_dist(orig)
    z_live = _zone_dist(live)
    z_prof = _zone_dist(profile) if profile is not None else None

    # Bars colored by zone brightness
    for i, zc in enumerate(_ZONE_COLORS):
        ax.bar(i - width, z_orig[i], width=width, color=zc, edgecolor=_GRID,
               linewidth=0.4)
        ax.bar(i, z_live[i], width=width, color=zc, edgecolor=_CURVE_LIVE,
               linewidth=1.2)
        if z_prof is not None:
            ax.bar(i + width, z_prof[i], width=width, color=zc,
                   edgecolor=_CURVE_PROFILE, linewidth=1.2, alpha=0.7)

    # Legend (manual since bars use zone colors)
    from matplotlib.patches import Patch
    handles = [
        Patch(facecolor="#555", edgecolor=_GRID, label="Original"),
        Patch(facecolor="#555", edgecolor=_CURVE_LIVE, label="Sliders"),
    ]
    if profile is not None:
        handles.append(Patch(facecolor="#555", edgecolor=_CURVE_PROFILE,
                             label=profile_name or "Profile"))
    ax.legend(handles=handles, loc="upper right", framealpha=0.2, fontsize=7,
              labelcolor=_TEXT, edgecolor=_GRID)

    ax.set_xticks(x)
    ax.set_xticklabels(_ZONE_NAMES, color=_TEXT, fontsize=8)
    ax.set_xlim(-0.5, 10.5)
    fig.tight_layout(pad=0.5)


# ─── Clipping map (2D shadow/highlight loss visualization) ───────────────────

def draw_clipping_map(
    fig: Figure,
    orig: np.ndarray,
    live: np.ndarray,
    profile: np.ndarray | None = None,
    profile_name: str | None = None,
) -> None:
    """Draw 2D clipping maps: blue = lost shadows (<3), red = lost highlights (>252).

    Spatial map showing WHERE detail is being clipped — critical for
    avoiding blown highlights or crushed blacks during grading.
    """
    fig.clear()
    fig.set_facecolor(_BG)

    def _clip_map(arr: np.ndarray) -> np.ndarray:
        """Returns (H, W, 3) RGB: black bg, blue shadows, red highlights."""
        arr = np.asarray(arr, dtype=np.uint8)
        out = np.zeros(arr.shape, dtype=np.float32)
        # Shadow clip: any channel < 3
        shadow = (arr.min(axis=-1) < 3)[..., None]
        # Highlight clip: any channel > 252
        highlight = (arr.max(axis=-1) > 252)[..., None]
        # Blue for shadows, red for highlights, magenta if both
        out[..., 0] = highlight[..., 0] * 0.9  # red
        out[..., 2] = shadow[..., 0] * 0.9     # blue
        # Where both → magenta (overwrite)
        both = shadow & highlight
        out[both[..., 0]] = [0.9, 0.0, 0.9]
        return out

    n = 3 if profile is not None else 2
    titles = ["Original", "Sliders"]
    arrays = [orig, live]
    if profile is not None:
        titles.append(profile_name or "Profile")
        arrays.append(profile)
    for i, (title, arr) in enumerate(zip(titles, arrays)):
        ax = fig.add_subplot(1, n, i + 1)
        m = _clip_map(arr)
        ax.imshow(m, aspect="equal")
        ax.set_title(title, color=_TEXT, fontsize=9, pad=4)
        ax.set_xticklabels([])
        ax.set_yticklabels([])
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_color(_GRID)
            spine.set_linewidth(0.5)
    fig.tight_layout(pad=0.5)