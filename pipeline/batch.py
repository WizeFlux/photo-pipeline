"""Multiprocessing batch processor for Apple M1 Ultra (20 CPU cores).

Uses ProcessPoolExecutor for parallel image processing.
GPU operations are handled per-process (each worker initializes its own MPS context).
"""

from __future__ import annotations

import gc
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image


def _process_single_file(
    input_path: str,
    output_dir: str,
    params: dict,
    use_gpu: bool = True,
) -> tuple[str, Optional[str], Optional[str]]:
    """Process a single image file. Designed to run in a worker process.

    Returns (input_path, output_path_or_None, error_or_None).
    """
    try:
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load image
        img = Image.open(input_path)
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Convert to numpy
        arr = np.array(img, dtype=np.float32)
        del img

        # Process
        if use_gpu:
            from pipeline.gpu_ops import gpu_process
            result = gpu_process(arr, params)
        else:
            from pipeline.processor import Pipeline
            # Use CPU ops directly
            from pipeline.ops.exposure import apply_exposure
            from pipeline.ops.contrast import apply_contrast
            from pipeline.ops.white_balance import apply_white_balance
            from pipeline.ops.saturation import apply_saturation
            from pipeline.ops.lut import apply_lut

            result = apply_exposure(
                arr, ev=params["ev"], gamma=params["gamma"],
                highlights=params["highlights"], shadows=params["shadows"],
            )
            # Custom S-Curve overrides sigmoid s_curve
            scurve_custom = params.get("scurve_custom")
            s_curve_param = 0 if scurve_custom is not None else params["s_curve"]
            result = apply_contrast(
                result, amount=params["contrast_amount"],
                s_curve=s_curve_param,
                black_point=params["black_point"],
                white_point=params["white_point"],
            )
            if scurve_custom is not None:
                curve = np.asarray(scurve_custom, dtype=np.float32)
                idx = np.clip(result.round(), 0, 255).astype(np.int64)
                result = curve[idx]
            result = apply_white_balance(
                result, temperature=params["temperature"], tint=params["tint"],
            )
            result = apply_saturation(
                result, amount=params["saturation"], vibrance=params["vibrance"],
            )
            result = apply_lut(
                result, lut_path=params.get("lut_path"),
                intensity=params.get("lut_intensity", 1.0),
            )

        # Save
        from pipeline.processor import _format_to_ext
        from pipeline.ops.resize import resize_and_save

        result_img = Image.fromarray(
            np.clip(result, 0, 255).astype(np.uint8), "RGB"
        )

        output_cfg = params.get("output", {})
        suffix = output_cfg.get("suffix", "_processed")
        fmt = output_cfg.get("format", "jpeg")
        out_name = f"{input_path.stem}{suffix}.{_format_to_ext(fmt)}"
        out_path = output_dir / out_name

        resize_and_save(
            result_img,
            out_path,
            width=output_cfg.get("width"),
            height=output_cfg.get("height"),
            fmt=fmt,
            quality=output_cfg.get("quality", 90),
        )

        del result, result_img, arr
        gc.collect()

        return (str(input_path), str(out_path), None)

    except Exception as e:
        return (str(input_path), None, str(e))


def batch_process_parallel(
    input_dir: str | Path,
    output_dir: str | Path,
    params: dict,
    max_workers: int = None,
    use_gpu: bool = True,
    extensions: tuple = (".tiff", ".tif", ".jpg", ".jpeg", ".png", ".webp"),
    progress_callback=None,
):
    """Process all images in a directory using multiprocessing.

    Args:
        input_dir: Directory with input images.
        output_dir: Directory for output images.
        params: Processing parameters dict.
        max_workers: Number of parallel workers. Defaults to min(cpu_count, 20).
        use_gpu: Use GPU (MPS) for processing.
        extensions: Supported file extensions.
        progress_callback: Optional callback(current, total, filename, status).

    Returns:
        List of (input_path, output_path, error) tuples.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    files = sorted([
        f for f in input_dir.iterdir()
        if f.suffix.lower() in extensions and f.is_file()
    ])

    if not files:
        print(f"No images found in {input_dir}")
        print(f"  Supported formats: {', '.join(extensions)}")
        return []

    if max_workers is None:
        # M1 Ultra has 20 cores, leave 2 for system
        max_workers = min(os.cpu_count() or 8, 20)

    total = len(files)
    results = []

    # Add output config to params for workers
    params_with_output = dict(params)
    params_with_output.setdefault("output", {})
    params_with_output["output"]["format"] = params.get("output_format", "jpeg")
    params_with_output["output"]["quality"] = params.get("output_quality", 90)

    print(f"Processing {total} image(s) with {max_workers} workers "
          f"({'GPU' if use_gpu else 'CPU'})...")
    print(f"  Input:  {input_dir}")
    print(f"  Output: {output_dir}")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _process_single_file,
                str(f),
                str(output_dir),
                params_with_output,
                use_gpu,
            ): f
            for f in files
        }

        for i, future in enumerate(as_completed(futures)):
            input_path, output_path, error = future.result()
            filename = Path(input_path).name

            if error:
                status = f"❌ {filename}: {error}"
            else:
                status = f"✅ {filename}"

            results.append((input_path, output_path, error))

            if progress_callback:
                progress_callback(i + 1, total, filename, status)
            else:
                print(f"  [{i+1}/{total}] {status}")

    success = sum(1 for _, o, e in results if o and not e)
    failed = total - success
    print(f"\nDone: {success}/{total} images processed")
    if failed:
        print(f"⚠️  {failed} image(s) failed")
    print(f"Output: {output_dir}")
    return results