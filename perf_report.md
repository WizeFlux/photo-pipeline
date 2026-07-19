# Photo-Pipeline Performance Report

Generated: 2026-07-19 08:39:09

Device: `cpu`  |  Image source: synthetic (PIL gradients + noise)

All timings in **ms**. Each row is mean over N reps after a warmup rep dropped.

## 1. `gpu_process_from_pil` — full pipeline (PIL → GPU → PIL)

Params: all ops active (exposure, contrast, S-curve, WB, saturation, vibrance, 3D LUT).

| Image size | Pixels | Mean (ms) | Min (ms) | Max (ms) | Reps |
|---|---:|---:|---:|---:|---:|
| 256×256 | 65,536 | 15.60 | 13.45 | 18.55 | 5 |
| 512×512 | 262,144 | 53.70 | 43.14 | 61.76 | 5 |
| 1024×1024 | 1,048,576 | 188.65 | 159.70 | 234.29 | 4 |
| 2048×2048 | 4,194,304 | 1986.51 | 1750.59 | 2250.25 | 3 |
| 3000×2000 | 6,000,000 | 2799.42 | 2794.86 | 2803.98 | 2 |

## 2. `PreviewWorker` — end-to-end (load + downscale + process + emit)

Uses a real temp JPEG on disk; preview cache cleared before each size's first run. Includes `gpu_process_from_pil` + downscale + cache write/read.

| Source size | Mean (ms) | Min (ms) | Max (ms) | Reps |
|---|---:|---:|---:|---:|
| 800×600 | 95.62 | 90.59 | 103.85 | 3 |
| 1600×1200 | 243.05 | 227.15 | 268.74 | 3 |
| 3000×2000 | 199.30 | 198.54 | 200.06 | 2 |

## 3. LUT picker thumbnail generation (`_LutThumbWorker.run`)

Source image: 1200×800. 8 LUTs processed sequentially (each = one grid cell).

| LUT | Mean (ms) | Min (ms) | Max (ms) |
|---|---:|---:|---:|
| None | 133.01 | 130.00 | 134.77 |
| luts/bw.cube | 169.94 | 146.86 | 192.93 |
| luts/contrast.cube | 149.94 | 142.48 | 154.80 |
| luts/cool.cube | 134.79 | 117.40 | 160.64 |
| luts/faded.cube | 148.74 | 121.19 | 189.98 |
| luts/neutral.cube | 128.95 | 117.01 | 145.50 |
| luts/teal_orange.cube | 160.28 | 119.89 | 183.35 |
| luts/warm.cube | 146.81 | 124.07 | 180.82 |
| SUM (sequential) | 1172.47 | 1172.47 | 1172.47 |

> In the real UI these run as parallel `QThread`s, so wall time ≈ slowest single LUT, not the sum.

## 4. Plots rendering (`draw_*` + `canvas.draw()`)

Preview image: 1200×800. Three image variants passed (orig / live / profile) where the function accepts them.

| Plot function | Mean (ms) | Min (ms) | Max (ms) |
|---|---:|---:|---:|
| draw_histograms_row | 239.84 | 186.28 | 380.63 |
| draw_channel_deltas | 205.49 | 139.79 | 387.06 |
| draw_tone_curve | 42.06 | 40.75 | 43.69 |
| draw_rgb_waveform | 386.65 | 282.92 | 626.42 |
| draw_vectorscope | 552.81 | 507.42 | 578.81 |
| draw_saturation_hist | 435.72 | 419.72 | 444.33 |
| draw_zone_system | 85.10 | 78.70 | 93.24 |
| draw_clipping_map | 229.27 | 213.26 | 249.96 |

## 5. S-Curve computation (`SCurveEditor._compute_curve`)

Catmull-Rom spline through 5 control points → 256 y-values. 100 reps per config (warmup dropped).

| Config | Mean (ms) | Min (ms) | Max (ms) | Reps |
|---|---:|---:|---:|---:|
| identity (default) | 0.0608 | 0.0542 | 0.1018 | 100 |
| gentle S | 0.0594 | 0.0539 | 0.0907 | 100 |
| steep mid | 0.0754 | 0.0542 | 0.1267 | 100 |
| inverted | 0.0879 | 0.0542 | 0.3230 | 100 |

## Notes

- Compute device: **cpu**. On Apple Silicon this would be MPS; on this host it's CPU (no CUDA/MPS).
- `gpu_process_from_pil` includes PIL↔numpy conversion + all 6 pipeline ops (exposure, contrast, custom-S-curve LUT, WB, saturation, 3D LUT).
- Plots timings include `Figure.canvas.draw()` (full Agg rasterization), which dominates for image-heavy plots (waveform, vectorscope, clipping).
- `_compute_curve` is called per mouse-move event during S-curve dragging; sub-0.1 ms is well within one frame budget.
- LUT thumbnail numbers reflect one worker thread; the picker runs ~8 in parallel so the grid fills in ≈ max(individual) not Σ.