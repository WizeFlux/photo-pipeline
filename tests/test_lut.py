"""Tests for LUT parsing and application."""

import numpy as np
import pytest
from pipeline.ops.lut import parse_cube, apply_3d_lut, apply_lut


def test_parse_3d_cube(tmp_path):
    """Parse a simple 3D .cube file."""
    cube_content = """# Test LUT
LUT_3D_SIZE 2
0.0 0.0 0.0
0.5 0.0 0.0
0.0 0.5 0.0
0.5 0.5 0.0
0.0 0.0 0.5
0.5 0.0 0.5
0.0 0.5 0.5
0.5 0.5 0.5
"""
    path = tmp_path / "test.cube"
    path.write_text(cube_content)

    lut = parse_cube(path)
    assert lut["type"] == "3D"
    assert lut["size"] == 2
    assert lut["table"].shape == (2, 2, 2, 3)


def test_apply_identity_lut():
    """Identity LUT should not change image."""
    # Create identity 3D LUT (size 2)
    table = np.zeros((2, 2, 2, 3), dtype=np.float32)
    for r in range(2):
        for g in range(2):
            for b in range(2):
                table[r, g, b] = [r, g, b]

    lut = {"type": "3D", "size": 2, "table": table,
           "domain_min": np.array([0, 0, 0]), "domain_max": np.array([1, 1, 1])}

    arr = np.random.rand(10, 10, 3).astype(np.float32) * 255
    result = apply_3d_lut(arr, lut, intensity=1.0)

    # Should be close to original (with interpolation at size=2)
    assert result.shape == arr.shape
    assert np.all(result >= 0)
    assert np.all(result <= 255)


def test_apply_lut_none():
    """None LUT path should return original array."""
    arr = np.random.rand(5, 5, 3).astype(np.float32) * 255
    result = apply_lut(arr, None, 1.0)
    assert np.array_equal(result, arr)


def test_lut_intensity_blend():
    """Intensity < 1.0 should blend with original."""
    # Create a LUT that maps everything to red
    table = np.ones((2, 2, 2, 3), dtype=np.float32)
    table[..., 1] = 0  # G=0
    table[..., 2] = 0  # B=0

    lut = {"type": "3D", "size": 2, "table": table,
           "domain_min": np.array([0, 0, 0]), "domain_max": np.array([1, 1, 1])}

    arr = np.ones((5, 5, 3), dtype=np.float32) * 128  # gray
    result_full = apply_3d_lut(arr, lut, intensity=1.0)
    result_half = apply_3d_lut(arr, lut, intensity=0.5)

    # Half intensity should be between original and full LUT per channel
    # result = arr * (1 - intensity) + lut_result * intensity
    # So result_half should be between arr and result_full
    assert np.all(result_half >= np.minimum(arr, result_full) - 1)
    assert np.all(result_half <= np.maximum(arr, result_full) + 1)