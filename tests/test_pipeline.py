"""Tests for pipeline integration."""

import numpy as np
from PIL import Image
from pipeline.config import load_config, apply_overrides, deep_merge
from pipeline.processor import Pipeline


def test_deep_merge():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 10}}
    result = deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 10, "d": 3}}


def test_load_default_config():
    config = load_config(None)
    assert "exposure" in config
    assert config["exposure"]["ev"] == 0.0
    assert config["output"]["format"] == "jpeg"


def test_apply_overrides():
    config = load_config(None)
    overrides = {"exposure.ev": 0.5, "contrast.amount": 15}
    result = apply_overrides(config, overrides)
    assert result["exposure"]["ev"] == 0.5
    assert result["contrast"]["amount"] == 15
    # Original unchanged
    assert config["exposure"]["ev"] == 0.0


def test_pipeline_no_op(tmp_path):
    """Pipeline with default config should produce same-ish image."""
    # Create test image
    img = Image.new("RGB", (200, 150), (128, 128, 128))
    input_path = tmp_path / "test.jpg"
    img.save(str(input_path), "JPEG")

    pipe = Pipeline.from_profile(None)
    output_dir = tmp_path / "output"
    out = pipe.process_image(input_path, output_dir)

    assert out is not None
    assert out.exists()

    with Image.open(out) as result:
        assert result.size == (200, 150)  # no crop, no resize


def test_pipeline_with_crop(tmp_path):
    """Pipeline with 4:3 crop."""
    img = Image.new("RGB", (400, 200), (100, 150, 200))
    input_path = tmp_path / "test.jpg"
    img.save(str(input_path), "JPEG")

    overrides = {"crop.aspect_ratio": "4:3", "output.format": "jpeg"}
    pipe = Pipeline.from_profile(None, overrides)
    out = pipe.process_image(input_path, tmp_path / "output")

    with Image.open(out) as result:
        # 400x200, crop to 4:3 → 200*4/3=266 wide, 200 tall
        assert result.size == (266, 200)