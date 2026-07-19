# Photo Pipeline — Performance, Coverage & Refactoring Report

**Date:** 2026-07-19
**Commit:** `59642bb` (main)
**Tests:** 224 passing

---

## 1. Performance Profiling

### GPU Processing (`gpu_process_from_pil`)

Device: **CPU** (3 threads, PyTorch)

| Image Size | Avg (ms) | Min (ms) | Notes |
|---|---|---|---|
| 800×600 | 24.4 | 22.5 | Preview size |
| 1200×800 | 38.6 | 37.3 | Typical preview |
| 2000×1500 | 289.9 | 258.9 | Large preview |
| 4000×3000 | 1256.9 | 1143.7 | Full-res (batch) |
| 800×600 + S-Curve | 19.2 | — | Custom curve (fast LUT) |
| 800×600 + LUT | 43.3 | — | 3D LUT via grid_sample |

**Observations:**
- CPU processing scales ~linearly with pixel count
- S-Curve (256-entry LUT) adds negligible overhead (~0ms — it's a simple index)
- 3D LUT adds ~20ms at preview size (grid_sample trilinear interpolation)
- 3-thread limit prevents contention when multiple workers run

### Plots Rendering (800×1200 image)

| Plot Type | Time (ms) | Complexity |
|---|---|---|
| Tone Curve | 47.3 | Low — single line plot |
| Channel Deltas | 181.4 | Medium — 3 histogram diffs |
| Zone System | 106.1 | Medium — 10 zone bars |
| Histograms | 240.5 | Medium — 3 RGB histograms |
| Clipping Map | 252.2 | Medium — pixel classification |
| RGB Waveform | 415.9 | High — per-column RGB scatter |
| Saturation Dist | 518.2 | High — HSV scatter |
| Vectorscope | 616.8 | Highest — polar YC mapping |

**Throttle:** 350ms coalescing timer prevents UI freeze during slider drag.
Heavy plots (Vectorscope 617ms) only render after user stops dragging.

### S-Curve Editor

| Operation | Avg (ms) | Notes |
|---|---|---|
| `_compute_curve` | 0.059 | Catmull-Rom spline, 256 values |
| `_redraw` | 12.45 | Full matplotlib figure redraw |

Curve computation is negligible — real-time during drag.

### UI Responsiveness

| Metric | Value | Notes |
|---|---|---|
| Max gap during 20 rapid slider changes | **2ms** | Workers terminated, not waited |
| Preview render (800×600) | 24ms | Background thread |
| Image render to screen | <5ms | FastTransformation + coalescing |
| Plots throttle | 350ms | Only final state rendered |

---

## 2. Test Coverage

**Total:** 224 tests, **69% coverage** (2990 statements, 939 missed)

### High Coverage (≥90%)

| Module | Coverage | Tests |
|---|---|---|
| `qt_app/plots.py` | 96% | test_plots.py |
| `qt_app/widgets/scurve_editor.py` | 96% | test_scurve_editor.py |
| `qt_app/widgets/plots_panel.py` | 98% | test_plots_panel_none.py |
| `qt_app/theme.py` | 100% | — |
| `pipeline/ops/saturation.py` | 100% | test_saturation.py |
| `pipeline/ops/vignette.py` | 100% | test_effects.py |
| `pipeline/ops/white_balance.py` | 100% | test_white_balance.py |
| `pipeline/ops/contrast.py` | 100% | test_contrast.py |
| `pipeline/cli.py` | 89% | test_cli.py |
| `pipeline/preview.py` | 91% | test_preview.py |

### Medium Coverage (60–89%)

| Module | Coverage | Gap |
|---|---|---|
| `qt_app/state.py` | 79% | Profile I/O edge cases |
| `qt_app/widgets/adjustments.py` | 80% | set_params, set_lut paths |
| `qt_app/widgets/dialogs.py` | 73% | Settings dialog (plots moved) |
| `qt_app/main_window.py` | 58% | Worker management, file ops |
| `qt_app/widgets/image_viewer.py` | 58% | Zoom/pan, resize events |
| `pipeline/ops/lut.py` | 71% | 1D LUT path |
| `pipeline/ops/exposure.py` | 71% | Edge cases |
| `pipeline/config.py` | 76% | Default merging |
| `pipeline/processor.py` | 83% | Strip processing |

### Low Coverage (<60%) — Refactoring Candidates

| Module | Coverage | Reason |
|---|---|---|
| `qt_app/widgets/lut_picker.py` | 52% | Dialog creation segfaults in tests |
| `qt_app/workers.py` | 37% | QThread hard to unit-test |
| `pipeline/gpu_ops.py` | 33% | Many GPU ops, CPU fallback paths |
| `qt_app/widgets/batch.py` | 16% | Dialog UI, batch runner |
| `qt_app/widgets/profiles.py` | 16% | Dialog UI |
| `qt_app/main.py` | 0% | Entry point (3 lines) |

### Missing Tests (Priority)

1. **`qt_app/workers.py`** (37%) — PreviewWorker/PlotsWorker run() paths
2. **`qt_app/main_window.py`** (58%) — `_on_open`, `_on_save`, batch runner
3. **`qt_app/widgets/image_viewer.py`** (58%) — zoom, pan, resize events
4. **`pipeline/gpu_ops.py`** (33%) — individual GPU ops (vignette, grain, etc.)
5. **`qt_app/widgets/lut_picker.py`** (52%) — dialog interactions (segfault risk)

---

## 3. DRY Refactoring Opportunities

### 3.1 Duplicated Worker Detachment Logic

**Files:** `qt_app/main_window.py:447-460`, `qt_app/main_window.py:495-505`

Both `_run_preview` and `_start_plots_worker` have identical pattern:
```python
if self._<worker> is not None:
    old = self._<worker>
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try: old.<signal>.disconnect()
        except (RuntimeError, TypeError): pass
    if old.isRunning(): old.terminate()
```

**Refactor:** Extract `_terminate_worker(worker, signal_name)` helper.

### 3.2 Duplicated `params_from_values` / `get_params` / `_emit_params`

**Files:** `qt_app/widgets/adjustments.py:310-316`, `qt_app/widgets/adjustments.py:319-323`

`get_params()` and `_emit_params()` build the same dict. `params_from_values`
in state.py also merges defaults.

**Refactor:** `get_params()` calls `_emit_params(emit=False)` returning dict.

### 3.3 Duplicated QImage Construction

**Files:** `qt_app/widgets/image_viewer.py:107-114`, `qt_app/widgets/lut_picker.py:128-132`

Both build QImage from numpy bytes:
```python
self._bytes = arr.tobytes()
qimg = QImage(self._bytes, w, h, bytes_per_line, QImage.Format_RGB888)
```

**Refactor:** Extract `numpy_to_qimage(arr) -> QImage` utility.

### 3.4 Duplicated DPR-Aware Pixmap Scaling

**Files:** `qt_app/widgets/image_viewer.py:122-145`, `qt_app/widgets/lut_picker.py:115-133`

Both compute `dpr`, scale to physical pixels, set `setDevicePixelRatio`.

**Refactor:** Extract `make_scaled_pixmap(arr, css_w, css_h, dpr) -> QPixmap`.

### 3.5 Repeated Color Constants

**Files:** `qt_app/widgets/scurve_editor.py`, `qt_app/widgets/image_viewer.py`, `qt_app/widgets/lut_picker.py`

Color constants (`#1e1e1e`, `#ff8c00`, `#6fbfa8`, `#333`, etc.) repeated.

**Refactor:** Centralize in `qt_app/theme.py` as `COLORS` dict.

### 3.6 Duplicated `params_to_config` / `params_from_config` Keys

**Files:** `qt_app/state.py:71-87`, `qt_app/state.py:89-101`

Both enumerate the same param keys with same defaults.

**Refactor:** Single `_PARAM_SPEC` list of `(key, section, default)` tuples.

### 3.7 Duplicated `_load_preview_image` calls

**Files:** `qt_app/workers.py`, `qt_app/main_window.py:318`

Both load preview image with same function.

**Refactor:** Already DRY — `_load_preview_image` is shared. ✓

---

## 4. Architecture Summary

### Strengths
- **Coalescing timers** (preview render, plots render, image display) keep UI responsive
- **Worker termination** (not interruption) prevents CPU contention
- **Thread-limited torch** (3 threads) avoids oversubscription
- **LANCZOS + DPR-aware** thumbnails — sharp on Retina
- **Catmull-Rom S-Curve** — smooth, intuitive tone shaping
- **YAML profiles with S-Curve** — full state persistence

### Weaknesses
- 69% coverage — workers and dialogs under-tested
- gpu_ops.py at 33% — many untested code paths
- Matplotlib plots block UI thread (throttled but not async)
- QThread segfaults in test environment (lut_picker dialog tests)

---

## 5. Recommendations

### High Priority
1. **Extract DRY helpers** (§3.1–3.4) — reduces ~80 lines of duplication
2. **Add worker tests** — mock QThread.run() to test logic without threads
3. **Centralize colors** in theme.py — single source of truth

### Medium Priority
4. **Add gpu_ops unit tests** — test individual ops (vignette, grain) in isolation
5. **Move plots rendering to worker** — matplotlib is not thread-safe but
   off-screen Figure rendering in a thread + blit to canvas is possible
6. **Profile LUT picker** with many LUTs (20+) — parallel thumbnail generation

### Low Priority
7. **Add batch.py tests** — multiprocessing hard to test, but logic testable
8. **Benchmark on MPS/CUDA** — CPU numbers will differ significantly
9. **Consider async plots** — QThreadPool for plot rendering

---

## 6. Files Changed This Session

| Commit | Description |
|---|---|
| `b08ba8f` | None plot option, RGB waveform, parallel plots, S-Curve editor |
| `a3a64d2` | Compact S-Curve, non-blocking workers, remove redundant sliders |
| `05aff89` | Coalesce image renders + fast scaling |
| `d857790` | Worker termination + thread limit + S-Curve scroll |
| `2b0fc42` | Minimize S-Curve padding |
| `593bbb2` | Fix S-Curve drag + active point stays orange |
| `48d7e97` | Fix S-Curve scroll — event filter for matplotlib |
| `7973438` | Fix right plot selector disappears on None |
| `9e4803d` | S-Curve scroll resolution 1 IRE |
| `2255497` | Invert S-Curve scroll direction |
| `2dbb69c` | Reduce S-Curve height ~1/4 |
| `2d7000f` | Remove grid lines from S-Curve |
| `5adc5fa` | Throttle plot rendering (350ms) |
| `53f2ecd` | Move Plots checkbox to toolbar |
| `afd9de2` | LUT picker dialog with visual previews |
| `e81b156` | LUT picker — intensity, name below, bigger+HQ |
| `6abc837` | Save/load scurve_custom in YAML profiles |
| `e65849d` | Retina/HiDPI rendering for LUT picker |
| `5eb0712` | Double LUT picker thumbnail size |
| `59642bb` | LUT picker 3 columns, window sized to fit |

**20 commits, 224 tests passing, 69% coverage.**