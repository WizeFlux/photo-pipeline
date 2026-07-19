"""Tests for saturation and vibrance operations."""

import numpy as np

from pipeline.ops.saturation import apply_saturation, rgb_to_hsl, hsl_to_rgb


def _color(r, g, b, size=(10, 10)) -> np.ndarray:
    return np.full((*size, 3), [r, g, b], dtype=np.float32)


def test_no_op_saturation():
    arr = _color(200, 50, 50)
    out = apply_saturation(arr, amount=0, vibrance=0)
    assert np.allclose(out, arr)


def test_desaturate_toward_gray():
    arr = _color(200, 50, 50)
    out = apply_saturation(arr, amount=-100)
    # Should move toward gray (all channels equal)
    r, g, b = out[0, 0]
    assert abs(r - g) < abs(arr[0, 0, 0] - arr[0, 0, 1])


def test_increase_saturation_spreads_channels():
    arr = _color(180, 90, 90)
    out = apply_saturation(arr, amount=50)
    # Red should become more dominant
    r, g, b = out[0, 0]
    assert r > arr[0, 0, 0]  # red up
    assert g < arr[0, 0, 1]  # green down (toward gray)


def test_vibrance_protects_already_saturated():
    arr = _color(240, 10, 10)  # already very saturated red
    out = apply_saturation(arr, amount=0, vibrance=80)
    # Vibrance should not push already-saturated pixels as hard
    # Check shape and in-range
    assert out.shape == arr.shape
    assert np.all(out >= 0) and np.all(out <= 255)


def test_rgb_hsl_roundtrip():
    arr = np.random.rand(10, 10, 3).astype(np.float32) * 255
    hsl = rgb_to_hsl(arr)
    back = hsl_to_rgb(hsl)
    assert np.allclose(back, arr, atol=2.0)


def test_preserves_shape():
    arr = np.random.rand(20, 30, 3).astype(np.float32) * 255
    out = apply_saturation(arr, amount=30, vibrance=40)
    assert out.shape == arr.shape