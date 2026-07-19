"""Tests for white balance operation (temperature, tint)."""

import numpy as np

from pipeline.ops.white_balance import apply_white_balance


def _gray(value: float = 128.0, size=(10, 10)) -> np.ndarray:
    return np.full((*size, 3), value, dtype=np.float32)


def test_no_op_wb():
    arr = _gray(128)
    out = apply_white_balance(arr, temperature=0, tint=0)
    assert np.allclose(out, arr)


def test_warm_temperature_increases_red():
    arr = _gray(128)
    out = apply_white_balance(arr, temperature=50)
    assert out[0, 0, 0] > arr[0, 0, 0]  # R up
    assert out[0, 0, 2] < arr[0, 0, 2]  # B down


def test_cool_temperature_increases_blue():
    arr = _gray(128)
    out = apply_white_balance(arr, temperature=-50)
    assert out[0, 0, 0] < arr[0, 0, 0]  # R down
    assert out[0, 0, 2] > arr[0, 0, 2]  # B up


def test_magenta_tint_decreases_green():
    arr = _gray(128)
    out = apply_white_balance(arr, tint=50)
    # Magenta: R and B up, G down
    assert out[0, 0, 1] < arr[0, 0, 1]  # G down


def test_green_tint_increases_green():
    arr = _gray(128)
    out = apply_white_balance(arr, tint=-50)
    assert out[0, 0, 1] > arr[0, 0, 1]  # G up


def test_output_in_range():
    arr = np.random.rand(20, 30, 3).astype(np.float32) * 255
    out = apply_white_balance(arr, temperature=80, tint=80)
    assert np.all(out >= 0) and np.all(out <= 255)


def test_preserves_shape():
    arr = np.random.rand(15, 25, 3).astype(np.float32) * 255
    out = apply_white_balance(arr, temperature=20, tint=-15)
    assert out.shape == arr.shape