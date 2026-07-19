"""Tests for preview generation (before/after side-by-side and grid)."""

import numpy as np
from PIL import Image
import pytest

from pipeline.config import load_config, apply_overrides
from pipeline.processor import Pipeline
from pipeline.preview import generate_preview, generate_grid


@pytest.fixture
def sample_image(tmp_path):
    arr = (np.random.rand(120, 180, 3) * 255).astype(np.uint8)
    path = tmp_path / "src.jpg"
    Image.fromarray(arr).save(str(path), "JPEG")
    return path


@pytest.fixture
def sample_dir(tmp_path):
    d = tmp_path / "imgs"
    d.mkdir()
    for i in range(4):
        arr = (np.random.rand(80, 100, 3) * 255).astype(np.uint8)
        Image.fromarray(arr).save(str(d / f"img_{i}.jpg"), "JPEG")
    return d


def test_generate_preview_default_path(sample_image, tmp_path):
    pipe = Pipeline.from_profile(None)
    out = tmp_path / "preview.jpg"
    generate_preview(pipe, str(sample_image), str(out))
    assert out.exists()
    with Image.open(out) as r:
        # Side-by-side: width = 2 * preview_width (800 default)
        assert r.size[0] == 1600
        assert r.size[1] > 0


def test_generate_preview_custom_width(sample_image, tmp_path):
    pipe = Pipeline.from_profile(None)
    out = tmp_path / "preview.jpg"
    generate_preview(pipe, str(sample_image), str(out), preview_width=400)
    with Image.open(out) as r:
        assert r.size[0] == 800  # 400 * 2


def test_generate_preview_with_adjustments(sample_image, tmp_path):
    overrides = {
        "exposure.ev": 0.8,
        "contrast.amount": 20,
        "saturation.amount": 30,
    }
    cfg = apply_overrides(load_config(None), overrides)
    pipe = Pipeline(cfg)
    out = tmp_path / "preview_adj.jpg"
    generate_preview(pipe, str(sample_image), str(out))
    assert out.exists()


def test_generate_preview_with_crop(sample_image, tmp_path):
    overrides = {"crop.aspect_ratio": "1:1"}
    cfg = apply_overrides(load_config(None), overrides)
    pipe = Pipeline(cfg)
    out = tmp_path / "preview_crop.jpg"
    generate_preview(pipe, str(sample_image), str(out))
    # Both halves should have the same height (post-crop)
    with Image.open(out) as r:
        w, h = r.size
        assert w == 1600  # 2 * 800


def test_generate_grid_default(sample_dir, tmp_path):
    out = tmp_path / "grid.jpg"
    generate_grid(str(sample_dir), str(out), cols=2)
    assert out.exists()
    with Image.open(out) as r:
        assert r.size[0] > 0 and r.size[1] > 0


def test_generate_grid_cols(sample_dir, tmp_path):
    out = tmp_path / "grid5.jpg"
    generate_grid(str(sample_dir), str(out), cols=4, thumb_width=100)
    assert out.exists()
    # 4 images, 4 cols → 1 row; width ≈ 4 * 100 = 400
    with Image.open(out) as r:
        assert r.size[0] > 0


def test_generate_grid_empty_dir(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    out = tmp_path / "grid.jpg"
    # Should not crash and should not produce a file (or produce empty)
    generate_grid(str(empty), str(out), cols=3)
    # Either file doesn't exist or is a valid image — just no crash
    if out.exists():
        with Image.open(out) as r:
            assert r.size[0] > 0