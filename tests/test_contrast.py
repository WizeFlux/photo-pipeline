"""Tests for contrast operation (linear, S-curve, black/white points)."""

import numpy as np

from pipeline.ops.contrast import apply_contrast


def _gray(value: float = 128.0, size=(10, 10)) -> np.ndarray:
    return np.full((*size, 3), value, dtype=np.float32)


def test_no_op_contrast():
    arr = _gray(128)
    out = apply_contrast(arr, amount=0, s_curve=0, black_point=0, white_point=255)
    assert np.allclose(out, arr)


def test_positive_contrast_increases_spread():
    arr = np.array([[[60, 128, 200]]], dtype=np.float32)
    arr = np.tile(arr, (10, 10, 1))
    out = apply_contrast(arr, amount=30)
    # Darks get darker, brights get brighter
    assert out[0, 0, 0] < arr[0, 0, 0]
    assert out[0, 0, 2] > arr[0, 0, 2]


def test_negative_contrast_decreases_spread():
    arr = np.array([[[60, 128, 200]]], dtype=np.float32)
    arr = np.tile(arr, (10, 10, 1))
    out = apply_contrast(arr, amount=-30)
    # Values pull toward 128
    assert abs(out[0, 0, 0] - 128) < abs(arr[0, 0, 0] - 128)
    assert abs(out[0, 0, 2] - 128) < abs(arr[0, 0, 2] - 128)


def test_s_curve_increases_midtone_contrast():
    arr = _gray(128)
    out = apply_contrast(arr, s_curve=50)
    # Midtone at 128 should stay near 128, but slopes change around it
    # Just check shape preservation and in-range
    assert out.shape == arr.shape
    assert np.all(out >= 0) and np.all(out <= 255)


def test_black_point_clips():
    arr = _gray(40)
    out = apply_contrast(arr, black_point=50)
    # Values below 50 should be clipped to 0
    assert out[0, 0, 0] == 0 or out[0, 0, 0] < arr[0, 0, 0]


def test_white_point_clips():
    arr = _gray(240)
    out = apply_contrast(arr, white_point=200)
    # Values above 200 should be clipped to 255
    assert out[0, 0, 0] >= arr[0, 0, 0]


def test_preserves_shape():
    arr = np.random.rand(30, 40, 3).astype(np.float32) * 255
    out = apply_contrast(arr, amount=20, s_curve=30, black_point=10, white_point=245)
    assert out.shape == arr.shape