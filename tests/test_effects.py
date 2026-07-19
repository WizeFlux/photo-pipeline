"""Tests for vignette, grain, and resize operations."""

import numpy as np
from PIL import Image

from pipeline.ops.vignette import apply_vignette
from pipeline.ops.grain import apply_grain
from pipeline.ops.resize import resize_and_save


def _uniform(value: float = 128.0, size=(50, 50)) -> np.ndarray:
    return np.full((*size, 3), value, dtype=np.float32)


# ─── Vignette ────────────────────────────────────────────────────────────────

def test_no_op_vignette():
    arr = _uniform(128)
    out = apply_vignette(arr, amount=0)
    assert np.array_equal(out, arr)


def test_dark_vignette_darkens_edges():
    arr = _uniform(180)
    out = apply_vignette(arr, amount=-50)
    center = out[25, 25].mean()
    edge = out[0, 0].mean()
    assert edge < center  # edges darker


def test_bright_vignette_brightens_edges():
    arr = _uniform(100)
    out = apply_vignette(arr, amount=50)
    center = out[25, 25].mean()
    edge = out[0, 0].mean()
    assert edge > center  # edges brighter


def test_vignette_preserves_center():
    arr = _uniform(150)
    out = apply_vignette(arr, amount=-50, size=100)  # size=100 = no effect at center
    # Center should be very close to original
    assert abs(out[25, 25, 0] - 150) < 10


def test_vignette_preserves_shape():
    arr = np.random.rand(30, 40, 3).astype(np.float32) * 255
    out = apply_vignette(arr, amount=-40, size=50, feather=50)
    assert out.shape == arr.shape


# ─── Grain ───────────────────────────────────────────────────────────────────

def test_no_op_grain():
    arr = _uniform(128)
    out = apply_grain(arr, amount=0)
    assert np.array_equal(out, arr)


def test_grain_adds_noise():
    arr = _uniform(128, (100, 100))
    out = apply_grain(arr, amount=30)
    # Output should differ from input (noise added)
    assert not np.allclose(out, arr)


def test_grain_monochrome_is_gray():
    arr = _uniform(128, (50, 50))
    out = apply_grain(arr, amount=40, monochrome=True)
    # Monochrome grain affects all channels equally
    r, g, b = out[0, 0]
    assert abs(r - g) < 5 and abs(g - b) < 5


def test_grain_in_range():
    arr = _uniform(128, (100, 100))
    out = apply_grain(arr, amount=80, size=3)
    assert np.all(out >= 0) and np.all(out <= 255)


def test_grain_preserves_shape():
    arr = np.random.rand(30, 40, 3).astype(np.float32) * 255
    out = apply_grain(arr, amount=20, size=2)
    assert out.shape == arr.shape


# ─── Resize & save ───────────────────────────────────────────────────────────

def test_resize_width(tmp_path):
    img = Image.new("RGB", (800, 600), (100, 150, 200))
    out = tmp_path / "out.jpg"
    resize_and_save(img, out, width=400)
    assert out.exists()
    with Image.open(out) as r:
        assert r.size == (400, 300)  # aspect preserved


def test_resize_height(tmp_path):
    img = Image.new("RGB", (800, 600), (100, 150, 200))
    out = tmp_path / "out.jpg"
    resize_and_save(img, out, height=150)
    assert out.exists()
    with Image.open(out) as r:
        assert r.size == (200, 150)


def test_no_resize_keeps_size(tmp_path):
    img = Image.new("RGB", (300, 200), (100, 150, 200))
    out = tmp_path / "out.jpg"
    resize_and_save(img, out, width=None, height=None)
    with Image.open(out) as r:
        assert r.size == (300, 200)


def test_save_webp(tmp_path):
    img = Image.new("RGB", (200, 200), (50, 100, 150))
    out = tmp_path / "out.webp"
    resize_and_save(img, out, fmt="webp", quality=85)
    assert out.exists()
    with Image.open(out) as r:
        assert r.format == "WEBP"


def test_save_png(tmp_path):
    img = Image.new("RGB", (200, 200), (50, 100, 150))
    out = tmp_path / "out.png"
    resize_and_save(img, out, fmt="png")
    assert out.exists()
    with Image.open(out) as r:
        assert r.format == "PNG"


def test_quality_affects_size(tmp_path):
    """Higher quality → larger file."""
    import io
    img = Image.new("RGB", (300, 300))
    # Fill with gradient so compression has something to work with
    for x in range(300):
        for y in range(300):
            img.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))

    out_low = tmp_path / "low.jpg"
    out_high = tmp_path / "high.jpg"
    resize_and_save(img, out_low, fmt="jpeg", quality=20)
    resize_and_save(img, out_high, fmt="jpeg", quality=95)
    assert out_high.stat().st_size > out_low.stat().st_size