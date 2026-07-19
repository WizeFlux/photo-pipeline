"""Tests for plot rendering functions — all 8 plot types render without error."""

import numpy as np
import pytest

matplotlib = pytest.importorskip("matplotlib")
from matplotlib.figure import Figure

from qt_app.plots import (
    draw_channel_deltas,
    draw_clipping_map,
    draw_histograms_row,
    draw_rgb_waveform,
    draw_saturation_hist,
    draw_tone_curve,
    draw_vectorscope,
    draw_zone_system,
    _rgb_to_hsv,
)
from qt_app.state import PARAM_DEFAULTS, params_from_values


@pytest.fixture
def sample_arrays():
    """Three synthetic images: original, brighter live, darker profile."""
    np.random.seed(42)
    orig = (np.random.rand(120, 180, 3) * 255).astype(np.uint8)
    live = np.clip(orig.astype(np.float32) * 1.2 + 20, 0, 255).astype(np.uint8)
    profile = np.clip(orig.astype(np.float32) * 0.85 + 15, 0, 255).astype(np.uint8)
    return orig, live, profile


@pytest.fixture
def params():
    p = params_from_values(PARAM_DEFAULTS)
    p["ev"] = 0.5
    p["contrast_amount"] = 15
    return p


def _fig():
    return Figure(figsize=(7, 2.8))


# ─── HSV helper ──────────────────────────────────────────────────────────────

def test_rgb_to_hsv_shape():
    arr = (np.random.rand(10, 20, 3) * 255).astype(np.uint8)
    hsv = _rgb_to_hsv(arr)
    assert hsv.shape == (10, 20, 3)


def test_rgb_to_hsv_range():
    arr = (np.random.rand(10, 10, 3) * 255).astype(np.uint8)
    hsv = _rgb_to_hsv(arr)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    assert h.min() >= 0 and h.max() <= 1
    assert s.min() >= 0 and s.max() <= 1
    assert v.min() >= 0 and v.max() <= 1


def test_rgb_to_hsv_gray_has_zero_saturation():
    arr = np.full((5, 5, 3), 128, dtype=np.uint8)
    hsv = _rgb_to_hsv(arr)
    assert np.all(hsv[..., 1] == 0)  # gray -> zero saturation


def test_rgb_to_hsv_red_is_hue_zero():
    arr = np.zeros((5, 5, 3), dtype=np.uint8)
    arr[..., 0] = 255  # pure red
    hsv = _rgb_to_hsv(arr)
    # Red hue is at 0 in HSV
    assert np.allclose(hsv[..., 0], 0.0)


# ─── Each plot type renders without error ────────────────────────────────────

def test_histograms_2panel(sample_arrays):
    orig, live, _ = sample_arrays
    fig = _fig()
    draw_histograms_row(fig, orig, live)
    assert len(fig.axes) == 2


def test_histograms_3panel(sample_arrays):
    orig, live, profile = sample_arrays
    fig = _fig()
    draw_histograms_row(fig, orig, live, profile, "Cine")
    assert len(fig.axes) == 3


def test_channel_deltas_1panel(sample_arrays):
    orig, live, _ = sample_arrays
    fig = _fig()
    draw_channel_deltas(fig, orig, live)
    assert len(fig.axes) == 1


def test_channel_deltas_2panel(sample_arrays):
    orig, live, profile = sample_arrays
    fig = _fig()
    draw_channel_deltas(fig, orig, live, profile, "Cine")
    assert len(fig.axes) == 2


def test_tone_curve(params):
    fig = _fig()
    draw_tone_curve(fig, params, third_params=None)
    assert len(fig.axes) == 1


def test_tone_curve_with_profile(params):
    fig = _fig()
    draw_tone_curve(fig, params, third_params=params, profile_name="Cine")
    assert len(fig.axes) == 1


def test_rgb_waveform_2panel(sample_arrays):
    orig, live, _ = sample_arrays
    fig = _fig()
    draw_rgb_waveform(fig, orig, live)
    assert len(fig.axes) == 2


def test_rgb_waveform_3panel(sample_arrays):
    orig, live, profile = sample_arrays
    fig = _fig()
    draw_rgb_waveform(fig, orig, live, profile, "Cine")
    assert len(fig.axes) == 3


def test_vectorscope_2panel(sample_arrays):
    orig, live, _ = sample_arrays
    fig = _fig()
    draw_vectorscope(fig, orig, live)
    assert len(fig.axes) == 2


def test_vectorscope_3panel(sample_arrays):
    orig, live, profile = sample_arrays
    fig = _fig()
    draw_vectorscope(fig, orig, live, profile, "Cine")
    assert len(fig.axes) == 3


def test_saturation_hist_2panel(sample_arrays):
    orig, live, _ = sample_arrays
    fig = _fig()
    draw_saturation_hist(fig, orig, live)
    assert len(fig.axes) == 1


def test_saturation_hist_3panel(sample_arrays):
    orig, live, profile = sample_arrays
    fig = _fig()
    draw_saturation_hist(fig, orig, live, profile, "Cine")
    assert len(fig.axes) == 1


def test_zone_system_2panel(sample_arrays):
    orig, live, _ = sample_arrays
    fig = _fig()
    draw_zone_system(fig, orig, live)
    assert len(fig.axes) == 1


def test_zone_system_3panel(sample_arrays):
    orig, live, profile = sample_arrays
    fig = _fig()
    draw_zone_system(fig, orig, live, profile, "Cine")
    assert len(fig.axes) == 1


def test_clipping_map_2panel(sample_arrays):
    orig, live, _ = sample_arrays
    fig = _fig()
    draw_clipping_map(fig, orig, live)
    assert len(fig.axes) == 2


def test_clipping_map_3panel(sample_arrays):
    orig, live, profile = sample_arrays
    fig = _fig()
    draw_clipping_map(fig, orig, live, profile, "Cine")
    assert len(fig.axes) == 3


# ─── Plot-type registry (plots_panel) ────────────────────────────────────────

def test_plot_types_registry_complete():
    from qt_app.widgets.plots_panel import PLOT_TYPES
    assert PLOT_TYPES == [
        "None",
        "Histograms",
        "Channel Deltas",
        "Tone Curve",
        "RGB Waveform",
        "Vectorscope",
        "Saturation Dist",
        "Zone System",
        "Clipping Map",
    ]


def test_plot_dispatcher_handles_all_types(sample_arrays, params):
    from qt_app.widgets.plots_panel import PLOT_TYPES, _draw_plot

    orig, live, profile = sample_arrays
    data = {
        "orig": orig,
        "live": live,
        "profile": profile,
        "profile_name": "Cine",
        "params": params,
        "third_params": params,
    }
    for plot_type in PLOT_TYPES:
        fig = _fig()
        drawn = _draw_plot(fig, plot_type, data)
        if plot_type == "None":
            assert drawn is False, "None should return False"
            assert len(fig.axes) == 0, "None should clear the figure"
        else:
            assert drawn is True, f"{plot_type} should return True"
            assert len(fig.axes) >= 1, f"{plot_type} produced no axes"