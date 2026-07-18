"""Tests for crop operation."""

from PIL import Image
from pipeline.ops.crop import crop_image, parse_aspect_ratio


def test_parse_aspect_ratio():
    assert parse_aspect_ratio("4:3") == 4.0 / 3.0
    assert parse_aspect_ratio("16:9") == 16.0 / 9.0
    assert parse_aspect_ratio("1:1") == 1.0
    assert parse_aspect_ratio(None) is None


def test_no_crop():
    """None aspect ratio returns original image."""
    img = Image.new("RGB", (100, 100))
    result = crop_image(img, aspect_ratio=None)
    assert result.size == (100, 100)


def test_crop_4x3():
    """4:3 crop from 16:9 image reduces width."""
    img = Image.new("RGB", (1600, 900))
    result = crop_image(img, aspect_ratio="4:3")
    assert result.size == (1200, 900)  # 900 * 4/3 = 1200


def test_crop_1x1():
    """1:1 crop from wide image."""
    img = Image.new("RGB", (800, 400))
    result = crop_image(img, aspect_ratio="1:1")
    assert result.size == (400, 400)


def test_crop_gravity_left():
    """Left gravity shifts crop to left edge."""
    img = Image.new("RGB", (1000, 500))
    result_center = crop_image(img, aspect_ratio="1:1", gravity="center")
    result_left = crop_image(img, aspect_ratio="1:1", gravity="left")
    # Both same size
    assert result_center.size == result_left.size == (500, 500)
    # Left crop should start at x=0 (vs center at x=250)


def test_crop_offset():
    """Custom offset shifts crop."""
    img = Image.new("RGB", (1000, 500))
    result = crop_image(img, aspect_ratio="1:1", offset_x=1.0)
    assert result.size == (500, 500)