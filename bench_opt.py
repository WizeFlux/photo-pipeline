"""Benchmark for the 3 preview optimizations.

Measures:
  1. PreviewWorker.run() equivalent: open + downscale + process (cache on/off)
  2. gpu_saturation op alone (HSL vs RGB-space)
  3. gpu_process_from_pil full pipeline at 1200 and 800 wide

Run:
    python bench_opt.py            # current code (baseline or after)
    python bench_opt.py --baseline # reference numbers printed for comparison
"""
from __future__ import annotations

import argparse
import hashlib
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.gpu_ops import gpu_process_from_pil, gpu_saturation, numpy_to_torch, torch_to_numpy


def make_test_image(path: Path, w: int = 4000, h: int = 2667) -> None:
    """Create a colorful test image on disk."""
    rng = np.random.default_rng(42)
    arr = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
    # Add some color structure so saturation has something to bite
    arr[..., 0] = (arr[..., 0].astype(int) + arr[..., 1] // 2).clip(0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(path, "JPEG", quality=92)


def time_n(fn, n: int = 5) -> float:
    """Return median of n runs in ms."""
    runs = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        runs.append((time.perf_counter() - t0) * 1000)
    runs.sort()
    return runs[len(runs) // 2]


def preview_hash(path: Path) -> str:
    st = path.stat()
    key = f"{path}|{st.st_mtime}|{st.st_size}"
    return hashlib.md5(key.encode()).hexdigest()


def preview_cache_path(h: str) -> Path:
    return Path.home() / ".cache" / "photo-pipeline" / "previews" / f"{h}.jpg"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true", help="just print reference numbers")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--width", type=int, default=4000)
    ap.add_argument("--height", type=int, default=2667)
    args = ap.parse_args()

    tmp = Path("/tmp/bench_opt")
    tmp.mkdir(exist_ok=True)
    img_path = tmp / "test.jpg"
    if not img_path.exists():
        print(f"creating {img_path} ({args.width}x{args.height})...")
        make_test_image(img_path, args.width, args.height)

    # Load full image once for op-level benchmarks
    full = Image.open(img_path).convert("RGB")
    arr_full = np.array(full, dtype=np.float32)

    # Downscaled arrays for op timing
    max_w_1200 = 1200
    max_w_800 = 800
    ratio1200 = max_w_1200 / full.width
    img1200 = full.resize((max_w_1200, int(full.height * ratio1200)), Image.LANCZOS)
    arr1200 = np.array(img1200, dtype=np.float32)
    ratio800 = max_w_800 / full.width
    img800 = full.resize((max_w_800, int(full.height * ratio800)), Image.LANCZOS)
    arr800 = np.array(img800, dtype=np.float32)

    params = {
        "ev": 0.3, "gamma": 1.0, "highlights": -20, "shadows": 15,
        "contrast_amount": 12, "s_curve": 10, "black_point": 0, "white_point": 255,
        "temperature": 5, "tint": 0,
        "saturation": 25, "vibrance": 30,
        "lut_path": None, "lut_intensity": 1.0,
    }

    print(f"\nImage: {full.width}x{full.height}, runs={args.runs}")
    print(f"Device: CPU torch\n")

    # ── 1. saturation op alone ──
    # NOTE: clone outside the timed region so we measure the op, not the copy.
    def _sat_bench(arr_np, amount, vibrance, runs=args.runs):
        t = numpy_to_torch(arr_np)
        fn = lambda: gpu_saturation(t, amount=amount, vibrance=vibrance)
        fn()  # warm
        rs = []
        for _ in range(runs):
            t0 = time.perf_counter()
            out = fn()
            rs.append((time.perf_counter() - t0) * 1000)
        # keep t alive
        _ = out
        rs.sort()
        return rs[len(rs) // 2]

    # gpu_saturation mutates t in-place via chroma = rgb - luma (no, it creates
    # new tensors), so reusing t is fine. But to be safe, re-load each run.
    def sat_amt(arr_np):
        t = numpy_to_torch(arr_np)
        fn = lambda: gpu_saturation(t, amount=25, vibrance=0)
        fn()
        rs = []
        for _ in range(args.runs):
            t0 = time.perf_counter()
            fn()
            rs.append((time.perf_counter() - t0) * 1000)
        rs.sort()
        return rs[len(rs) // 2]

    def sat_both(arr_np):
        t = numpy_to_torch(arr_np)
        fn = lambda: gpu_saturation(t, amount=25, vibrance=30)
        fn()
        rs = []
        for _ in range(args.runs):
            t0 = time.perf_counter()
            fn()
            rs.append((time.perf_counter() - t0) * 1000)
        rs.sort()
        return rs[len(rs) // 2]

    print(f"gpu_saturation @1200x{img1200.height} amount-only: {sat_amt(arr1200):6.1f} ms")
    print(f"gpu_saturation @1200x{img1200.height} both:       {sat_both(arr1200):6.1f} ms")
    print(f"gpu_saturation @800x{img800.height}   amount-only: {sat_amt(arr800):6.1f} ms")
    print(f"gpu_saturation @800x{img800.height}   both:       {sat_both(arr800):6.1f} ms")

    # ── 2. full pipeline from PIL ──
    pipe_ms_1200 = time_n(lambda: gpu_process_from_pil(img1200, params), args.runs)
    print(f"gpu_process_from_pil @1200x{img1200.height}: {pipe_ms_1200:6.1f} ms")
    pipe_ms_800 = time_n(lambda: gpu_process_from_pil(img800, params), args.runs)
    print(f"gpu_process_from_pil @800x{img800.height}:   {pipe_ms_800:6.1f} ms")

    # ── 3. PreviewWorker.run() equivalent: open+downscale+process ──
    # Simulate the load path (no cache vs cache)
    def load_no_cache():
        im = Image.open(img_path)
        if im.mode != "RGB":
            im = im.convert("RGB")
        mw = 800
        if im.width > mw:
            r = mw / im.width
            im = im.resize((mw, int(im.height * r)), Image.LANCZOS)
        return im

    def load_from_cache():
        h = preview_hash(img_path)
        cp = preview_cache_path(h)
        if cp.exists():
            return Image.open(cp).convert("RGB")
        im = load_no_cache()
        cp.parent.mkdir(parents=True, exist_ok=True)
        im.save(cp, "JPEG", quality=95)
        return im

    # Warm the cache (first call writes it)
    load_from_cache()

    open_ms = time_n(load_no_cache, args.runs)
    cache_ms = time_n(load_from_cache, args.runs)
    print(f"PreviewWorker load (PIL open+resize):  {open_ms:6.1f} ms")
    print(f"PreviewWorker load (cache hit):        {cache_ms:6.1f} ms")

    # End-to-end preview worker (load + process)
    def worker_no_cache():
        im = load_no_cache()
        gpu_process_from_pil(im, params)

    def worker_cache():
        im = load_from_cache()
        gpu_process_from_pil(im, params)

    worker_open_ms = time_n(worker_no_cache, args.runs)
    worker_cache_ms = time_n(worker_cache, args.runs)
    print(f"PreviewWorker end-to-end (open+proc):  {worker_open_ms:6.1f} ms")
    print(f"PreviewWorker end-to-end (cache+proc): {worker_cache_ms:6.1f} ms")

    if args.baseline:
        print("\n(baseline reference — no comparison run)")


if __name__ == "__main__":
    main()