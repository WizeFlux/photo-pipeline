"""Tests for state.py — params mapping, profile I/O, tone curves, stats."""

import numpy as np
import pytest

from qt_app.state import (
    PARAM_DEFAULTS,
    compute_stats,
    compute_tone_curve,
    curve_from_params,
    params_from_config,
    params_from_values,
    params_to_config,
    stats_rows,
)


def test_param_defaults_keys():
    # gamma, contrast_amount, s_curve, black_point, white_point remain in
    # PARAM_DEFAULTS (processing still needs them) even though their sliders
    # were removed from the UI.
    expected = {
        "ev", "gamma", "highlights", "shadows",
        "contrast_amount", "s_curve", "black_point", "white_point",
        "temperature", "tint", "saturation", "vibrance",
        "lut_path", "lut_intensity",
    }
    assert set(PARAM_DEFAULTS.keys()) == expected


def test_params_from_values_fills_missing_contrast_keys():
    """With contrast sliders removed, params_from_values should still
    produce a complete params dict by falling back to PARAM_DEFAULTS."""
    values = {
        "ev": 0.5, "highlights": 10, "shadows": 20,
        "temperature": 15, "tint": -5,
        "saturation": 30, "vibrance": 10,
        "lut_path": "None", "lut_intensity": 1.0,
    }
    params = params_from_values(values)
    # Removed-slider keys should fall back to defaults
    assert params["gamma"] == 1.0
    assert params["contrast_amount"] == 0
    assert params["s_curve"] == 0
    assert params["black_point"] == 0
    assert params["white_point"] == 255
    # Provided keys should pass through
    assert params["ev"] == 0.5
    assert params["temperature"] == 15


def test_params_from_values_passes_through():
    values = {**PARAM_DEFAULTS, "ev": 0.5, "contrast_amount": 20, "lut_path": "None"}
    params = params_from_values(values)
    assert params["ev"] == 0.5
    assert params["contrast_amount"] == 20
    assert params["lut_path"] is None  # "None" string normalized


def test_params_from_values_empty_lut():
    values = {**PARAM_DEFAULTS, "lut_path": ""}
    params = params_from_values(values)
    assert params["lut_path"] is None


def test_params_from_config_roundtrip():
    cfg = {
        "exposure": {"ev": -0.3, "gamma": 1.2, "highlights": 10, "shadows": 20},
        "contrast": {"amount": 15, "s_curve": 30, "black_point": 5, "white_point": 250},
        "white_balance": {"temperature": 12, "tint": -5},
        "saturation": {"amount": 10, "vibrance": 25},
        "lut": {"path": "luts/x.cube", "intensity": 0.7},
    }
    params = params_from_config(cfg)
    assert params["ev"] == -0.3
    assert params["gamma"] == 1.2
    assert params["contrast_amount"] == 15
    assert params["temperature"] == 12
    assert params["vibrance"] == 25
    assert params["lut_path"] == "luts/x.cube"
    assert params["lut_intensity"] == 0.7


def test_params_to_config_roundtrip():
    params = {**PARAM_DEFAULTS, "ev": 0.8, "temperature": 15, "lut_path": "a.cube"}
    cfg = params_to_config(params)
    back = params_from_config(cfg)
    for k in params:
        assert back[k] == params[k], f"mismatch on {k}"


def test_params_to_config_saves_scurve_custom():
    """params_to_config should serialize scurve_custom as a list."""
    curve = np.arange(256, dtype=np.float32)
    params = {**PARAM_DEFAULTS, "scurve_custom": curve}
    cfg = params_to_config(params)
    assert "scurve_custom" in cfg
    assert isinstance(cfg["scurve_custom"], list)
    assert len(cfg["scurve_custom"]) == 256


def test_params_from_config_loads_scurve_custom():
    """params_from_config should load scurve_custom back into numpy array."""
    curve = np.arange(256, dtype=np.float32) * 0.5
    params = {**PARAM_DEFAULTS, "scurve_custom": curve}
    cfg = params_to_config(params)
    back = params_from_config(cfg)
    assert "scurve_custom" in back
    assert isinstance(back["scurve_custom"], np.ndarray)
    np.testing.assert_array_almost_equal(back["scurve_custom"], curve)


def test_scurve_custom_roundtrip_via_yaml(tmp_path):
    """Save → load profile should preserve scurve_custom exactly."""
    import yaml
    curve = np.arange(256, dtype=np.float32)
    # Modify a few points so it's not identity
    curve[64] = 80
    curve[128] = 180
    curve[192] = 220
    params = {**PARAM_DEFAULTS, "scurve_custom": curve, "ev": 0.5}
    cfg = params_to_config(params)
    # Write to YAML and read back
    yaml_path = tmp_path / "test_profile.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)
    with open(yaml_path) as f:
        loaded_cfg = yaml.safe_load(f)
    back = params_from_config(loaded_cfg)
    assert "scurve_custom" in back
    assert isinstance(back["scurve_custom"], np.ndarray)
    np.testing.assert_array_almost_equal(back["scurve_custom"], curve, decimal=3)
    assert back["ev"] == 0.5


def test_params_to_config_no_scurve_when_absent():
    """params_to_config should not include scurve_custom when it's None."""
    params = {**PARAM_DEFAULTS}
    cfg = params_to_config(params)
    assert "scurve_custom" not in cfg


def test_params_from_config_no_scurve_when_absent():
    """params_from_config should not add scurve_custom when missing in cfg."""
    cfg = params_to_config({**PARAM_DEFAULTS})
    back = params_from_config(cfg)
    assert "scurve_custom" not in back


# ─── Tone curve ──────────────────────────────────────────────────────────────

def test_tone_curve_identity():
    x, y = compute_tone_curve(ev=0.0, gamma=1.0, contrast=0, s_curve=0,
                              black_point=0, white_point=255)
    assert np.allclose(x, y, atol=0.5)


def test_tone_curve_positive_ev_shifts_up():
    x, y = compute_tone_curve(ev=1.0, gamma=1.0, contrast=0, s_curve=0,
                              black_point=0, white_point=255)
    assert y[128] > x[128]


def test_tone_curve_gamma_above_one_brightens_midtones():
    _, y = compute_tone_curve(ev=0.0, gamma=2.0, contrast=0, s_curve=0,
                              black_point=0, white_point=255)
    assert y[128] > 128


def test_tone_curve_clips_to_0_255():
    _, y = compute_tone_curve(ev=3.0, gamma=1.0, contrast=50, s_curve=50,
                              black_point=10, white_point=245)
    assert y.min() >= 0
    assert y.max() <= 255


def test_curve_from_params_matches_compute():
    params = {"ev": 0.5, "gamma": 1.3, "contrast_amount": 20, "s_curve": 10,
              "black_point": 5, "white_point": 250}
    _, y1 = curve_from_params(params)
    _, y2 = compute_tone_curve(0.5, 1.3, 20, 10, 5, 250)
    assert np.allclose(y1, y2)


# ─── Stats ───────────────────────────────────────────────────────────────────

def _img(value=128, size=(20, 20)):
    return np.full((*size, 3), value, dtype=np.uint8)


def test_compute_stats_uniform():
    arr = _img(128)
    s = compute_stats(arr)
    assert abs(s["Brightness"] - 128.0) < 0.01
    assert s["B_std"] == 0.0
    assert s["Range"] == 0.0


def test_compute_stats_keys():
    arr = np.random.rand(30, 40, 3).astype(np.uint8) * 255
    s = compute_stats(arr)
    expected = {
        "Brightness", "B_median", "B_std", "B_min", "B_max", "Range",
        "R_mean", "G_mean", "B_mean",
        "R_std", "G_std", "B_std",
        "R/B", "R/G", "G/B",
        "Saturation", "SNR",
        "Shadows%", "Midtones%", "Highlights%",
        "Clip_S%", "Clip_H%",
    }
    assert set(s.keys()) == expected


def test_stats_rows_with_profile():
    orig = _img(100)
    live = _img(150)
    prof = _img(200)
    rows = stats_rows(orig, live, prof)
    assert len(rows) > 0
    assert "Original" in rows[0]
    assert "Live" in rows[0]
    assert "Profile" in rows[0]


def test_stats_rows_without_profile():
    orig = _img(100)
    live = _img(150)
    rows = stats_rows(orig, live, None)
    assert "Profile" not in rows[0]