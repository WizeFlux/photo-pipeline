"""Tests for exposure operation (EV, gamma, highlights, shadows)."""

import numpy as np

from pipeline.ops.exposure import apply_exposure


def _gray(value: float = 128.0, size=(10, 10)) -> np.ndarray:
    return np.full((*size, 3), value, dtype=np.float32)


def test_no_op_exposure():
    arr = _gray(128)
    out = apply_exposure(arr, ev=0.0, gamma=1.0, highlights=0, shadows=0)
    assert np.allclose(out, arr)


def test_positive_ev_brightens():
    arr = _gray(100)
    out = apply_exposure(arr, ev=1.0)
    assert out.mean() > arr.mean()


def test_negative_ev_darkens():
    arr = _gray(100)
    out = apply_exposure(arr, ev=-1.0)
    assert out.mean() < arr.mean()


def test_gamma_brightens_midtones():
    arr = _gray(128)
    out = apply_exposure(arr, gamma=2.0)  # gamma > 1 brightens midtones
    assert out.mean() > arr.mean()


def test_gamma_darkens_midtones():
    arr = _gray(128)
    out = apply_exposure(arr, gamma=0.5)  # gamma < 1 darkens midtones
    assert out.mean() < arr.mean()


def test_highlights_recovery_darkens_brights():
    arr = _gray(220)
    out = apply_exposure(arr, highlights=50)
    assert out.mean() < arr.mean()


def test_shadow_lift_brightens_darks():
    arr = _gray(30)
    out = apply_exposure(arr, shadows=50)
    assert out.mean() > arr.mean()


def test_output_clipped_to_range():
    arr = _gray(200)
    out = apply_exposure(arr, ev=3.0)
    assert np.all(out <= 255)
    arr2 = _gray(10)
    out2 = apply_exposure(arr2, ev=-3.0)
    assert np.all(out2 >= 0)


def test_preserves_shape():
    arr = np.random.rand(50, 80, 3).astype(np.float32) * 255
    out = apply_exposure(arr, ev=0.5, gamma=1.2, highlights=20, shadows=10)
    assert out.shape == arr.shape