"""Tests for CLI — invoke commands via Click's CliRunner."""

import numpy as np
from PIL import Image
import pytest
from click.testing import CliRunner

from pipeline.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def sample_image(tmp_path):
    """Create a small test JPEG and return its path."""
    arr = (np.random.rand(100, 150, 3) * 255).astype(np.uint8)
    img = Image.fromarray(arr)
    path = tmp_path / "test.jpg"
    img.save(str(path), "JPEG")
    return path


@pytest.fixture
def sample_dir(tmp_path, sample_image):
    """Directory with several images for batch testing."""
    d = tmp_path / "input"
    d.mkdir()
    arr = (np.random.rand(80, 120, 3) * 255).astype(np.uint8)
    for i in range(3):
        Image.fromarray(arr).save(str(d / f"img_{i}.jpg"), "JPEG")
    return d


# ─── CLI: process ────────────────────────────────────────────────────────────

def test_process_help(runner):
    result = runner.invoke(cli, ["process", "--help"])
    assert result.exit_code == 0
    assert "Process all images in INPUT_DIR" in result.output


def test_process_no_profile(runner, sample_dir, tmp_path):
    out = tmp_path / "output"
    result = runner.invoke(cli, ["process", str(sample_dir), "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert len(list(out.glob("*.jpg"))) == 3


def test_process_with_overrides(runner, sample_dir, tmp_path):
    out = tmp_path / "output"
    result = runner.invoke(cli, [
        "process", str(sample_dir), "-o", str(out),
        "--exposure", "0.5",
        "--contrast", "20",
        "--format", "webp",
        "--quality", "85",
    ])
    assert result.exit_code == 0
    assert len(list(out.glob("*.webp"))) == 3


def test_process_empty_dir(runner, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    out = tmp_path / "output"
    result = runner.invoke(cli, ["process", str(empty), "-o", str(out)])
    assert result.exit_code == 0
    assert "No images" in result.output


def test_process_aspect_crop(runner, sample_dir, tmp_path):
    out = tmp_path / "output"
    result = runner.invoke(cli, [
        "process", str(sample_dir), "-o", str(out), "--aspect", "1:1",
    ])
    assert result.exit_code == 0
    with Image.open(next(out.glob("*.jpg"))) as r:
        assert r.size[0] == r.size[1]  # 1:1


# ─── CLI: preview ────────────────────────────────────────────────────────────

def test_preview_help(runner):
    result = runner.invoke(cli, ["preview", "--help"])
    assert result.exit_code == 0
    assert "Generate before/after preview" in result.output
    # All override options should have help strings
    assert "--exposure" in result.output
    assert "--contrast" in result.output


def test_preview_generates_file(runner, sample_image, tmp_path):
    out = tmp_path / "preview.jpg"
    result = runner.invoke(cli, ["preview", str(sample_image), "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    with Image.open(out) as r:
        # Preview is side-by-side (width = 2 * preview_width)
        assert r.size[0] > r.size[1]  # wider than tall


def test_preview_with_overrides(runner, sample_image, tmp_path):
    out = tmp_path / "preview.jpg"
    result = runner.invoke(cli, [
        "preview", str(sample_image), "-o", str(out),
        "--exposure", "1.0",
        "--contrast", "30",
    ])
    assert result.exit_code == 0
    assert out.exists()


# ─── CLI: grid ───────────────────────────────────────────────────────────────

def test_grid_help(runner):
    result = runner.invoke(cli, ["grid", "--help"])
    assert result.exit_code == 0
    assert "grid preview" in result.output.lower()


def test_grid_generates_file(runner, sample_dir, tmp_path):
    out = tmp_path / "grid.jpg"
    result = runner.invoke(cli, ["grid", str(sample_dir), "-o", str(out), "--cols", "2"])
    assert result.exit_code == 0
    assert out.exists()


def test_grid_empty_dir(runner, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    out = tmp_path / "grid.jpg"
    result = runner.invoke(cli, ["grid", str(empty), "-o", str(out)])
    assert result.exit_code == 0
    assert "No images" in result.output


# ─── CLI: analyze ────────────────────────────────────────────────────────────

def test_analyze_help(runner):
    result = runner.invoke(cli, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "Analyze images" in result.output


def test_analyze_outputs_table(runner, sample_dir):
    result = runner.invoke(cli, ["analyze", str(sample_dir)])
    assert result.exit_code == 0
    assert "Brightness" in result.output
    assert "R/B" in result.output
    # Each image name should appear
    for i in range(3):
        assert f"img_{i}.jpg" in result.output


def test_analyze_empty_dir(runner, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(cli, ["analyze", str(empty)])
    assert result.exit_code == 0
    assert "No images" in result.output


# ─── CLI: version ────────────────────────────────────────────────────────────

def test_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output