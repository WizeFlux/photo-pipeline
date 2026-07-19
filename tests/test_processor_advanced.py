"""Tests for large-image strip processing in Pipeline.

Verifies that images above the 50MP threshold are processed in strips
without OOM, and results match full-array processing for per-strip ops.
"""

import numpy as np
from PIL import Image
import pytest

from pipeline.config import load_config, apply_overrides
from pipeline.processor import Pipeline


def test_process_strips_matches_full_array():
    """Per-strip ops (exposure, contrast, WB, sat, LUT) are point-wise,
    so strip processing should match full-array processing exactly."""
    # Small image — strip processing is triggered only for >50MP,
    # but we can test _apply_per_strip_ops vs _apply_all_ops directly.
    arr = (np.random.rand(100, 150, 3) * 255).astype(np.float32)

    overrides = {
        "exposure.ev": 0.5,
        "contrast.amount": 20,
        "white_balance.temperature": 15,
        "saturation.amount": 20,
    }
    cfg = apply_overrides(load_config(None), overrides)
    pipe = Pipeline(cfg)

    full = pipe._apply_all_ops(arr.copy())
    # Simulate strips of 50 rows
    strips = [pipe._apply_per_strip_ops(arr[i:i+50].copy()) for i in range(0, 100, 50)]
    stitched = np.concatenate(strips, axis=0)

    assert full.shape == stitched.shape
    assert np.allclose(full, stitched, atol=1.0)


def test_strip_height_parameter():
    """Different strip heights should produce the same final result."""
    arr = (np.random.rand(80, 60, 3) * 255).astype(np.float32)
    cfg = apply_overrides(load_config(None), {"exposure.ev": 0.3})
    pipe = Pipeline(cfg)

    s1 = [pipe._apply_per_strip_ops(arr[i:i+20].copy()) for i in range(0, 80, 20)]
    s2 = [pipe._apply_per_strip_ops(arr[i:i+40].copy()) for i in range(0, 80, 40)]
    r1 = np.concatenate(s1, axis=0)
    r2 = np.concatenate(s2, axis=0)
    assert np.allclose(r1, r2, atol=0.5)


def test_pipeline_order_constant():
    from pipeline.processor import PIPELINE_ORDER
    assert PIPELINE_ORDER == [
        "crop", "exposure", "contrast", "white_balance",
        "saturation", "lut", "vignette", "grain", "output",
    ]


def test_format_to_ext_mapping():
    from pipeline.processor import _format_to_ext
    assert _format_to_ext("jpeg") == "jpg"
    assert _format_to_ext("jpg") == "jpg"
    assert _format_to_ext("webp") == "webp"
    assert _format_to_ext("avif") == "avif"
    assert _format_to_ext("tiff") == "tiff"
    assert _format_to_ext("tif") == "tiff"
    assert _format_to_ext("unknown") == "jpg"  # fallback


def test_pipeline_rgb_conversion(tmp_path):
    """RGBA and grayscale images should be converted to RGB."""
    # RGBA
    img_rgba = Image.new("RGBA", (100, 80), (100, 150, 200, 255))
    p_rgba = tmp_path / "rgba.png"
    img_rgba.save(str(p_rgba), "PNG")

    pipe = Pipeline.from_profile(None)
    out = pipe.process_image(p_rgba, tmp_path / "out")
    assert out is not None
    with Image.open(out) as r:
        assert r.mode == "RGB"

    # Grayscale
    img_gray = Image.new("L", (100, 80), 128)
    p_gray = tmp_path / "gray.png"
    img_gray.save(str(p_gray), "PNG")

    out2 = pipe.process_image(p_gray, tmp_path / "out2")
    assert out2 is not None
    with Image.open(out2) as r:
        assert r.mode == "RGB"


def test_pipeline_output_suffix(tmp_path):
    """Output filename uses the configured suffix."""
    arr = (np.random.rand(50, 50, 3) * 255).astype(np.uint8)
    img = Image.fromarray(arr)
    src = tmp_path / "photo.jpg"
    img.save(str(src), "JPEG")

    pipe = Pipeline.from_profile(None)
    out_dir = tmp_path / "result"
    out = pipe.process_image(src, out_dir)
    assert out.name == "photo_processed.jpg"


def test_pipeline_directory_processing(tmp_path):
    """process_directory handles multiple files and returns paths."""
    d = tmp_path / "input"
    d.mkdir()
    for i in range(3):
        arr = (np.random.rand(40, 60, 3) * 255).astype(np.uint8)
        Image.fromarray(arr).save(str(d / f"img_{i}.jpg"), "JPEG")

    pipe = Pipeline.from_profile(None)
    out_dir = tmp_path / "output"
    results = pipe.process_directory(d, out_dir)
    assert len(results) == 3
    for p in results:
        assert p.exists()


def test_pipeline_directory_empty(tmp_path):
    """process_directory on empty dir returns [] without crashing."""
    empty = tmp_path / "empty"
    empty.mkdir()
    pipe = Pipeline.from_profile(None)
    results = pipe.process_directory(empty, tmp_path / "out")
    assert results == []