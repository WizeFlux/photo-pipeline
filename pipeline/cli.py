"""CLI entry point for Photo Pipeline.

Usage:
    python -m pipeline process <input_dir> -o <output_dir> -p profiles/default.yaml
    python -m pipeline preview <input_file> -p profiles/default.yaml
    python -m pipeline analyze <input_dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .config import load_config, apply_overrides
from .processor import Pipeline
from .preview import generate_preview, generate_grid


@click.group()
@click.version_option("0.1.0")
def cli():
    """Photo Pipeline — batch photo processing with LUTs and color grading."""


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("-o", "--output-dir", "output_dir", required=True, help="Output directory")
@click.option("-p", "--profile", "profile", default=None, help="YAML profile path")
@click.option("--exposure", default=None, type=float, help="Override exposure EV")
@click.option("--contrast", default=None, type=int, help="Override contrast amount")
@click.option("--temperature", default=None, type=int, help="Override WB temperature")
@click.option("--tint", default=None, type=int, help="Override WB tint")
@click.option("--saturation", default=None, type=int, help="Override saturation")
@click.option("--vibrance", default=None, type=int, help="Override vibrance")
@click.option("--lut", "lut_path", default=None, help="Override LUT path")
@click.option("--lut-intensity", default=None, type=float, help="Override LUT intensity")
@click.option("--aspect", default=None, help="Override crop aspect ratio (e.g. 4:3)")
@click.option("--width", default=None, type=int, help="Override output width")
@click.option("--format", "fmt", default=None, help="Override output format (jpeg/webp/avif)")
@click.option("--quality", default=None, type=int, help="Override output quality")
@click.option("--vignette", default=None, type=int, help="Override vignette amount")
@click.option("--grain", default=None, type=int, help="Override grain amount")
def process(
    input_dir, output_dir, profile,
    exposure, contrast, temperature, tint, saturation, vibrance,
    lut_path, lut_intensity, aspect, width, fmt, quality, vignette, grain,
):
    """Process all images in INPUT_DIR."""
    # Build overrides from CLI options
    overrides = {}
    if exposure is not None:
        overrides["exposure.ev"] = exposure
    if contrast is not None:
        overrides["contrast.amount"] = contrast
    if temperature is not None:
        overrides["white_balance.temperature"] = temperature
    if tint is not None:
        overrides["white_balance.tint"] = tint
    if saturation is not None:
        overrides["saturation.amount"] = saturation
    if vibrance is not None:
        overrides["saturation.vibrance"] = vibrance
    if lut_path is not None:
        overrides["lut.path"] = lut_path
    if lut_intensity is not None:
        overrides["lut.intensity"] = lut_intensity
    if aspect is not None:
        overrides["crop.aspect_ratio"] = aspect
    if width is not None:
        overrides["output.width"] = width
    if fmt is not None:
        overrides["output.format"] = fmt
    if quality is not None:
        overrides["output.quality"] = quality
    if vignette is not None:
        overrides["vignette.amount"] = vignette
    if grain is not None:
        overrides["grain.amount"] = grain

    pipe = Pipeline.from_profile(profile, overrides if overrides else None)

    print(f"Processing: {input_dir} → {output_dir}")
    if profile:
        print(f"Profile: {profile}")
    if overrides:
        print(f"Overrides: {overrides}")

    results = pipe.process_directory(input_dir, output_dir)

    print(f"\n✅ Done: {len(results)} images processed → {output_dir}")


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("-o", "--output", "output", default=None, help="Output path for preview")
@click.option("-p", "--profile", "profile", default=None, help="YAML profile path")
@click.option("--exposure", default=None, type=float)
@click.option("--contrast", default=None, type=int)
@click.option("--temperature", default=None, type=int)
@click.option("--tint", default=None, type=int)
@click.option("--saturation", default=None, type=int)
@click.option("--lut", "lut_path", default=None)
@click.option("--aspect", default=None)
@click.option("--width", default=None, type=int)
def preview(input_file, output, profile, **kwargs):
    """Generate before/after preview for a single image."""
    overrides = {}
    for key, val in kwargs.items():
        if val is not None:
            mapping = {
                "exposure": "exposure.ev",
                "contrast": "contrast.amount",
                "temperature": "white_balance.temperature",
                "tint": "white_balance.tint",
                "saturation": "saturation.amount",
                "lut_path": "lut.path",
                "aspect": "crop.aspect_ratio",
                "width": "output.width",
            }
            if key in mapping:
                overrides[mapping[key]] = val

    pipe = Pipeline.from_profile(profile, overrides if overrides else None)

    if output is None:
        output = str(Path(input_file).with_suffix("")) + "_preview.jpg"

    generate_preview(pipe, input_file, output)
    print(f"✅ Preview saved: {output}")


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
@click.option("-o", "--output", "output", default=None, help="Output grid path")
@click.option("--cols", default=5, type=int, help="Number of columns")
def grid(input_dir, output, cols):
    """Generate a grid preview of all images in directory."""
    if output is None:
        output = str(Path(input_dir)) + "_grid.jpg"
    generate_grid(input_dir, output, cols)
    print(f"✅ Grid saved: {output}")


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True))
def analyze(input_dir):
    """Analyze images: show brightness, color temperature, dimensions."""
    from PIL import Image
    import numpy as np

    input_dir = Path(input_dir)
    files = sorted([
        f for f in input_dir.iterdir()
        if f.suffix.lower() in (".tiff", ".tif", ".jpg", ".jpeg", ".png", ".webp")
    ])

    if not files:
        print(f"No images in {input_dir}")
        return

    print(f"{'File':<50} {'Size':>10} {'WxH':>15} {'Brightness':>12} {'R/B':>6}")
    print("-" * 100)

    for f in files:
        with Image.open(f) as img:
            small = img.resize((200, 200))
            arr = np.array(small, dtype=np.float64)
            mean = arr.mean(axis=(0, 1))
            brightness = 0.299 * mean[0] + 0.587 * mean[1] + 0.114 * mean[2]
            rb = mean[0] / max(mean[2], 1)
            size_mb = f.stat().st_size // 1024 // 1024
            w, h = img.size
            print(f"{f.name:<50} {size_mb:>8}MB {f'{w}x{h}':>15} {brightness:>10.1f} {rb:>6.2f}")


def main():
    cli()


if __name__ == "__main__":
    main()