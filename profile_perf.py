"""Performance profiling for the photo-pipeline Qt app.

Measures:
1. gpu_process_from_pil timing for various image sizes
2. PreviewWorker end-to-end timing (uses a real image file on disk)
3. LUT picker thumbnail generation timing (per-LUT + total)
4. Plots rendering timing for each draw_* function
5. S-Curve computation timing (_compute_curve)

Run headless with QT_QPA_PLATFORM=offscreen.
Outputs a markdown report to perf_report.md.
"""

from __future__ import annotations

import os
import sys
import time
import statistics
from pathlib import Path

# Headless Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLBACKEND", "Agg")

# Ensure project root on path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np
from PIL import Image

# Imports under test
from pipeline.gpu_ops import gpu_process_from_pil, DEVICE
from qt_app.plots import (
    make_empty_figure,
    draw_histograms_row,
    draw_channel_deltas,
    draw_tone_curve,
    draw_rgb_waveform,
    draw_vectorscope,
    draw_saturation_hist,
    draw_zone_system,
    draw_clipping_map,
)

# Qt app for workers/widgets needs QApplication
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from qt_app.workers import PreviewWorker
from qt_app.widgets.scurve_editor import SCurveEditor
from qt_app.widgets.lut_picker import _LutThumbWorker
from qt_app.state import list_luts, PARAM_DEFAULTS


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ms(times_s: list[float]) -> tuple[float, float, float]:
    """Return (mean_ms, min_ms, max_ms)."""
    ms = [t * 1000.0 for t in times_s]
    return statistics.mean(ms), min(ms), max(ms)


def make_test_image(size: tuple[int, int]) -> Image.Image:
    """A synthetic photographic-ish image with gradients + noise."""
    w, h = size
    # Smooth horizontal gradient with per-channel offsets
    x = np.linspace(0, 255, w, dtype=np.float32)
    y = np.linspace(0, 255, h, dtype=np.float32)
    arr = np.empty((h, w, 3), dtype=np.float32)
    arr[..., 0] = x[None, :] * 0.6 + y[:, None] * 0.4
    arr[..., 1] = x[None, :] * 0.3 + y[:, None] * 0.7
    arr[..., 2] = x[None, :] * 0.5 + y[:, None] * 0.5
    # Add some noise so histograms/vectorscopes aren't degenerate
    rng = np.random.default_rng(42)
    arr += rng.normal(0, 8, arr.shape)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


# Default params with a bit of everything active (so all ops are exercised)
ACTIVE_PARAMS = {
    **PARAM_DEFAULTS,
    "ev": 0.5,
    "gamma": 1.1,
    "highlights": -20,
    "shadows": 15,
    "contrast_amount": 10,
    "s_curve": 15,
    "black_point": 5,
    "white_point": 250,
    "temperature": 10,
    "tint": -5,
    "saturation": 12,
    "vibrance": 20,
}

LUT_PATH = str(ROOT / "luts" / "teal_orange.cube")
ACTIVE_PARAMS_WITH_LUT = {**ACTIVE_PARAMS, "lut_path": LUT_PATH, "lut_intensity": 0.8}


# ─── 1. gpu_process_from_pil timing ───────────────────────────────────────────

def bench_gpu_process_from_pil() -> list[dict]:
    # (size, reps) — reduce reps for very large images on CPU to keep
    # the profiling runtime bounded. Skip 4000x3000 (OOM on this host).
    sizes = [
        ((256, 256), 6),
        ((512, 512), 6),
        ((1024, 1024), 5),
        ((2048, 2048), 4),
        ((3000, 2000), 3),
    ]
    results = []
    # Warmup the LUT cache once with a small image so first call doesn't
    # include .cube parsing overhead (that's I/O, not compute).
    _ = gpu_process_from_pil(make_test_image((64, 64)), ACTIVE_PARAMS_WITH_LUT)
    # also warmup torch kernels on the device
    _ = gpu_process_from_pil(make_test_image((256, 256)), ACTIVE_PARAMS_WITH_LUT)

    for size, n_reps in sizes:
        img = make_test_image(size)
        reps = []
        for i in range(n_reps):
            t0 = time.perf_counter()
            _ = gpu_process_from_pil(img, ACTIVE_PARAMS_WITH_LUT)
            if DEVICE.type == "cuda":
                import torch
                torch.cuda.synchronize()
            reps.append(time.perf_counter() - t0)
        reps = reps[1:]  # drop warmup
        mean, mn, mx = _ms(reps)
        results.append({
            "size": f"{size[0]}×{size[1]}",
            "pixels": size[0] * size[1],
            "mean_ms": mean, "min_ms": mn, "max_ms": mx,
            "reps": len(reps),
        })
        print(f"  gpu_process_from_pil {size[0]}×{size[1]}: {mean:.1f} ms (min {mn:.1f}, max {mx:.1f})")
    return results


# ─── 2. PreviewWorker end-to-end ──────────────────────────────────────────────

def bench_preview_worker() -> list[dict]:
    # PreviewWorker loads a downscale preview from disk via _load_preview_image.
    # We write a synthetic image file to a temp path so it has a real source.
    import tempfile
    sizes = [
        ((800, 600), 4),     # typical preview-sized source
        ((1600, 1200), 4),   # larger source, will be downscaled
        ((3000, 2000), 3),   # big source, exercises downscale + cache write
    ]
    results = []
    for size, n_reps in sizes:
        img = make_test_image(size)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            img.save(f, "JPEG", quality=92)
            tmp_path = f.name
        try:
            # Clear preview cache so first run does the downscale work
            from qt_app import workers as _w
            cache_dir = _w._PREVIEW_CACHE_DIR
            if cache_dir.exists():
                for p in cache_dir.glob("*.jpg"):
                    try: p.unlink()
                    except OSError: pass

            reps = []
            for i in range(n_reps):
                w = PreviewWorker(tmp_path, ACTIVE_PARAMS_WITH_LUT)
                t0 = time.perf_counter()
                # Run synchronously in current thread (don't call start() to
                # avoid QThread event-loop overhead; we want raw wall time).
                w.run()
                reps.append(time.perf_counter() - t0)
            reps = reps[1:]  # drop warmup (first call writes cache)
            mean, mn, mx = _ms(reps)
            results.append({
                "size": f"{size[0]}×{size[1]}",
                "mean_ms": mean, "min_ms": mn, "max_ms": mx,
                "reps": len(reps),
            })
            print(f"  PreviewWorker {size[0]}×{size[1]}: {mean:.1f} ms (min {mn:.1f}, max {mx:.1f})")
        finally:
            os.unlink(tmp_path)
    return results


# ─── 3. LUT picker thumbnail generation ───────────────────────────────────────

def bench_lut_thumbnails() -> list[dict]:
    """Time per-LUT thumbnail processing via _LutThumbWorker.run().

    Mirrors what the LUT picker grid does (one worker per LUT, each
    processes the same base image with that LUT applied). We run them
    sequentially to measure individual timings cleanly.
    """
    luts = list_luts()
    # Use a representative picker-size source image (matches _THUMB_W=640
    # aspect; picker typically gets a preview-sized image ~1200 wide).
    img = make_test_image((1200, 800))
    results = []
    total_times = []
    # Warmup LUT caches for all LUTs with a tiny image
    for lut in luts:
        p = {**ACTIVE_PARAMS, "lut_path": None if lut == "None" else lut,
             "lut_intensity": 0.8}
        _ = gpu_process_from_pil(make_test_image((64, 64)), p)

    for lut in luts:
        p = {**ACTIVE_PARAMS, "lut_path": None if lut == "None" else lut,
             "lut_intensity": 0.8}
        reps = []
        for i in range(4):
            worker = _LutThumbWorker(img, ACTIVE_PARAMS, lut, 0.8)
            t0 = time.perf_counter()
            worker.run()
            reps.append(time.perf_counter() - t0)
        reps = reps[1:]
        mean, mn, mx = _ms(reps)
        total_times.append(mean)
        results.append({
            "lut": lut,
            "mean_ms": mean, "min_ms": mn, "max_ms": mx,
        })
        print(f"  LUT thumb {lut}: {mean:.1f} ms")

    # Sequential total (what one worker thread costs end-to-end if run
    # one-by-one). The real UI runs them in parallel, but sequential sum
    # is a useful upper bound for wall-time on a single core.
    results.append({
        "lut": "SUM (sequential)",
        "mean_ms": sum(total_times), "min_ms": sum(total_times),
        "max_ms": sum(total_times),
    })
    print(f"  LUT thumbs sequential sum: {sum(total_times):.1f} ms over {len(luts)} LUTs")
    return results


# ─── 4. Plots rendering timing ────────────────────────────────────────────────

def bench_plots() -> list[dict]:
    """Time each draw_* function on a representative preview image."""
    # Plots operate on the processed preview arrays. Use ~1200x800
    # (typical preview size after downscale to _PREVIEW_MAX_W=1200).
    orig = np.array(make_test_image((1200, 800)), dtype=np.uint8)
    live = np.array(gpu_process_from_pil(
        Image.fromarray(orig, "RGB"), ACTIVE_PARAMS_WITH_LUT), dtype=np.uint8)
    profile = np.array(gpu_process_from_pil(
        Image.fromarray(orig, "RGB"),
        {**ACTIVE_PARAMS, "lut_path": str(ROOT / "luts" / "warm.cube"),
         "lut_intensity": 0.7}), dtype=np.uint8)

    plot_fns = [
        ("draw_histograms_row", draw_histograms_row),
        ("draw_channel_deltas", draw_channel_deltas),
        ("draw_tone_curve", draw_tone_curve),
        ("draw_rgb_waveform", draw_rgb_waveform),
        ("draw_vectorscope", draw_vectorscope),
        ("draw_saturation_hist", draw_saturation_hist),
        ("draw_zone_system", draw_zone_system),
        ("draw_clipping_map", draw_clipping_map),
    ]

    # Signature variations: tone_curve doesn't take image arrays.
    def call(fn_name, fn, fig):
        if fn_name == "draw_tone_curve":
            fn(fig, ACTIVE_PARAMS_WITH_LUT,
               third_params={**ACTIVE_PARAMS, "lut_path": str(ROOT / "luts" / "warm.cube")},
               profile_name="Warm")
        else:
            fn(fig, orig, live, profile, profile_name="Warm")

    results = []
    # Pre-warm matplotlib (font cache, etc.) by rendering one figure
    fig = make_empty_figure()
    call("draw_histograms_row", draw_histograms_row, fig)

    for name, fn in plot_fns:
        reps = []
        for i in range(5):
            fig = make_empty_figure()
            t0 = time.perf_counter()
            call(name, fn, fig)
            # Force a full draw to measure realistic render cost
            fig.canvas.draw() if hasattr(fig, "canvas") else fig.draw_without_rendering()
            reps.append(time.perf_counter() - t0)
        reps = reps[1:]
        mean, mn, mx = _ms(reps)
        results.append({
            "plot": name, "mean_ms": mean, "min_ms": mn, "max_ms": mx,
        })
        print(f"  {name}: {mean:.1f} ms (min {mn:.1f}, max {mx:.1f})")
    return results


# ─── 5. S-Curve computation timing ────────────────────────────────────────────

def bench_scurve() -> list[dict]:
    """Time SCurveEditor._compute_curve across several control-point configs."""
    # _compute_curve is a pure method — we can call it on a bare instance
    # without the QWidget machinery by using the unbound function on a
    # lightweight stand-in. Simpler: instantiate the widget (offscreen Qt).
    editor = SCurveEditor()

    configs = {
        "identity (default)": None,
        "gentle S": np.array([0, 50, 128, 205, 255], dtype=np.float64),
        "steep mid": np.array([0, 90, 128, 165, 255], dtype=np.float64),
        "inverted": np.array([255, 200, 128, 55, 0], dtype=np.float64),
    }

    results = []
    for name, pts in configs.items():
        if pts is not None:
            editor._points_y = pts.copy()
        else:
            editor.reset()
        # warmup
        _ = editor._compute_curve()
        reps = []
        for i in range(200):
            t0 = time.perf_counter()
            _ = editor._compute_curve()
            reps.append(time.perf_counter() - t0)
        # Keep first 100 after dropping first 10 as warmup
        reps = reps[10:110]
        mean, mn, mx = _ms(reps)
        results.append({
            "config": name, "mean_ms": mean, "min_ms": mn, "max_ms": mx,
            "reps": len(reps),
        })
        print(f"  _compute_curve {name}: {mean:.4f} ms (min {mn:.4f}, max {mx:.4f})")
    return results


# ─── Report ───────────────────────────────────────────────────────────────────

def write_report(gpu, preview, luts, plots, scurve, path: Path) -> None:
    dev_str = str(DEVICE)
    lines = []
    lines.append("# Photo-Pipeline Performance Report\n")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"Device: `{dev_str}`  |  Image source: synthetic (PIL gradients + noise)\n")
    lines.append("All timings in **ms**. Each row is mean over N reps after a warmup rep dropped.\n")

    lines.append("## 1. `gpu_process_from_pil` — full pipeline (PIL → GPU → PIL)\n")
    lines.append("Params: all ops active (exposure, contrast, S-curve, WB, saturation, vibrance, 3D LUT).\n")
    lines.append("| Image size | Pixels | Mean (ms) | Min (ms) | Max (ms) | Reps |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for r in gpu:
        lines.append(f"| {r['size']} | {r['pixels']:,} | {r['mean_ms']:.2f} | {r['min_ms']:.2f} | {r['max_ms']:.2f} | {r['reps']} |")
    lines.append("")

    lines.append("## 2. `PreviewWorker` — end-to-end (load + downscale + process + emit)\n")
    lines.append("Uses a real temp JPEG on disk; preview cache cleared before each size's first run. Includes `gpu_process_from_pil` + downscale + cache write/read.\n")
    lines.append("| Source size | Mean (ms) | Min (ms) | Max (ms) | Reps |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in preview:
        lines.append(f"| {r['size']} | {r['mean_ms']:.2f} | {r['min_ms']:.2f} | {r['max_ms']:.2f} | {r['reps']} |")
    lines.append("")

    lines.append("## 3. LUT picker thumbnail generation (`_LutThumbWorker.run`)\n")
    lines.append(f"Source image: 1200×800. {len(luts)-1} LUTs processed sequentially (each = one grid cell).\n")
    lines.append("| LUT | Mean (ms) | Min (ms) | Max (ms) |")
    lines.append("|---|---:|---:|---:|")
    for r in luts:
        lines.append(f"| {r['lut']} | {r['mean_ms']:.2f} | {r['min_ms']:.2f} | {r['max_ms']:.2f} |")
    lines.append("")
    lines.append("> In the real UI these run as parallel `QThread`s, so wall time ≈ slowest single LUT, not the sum.\n")

    lines.append("## 4. Plots rendering (`draw_*` + `canvas.draw()`)\n")
    lines.append("Preview image: 1200×800. Three image variants passed (orig / live / profile) where the function accepts them.\n")
    lines.append("| Plot function | Mean (ms) | Min (ms) | Max (ms) |")
    lines.append("|---|---:|---:|---:|")
    for r in plots:
        lines.append(f"| {r['plot']} | {r['mean_ms']:.2f} | {r['min_ms']:.2f} | {r['max_ms']:.2f} |")
    lines.append("")

    lines.append("## 5. S-Curve computation (`SCurveEditor._compute_curve`)\n")
    lines.append("Catmull-Rom spline through 5 control points → 256 y-values. 100 reps per config (warmup dropped).\n")
    lines.append("| Config | Mean (ms) | Min (ms) | Max (ms) | Reps |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in scurve:
        lines.append(f"| {r['config']} | {r['mean_ms']:.4f} | {r['min_ms']:.4f} | {r['max_ms']:.4f} | {r['reps']} |")
    lines.append("")

    lines.append("## Notes\n")
    lines.append(f"- Compute device: **{dev_str}**. On Apple Silicon this would be MPS; on this host it's {'CPU (no CUDA/MPS)' if dev_str == 'cpu' else dev_str}.")
    lines.append("- `gpu_process_from_pil` includes PIL↔numpy conversion + all 6 pipeline ops (exposure, contrast, custom-S-curve LUT, WB, saturation, 3D LUT).")
    lines.append("- Plots timings include `Figure.canvas.draw()` (full Agg rasterization), which dominates for image-heavy plots (waveform, vectorscope, clipping).")
    lines.append("- `_compute_curve` is called per mouse-move event during S-curve dragging; sub-0.1 ms is well within one frame budget.")
    lines.append("- LUT thumbnail numbers reflect one worker thread; the picker runs ~8 in parallel so the grid fills in ≈ max(individual) not Σ.")

    path.write_text("\n".join(lines))
    print(f"\nReport written to {path}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Device: {DEVICE}")
    print("\n[1/5] gpu_process_from_pil…")
    gpu = bench_gpu_process_from_pil()
    print("\n[2/5] PreviewWorker…")
    preview = bench_preview_worker()
    print("\n[3/5] LUT thumbnails…")
    luts = bench_lut_thumbnails()
    print("\n[4/5] Plots…")
    plots = bench_plots()
    print("\n[5/5] S-Curve computation…")
    scurve = bench_scurve()

    out = ROOT / "perf_report.md"
    write_report(gpu, preview, luts, plots, scurve, out)


if __name__ == "__main__":
    main()