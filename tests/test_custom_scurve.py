"""Tests for custom S-Curve integration in the GPU processing pipeline.

The interactive S-Curve editor produces 256 y-values that override the
sigmoid s_curve parameter when present in the params dict.
"""

import numpy as np
import pytest

torch = pytest.importorskip("torch")
from pipeline.gpu_ops import gpu_process
from qt_app.state import PARAM_DEFAULTS, params_from_values


def _gray(value=128, size=(10, 10)):
    return np.full((*size, 3), value, dtype=np.float32)


def test_no_custom_scurve_uses_sigmoid():
    """Without scurve_custom, the sigmoid s_curve param applies."""
    arr = _gray(128)
    params = params_from_values(PARAM_DEFAULTS)
    params["s_curve"] = 50
    result = gpu_process(arr, params)
    assert result.shape == arr.shape


def test_custom_scurve_identity_is_noop():
    """Identity custom curve (y=x) should not change the image."""
    arr = _gray(100)
    params = params_from_values(PARAM_DEFAULTS)
    params["scurve_custom"] = np.arange(256, dtype=np.float32)
    result = gpu_process(arr, params)
    # Identity curve → output should match input (within rounding)
    assert np.allclose(result, arr, atol=1.5)


def test_custom_scurve_brightens():
    """A curve that lifts midtones should brighten a midtone input."""
    arr = _gray(128)
    params = params_from_values(PARAM_DEFAULTS)
    # Curve that maps 128 → 200
    curve = np.arange(256, dtype=np.float32)
    curve[128] = 200
    params["scurve_custom"] = curve
    result = gpu_process(arr, params)
    # The pixel at value 128 should now be near 200
    assert result[0, 0, 0] > 150


def test_custom_scurve_darkens():
    """A curve that crushes midtones should darken a midtone input."""
    arr = _gray(128)
    params = params_from_values(PARAM_DEFAULTS)
    curve = np.arange(256, dtype=np.float32)
    curve[128] = 50
    params["scurve_custom"] = curve
    result = gpu_process(arr, params)
    assert result[0, 0, 0] < 100


def test_custom_scurve_overrides_sigmoid():
    """When scurve_custom is present, it takes precedence over s_curve."""
    # Use a non-midtone value so the sigmoid actually changes it
    arr = _gray(180)
    params_with_sigmoid = params_from_values(PARAM_DEFAULTS)
    params_with_sigmoid["s_curve"] = 100  # max sigmoid
    result_sigmoid = gpu_process(arr, params_with_sigmoid)

    params_with_custom = dict(params_with_sigmoid)
    params_with_custom["scurve_custom"] = np.arange(256, dtype=np.float32)
    result_custom = gpu_process(arr, params_with_custom)

    # Sigmoid should change 180 somewhat; custom identity should keep it at 180
    assert abs(result_sigmoid[0, 0, 0] - 180) > 3.0
    assert abs(result_custom[0, 0, 0] - 180) < 2


def test_custom_scurve_preserves_shape():
    arr = np.random.rand(30, 40, 3).astype(np.float32) * 255
    params = params_from_values(PARAM_DEFAULTS)
    params["scurve_custom"] = np.arange(256, dtype=np.float32)
    result = gpu_process(arr, params)
    assert result.shape == arr.shape


def test_custom_scurve_clipped_to_range():
    arr = _gray(200)
    params = params_from_values(PARAM_DEFAULTS)
    # Curve that maps everything to 300 (above 255)
    curve = np.full(256, 300.0, dtype=np.float32)
    params["scurve_custom"] = curve
    result = gpu_process(arr, params)
    assert np.all(result <= 255)
    assert np.all(result >= 0)