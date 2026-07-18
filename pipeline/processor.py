"""Main pipeline orchestrator — applies all ops in order."""

from __future__ import annotations

import gc
from pathlib import Path

import numpy as np
from PIL import Image

from .config import load_config, apply_overrides
from .ops.crop import crop_image
from .ops.exposure import apply_exposure
from .ops.contrast import apply_contrast
from .ops.white_balance import apply_white_balance
from .ops.saturation import apply_saturation
from .ops.lut import apply_lut
from .ops.vignette import apply_vignette
from .ops.grain import apply_grain
from .ops.resize import resize_and_save


# Processing order (matches slider order in photo editors)
PIPELINE_ORDER = [
    "crop",
    "exposure",
    "contrast",
    "white_balance",
    "saturation",
    "lut",
    "vignette",
    "grain",
    "output",
]


def _format_to_ext(fmt: str) -> str:
    """Convert format name to file extension."""
    return {"jpeg": "jpg", "jpg": "jpg", "webp": "webp", "avif": "avif", "tiff": "tiff", "tif": "tiff"}.get(fmt.lower(), "jpg")


class Pipeline:
    """Batch photo processing pipeline.

    Loads config from YAML profile, applies operations in order,
    saves results in specified format.
    """

    def __init__(self, config: dict):
        """Initialize with a merged config dict (from load_config)."""
        self.config = config

    @classmethod
    def from_profile(cls, profile_path: str | Path | None = None, overrides: dict | None = None):
        """Create pipeline from YAML profile + optional CLI overrides."""
        config = load_config(profile_path)
        if overrides:
            config = apply_overrides(config, overrides)
        return cls(config)

    def process_image(self, input_path: str | Path, output_dir: str | Path) -> Path | None:
        """Process a single image file.

        Args:
            input_path: Path to input image.
            output_dir: Directory for output file.

        Returns:
            Path to saved output, or None on failure.
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        cfg = self.config

        # Step 1: Load and crop (PIL, memory-efficient)
        img = Image.open(input_path)

        # Convert to RGB if needed (handle RGBA, grayscale, CMYK)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        elif img.mode == "L":
            img = img.convert("RGB")

        # Crop first — reduces data for subsequent numpy ops
        crop_cfg = cfg.get("crop", {})
        img = crop_image(
            img,
            aspect_ratio=crop_cfg.get("aspect_ratio"),
            gravity=crop_cfg.get("gravity", "center"),
            offset_x=crop_cfg.get("offset_x", 0.0),
            offset_y=crop_cfg.get("offset_y", 0.0),
        )

        # Step 2: Convert to numpy for pixel ops
        # Process in strips if image is very large (>50MP)
        w, h = img.size
        total_px = w * h

        if total_px > 50_000_000:
            result = self._process_strips(img)
        else:
            arr = np.array(img, dtype=np.float32)
            del img
            result = self._apply_all_ops(arr)
            del arr
            gc.collect()

        # Convert back to PIL
        result_img = Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), "RGB")
        del result
        gc.collect()

        # Step 3: Resize and save
        output_cfg = cfg.get("output", {})
        suffix = output_cfg.get("suffix", "_processed")
        stem = input_path.stem
        out_name = f"{stem}{suffix}.{_format_to_ext(output_cfg.get('format', 'jpeg'))}"
        out_path = output_dir / out_name

        resize_and_save(
            result_img,
            out_path,
            width=output_cfg.get("width"),
            height=output_cfg.get("height"),
            fmt=output_cfg.get("format", "jpeg"),
            quality=output_cfg.get("quality", 90),
        )

        del result_img
        gc.collect()

        return out_path

    def _apply_all_ops(self, arr: np.ndarray) -> np.ndarray:
        """Apply all pixel operations to a full array."""
        cfg = self.config

        # Exposure
        exp_cfg = cfg.get("exposure", {})
        arr = apply_exposure(
            arr,
            ev=exp_cfg.get("ev", 0.0),
            gamma=exp_cfg.get("gamma", 1.0),
            highlights=exp_cfg.get("highlights", 0),
            shadows=exp_cfg.get("shadows", 0),
        )

        # Contrast
        con_cfg = cfg.get("contrast", {})
        arr = apply_contrast(
            arr,
            amount=con_cfg.get("amount", 0),
            s_curve=con_cfg.get("s_curve", 0),
            black_point=con_cfg.get("black_point", 0),
            white_point=con_cfg.get("white_point", 255),
        )

        # White balance
        wb_cfg = cfg.get("white_balance", {})
        arr = apply_white_balance(
            arr,
            temperature=wb_cfg.get("temperature", 0),
            tint=wb_cfg.get("tint", 0),
        )

        # Saturation
        sat_cfg = cfg.get("saturation", {})
        arr = apply_saturation(
            arr,
            amount=sat_cfg.get("amount", 0),
            vibrance=sat_cfg.get("vibrance", 0),
        )

        # LUT
        lut_cfg = cfg.get("lut", {})
        arr = apply_lut(
            arr,
            lut_path=lut_cfg.get("path"),
            intensity=lut_cfg.get("intensity", 1.0),
        )

        # Vignette
        vig_cfg = cfg.get("vignette", {})
        arr = apply_vignette(
            arr,
            amount=vig_cfg.get("amount", 0),
            size=vig_cfg.get("size", 50),
            feather=vig_cfg.get("feather", 50),
            roundness=vig_cfg.get("roundness", 0),
        )

        # Grain
        grain_cfg = cfg.get("grain", {})
        arr = apply_grain(
            arr,
            amount=grain_cfg.get("amount", 0),
            size=grain_cfg.get("size", 1),
            monochrome=grain_cfg.get("monochrome", True),
        )

        return arr

    def _process_strips(self, img: Image.Image, strip_height: int = 512) -> np.ndarray:
        """Process very large images in horizontal strips to avoid OOM.

        Vignette and grain are applied to the full image after stitching
        (they need global context).
        """
        w, h = img.size
        cfg = self.config

        # Ops that can work per-strip (don't need global context)
        # LUT needs special handling for 3D (it's per-pixel, so strips are fine)
        strips = []

        for y0 in range(0, h, strip_height):
            y1 = min(y0 + strip_height, h)
            strip = img.crop((0, y0, w, y1))
            arr = np.array(strip, dtype=np.float32)
            del strip

            # Apply per-strip ops: exposure, contrast, WB, saturation, LUT
            # (vignette and grain need full image)
            arr = self._apply_per_strip_ops(arr)
            strips.append(arr)
            gc.collect()

        # Stitch
        result = np.concatenate(strips, axis=0)
        del strips
        gc.collect()

        # Apply global ops: vignette, grain
        vig_cfg = cfg.get("vignette", {})
        result = apply_vignette(
            result,
            amount=vig_cfg.get("amount", 0),
            size=vig_cfg.get("size", 50),
            feather=vig_cfg.get("feather", 50),
            roundness=vig_cfg.get("roundness", 0),
        )

        grain_cfg = cfg.get("grain", {})
        result = apply_grain(
            result,
            amount=grain_cfg.get("amount", 0),
            size=grain_cfg.get("size", 1),
            monochrome=grain_cfg.get("monochrome", True),
        )

        return result

    def _apply_per_strip_ops(self, arr: np.ndarray) -> np.ndarray:
        """Apply ops that work per-strip (no global context needed)."""
        cfg = self.config

        exp_cfg = cfg.get("exposure", {})
        arr = apply_exposure(
            arr,
            ev=exp_cfg.get("ev", 0.0),
            gamma=exp_cfg.get("gamma", 1.0),
            highlights=exp_cfg.get("highlights", 0),
            shadows=exp_cfg.get("shadows", 0),
        )

        con_cfg = cfg.get("contrast", {})
        arr = apply_contrast(
            arr,
            amount=con_cfg.get("amount", 0),
            s_curve=con_cfg.get("s_curve", 0),
            black_point=con_cfg.get("black_point", 0),
            white_point=con_cfg.get("white_point", 255),
        )

        wb_cfg = cfg.get("white_balance", {})
        arr = apply_white_balance(
            arr,
            temperature=wb_cfg.get("temperature", 0),
            tint=wb_cfg.get("tint", 0),
        )

        sat_cfg = cfg.get("saturation", {})
        arr = apply_saturation(
            arr,
            amount=sat_cfg.get("amount", 0),
            vibrance=sat_cfg.get("vibrance", 0),
        )

        lut_cfg = cfg.get("lut", {})
        arr = apply_lut(
            arr,
            lut_path=lut_cfg.get("path"),
            intensity=lut_cfg.get("intensity", 1.0),
        )

        return arr

    def process_directory(
        self,
        input_dir: str | Path,
        output_dir: str | Path,
        extensions: tuple = (".tiff", ".tif", ".jpg", ".jpeg", ".png", ".webp"),
    ) -> list[Path]:
        """Process all images in a directory.

        Args:
            input_dir: Directory with input images.
            output_dir: Directory for output images.
            extensions: Supported file extensions.

        Returns:
            List of output paths.
        """
        input_dir = Path(input_dir)
        files = sorted([
            f for f in input_dir.iterdir()
            if f.suffix.lower() in extensions and f.is_file()
        ])

        if not files:
            print(f"No images found in {input_dir}")
            print(f"  Supported formats: {', '.join(extensions)}")
            return []

        results = []
        total = len(files)
        print(f"Processing {total} image(s) from {input_dir} → {output_dir}")
        print(f"Profile: {getattr(self, '_profile_name', 'default (no profile)')}")

        for i, f in enumerate(files):
            print(f"  [{i+1}/{total}] {f.name}...", end=" ", flush=True)
            try:
                out = self.process_image(f, output_dir)
                if out:
                    size_kb = out.stat().st_size // 1024
                    print(f"✅ {size_kb}KB")
                    results.append(out)
                else:
                    print("❌ failed (no output)")
            except Exception as e:
                print(f"❌ {e}")

        failed = total - len(results)
        print(f"\nDone: {len(results)}/{total} processed")
        if failed:
            print(f"⚠️  {failed} image(s) failed")
        print(f"Output: {output_dir}")
        return results