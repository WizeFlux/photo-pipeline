# DRY Violations & Refactoring Opportunities — `photo-pipeline`

Scope: `qt_app/widgets/` (adjustments, scurve_editor, image_viewer, plots_panel, lut_picker), `qt_app/main_window.py`, `qt_app/workers.py`, `qt_app/state.py`, `qt_app/plots.py`, `pipeline/gpu_ops.py`, `pipeline/batch.py`. Cross-references to sibling modules (`qt_app/theme.py`, `pipeline/ops/*.py`, `pipeline/processor.py`, `pipeline/preview.py`, `pipeline/cli.py`) are included where they share the same duplication.

Each finding lists: **where** (file:line), **what's duplicated**, and a **suggested refactor**. Findings are grouped by theme. Line numbers are from the current tree (head read in this session).

---

## 1. Duplicated "build preview/profile arrays" title-array triplet in plots.py

**Where:** `qt_app/plots.py:119-121`, `:336-338`, `:396-398`, `:557-559`

```python
n = 3 if profile is not None else 2
titles = ["Original", "Sliders"]
arrays = [orig, live]
if profile is not None:
    titles.append(profile_name or "Profile")
    arrays.append(profile)
```

This exact 6-line block is repeated verbatim in `draw_histograms_row`, `draw_rgb_waveform`, `draw_vectorscope`, and `draw_clipping_map`. A fourth near-duplicate (different labels) appears in `draw_channel_deltas` (`:147-149` uses different titles, but the same structure).

**Suggested refactor:** add a small helper at the top of `plots.py`:

```python
def _triplet(orig, live, profile, profile_name):
    """Return (titles, arrays) for the 2-or-3 panel layout."""
    titles = ["Original", "Sliders"]
    arrays = [orig, live]
    if profile is not None:
        titles.append(profile_name or "Profile")
        arrays.append(profile)
    return titles, arrays
```

Then every draw function becomes `titles, arrays = _triplet(orig, live, profile, profile_name)`.

---

## 2. Spine styling loop duplicated across plots.py and scurve_editor.py

**Where:**
- `qt_app/plots.py:63-65` (inside `_style_axes`)
- `qt_app/plots.py:320-322` (inside `_wave_on_ax` sub-axes)
- `qt_app/plots.py:391-393` (inside `_scope_on_ax`)
- `qt_app/plots.py:571-573` (inside `draw_clipping_map`)
- `qt_app/widgets/scurve_editor.py:106-108` (inside `_redraw`)

```python
for sp in ax.spines.values():
    sp.set_color(_GRID)
    sp.set_linewidth(0.5)
```

**Suggested refactor:** the public `_style_axes(ax, title)` helper in `plots.py:56` already encapsulates most styling, but it does extra work (grid, locators, tick labels) that isn't always wanted. Extract a minimal `_style_spines(ax, color=_GRID, lw=0.5)` helper and call it from all five sites. The scurve editor currently inlines its own copy using its own `_GRID` constant — see §3 for consolidation.

---

## 3. Dark-theme color constants duplicated between plots.py and scurve_editor.py

**Where:**
- `qt_app/plots.py:31-35` — `_BG, _PANEL, _GRID, _TEXT, _MUTED`
- `qt_app/widgets/scurve_editor.py:20-23` — `_BG, _PANEL, _GRID, _TEXT` (same values)

```python
_BG = "#1e1e1e"
_PANEL = "#232323"
_GRID = "#3a3a3a"
_TEXT = "#b0b0b0"
```

Same literals also appear scattered through `qt_app/theme.py` (`#1e1e1e` ×6, `#3a3a3a` ×6, `#b0b0b0` ×2) and `qt_app/widgets/dialogs.py:25,30`. See §4 for the orange accent.

**Suggested refactor:** create `qt_app/theme.py` (or a new `qt_app/palette.py`) module exporting named constants:

```python
# qt_app/palette.py
BG = "#1e1e1e"
PANEL = "#232323"
GRID = "#3a3a3a"
TEXT = "#b0b0b0"
MUTED = "#666666"
ACCENT = "#ff8c00"
ACCENT_DARK = "#cc7000"
TEAL = "#6fbfa8"
```

Have `theme.py` reference these constants when building `DARK_QSS` (or generate the QSS via f-string). `plots.py` and `scurve_editor.py` then `from qt_app.palette import *` (or explicit imports) instead of redeclaring. Eliminates ~10 duplicated string literals.

---

## 4. Orange accent color duplicated across widgets

**Where:**
- `qt_app/widgets/adjustments.py:32,33,40,145` — `#ff8c00`, `#cc7000` (slider active QSS + label style)
- `qt_app/widgets/scurve_editor.py:26,100` — `_POINT_ACTIVE = "#ff8c00"`, edge `"#cc7000"`
- `qt_app/widgets/lut_picker.py:78` — `QFrame:hover { border-color: #ff8c00; }`
- `qt_app/widgets/dialogs.py` likely also uses it (hover states)

`_ACTIVE_SLIDER_QSS` in `adjustments.py:30-43` is also a near-duplicate of the active-point styling in `scurve_editor.py:99-102` (same colors, different markers).

**Suggested refactor:** centralize `ACCENT`/`ACCENT_DARK` per §3, and build `_ACTIVE_SLIDER_QSS` from an f-string so the color is named, not magic. Consider a shared `_active_qss(color, edge)` helper if the slider handle + sub-page QSS is reused.

---

## 5. PIL "open + ensure RGB" idiom duplicated across the pipeline

**Where:**
- `qt_app/main_window.py:394-396` (`_on_save`)
- `qt_app/workers.py:65-67` (`_load_preview_image`)
- `pipeline/gpu_ops.py:447-449` (`gpu_process_from_pil`)
- `pipeline/batch.py:35-37` (`_process_single_file`)
- `pipeline/preview.py:31, 105`
- `pipeline/processor.py:78`

```python
img = Image.open(path)
if img.mode != "RGB":
    img = img.convert("RGB")
```

**Suggested refactor:** add a single helper in a shared location (e.g. `pipeline/io_utils.py` or extend `pipeline/gpu_ops.py`):

```python
def load_rgb(path) -> Image.Image:
    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img
```

Then replace each call site. `gpu_process_from_pil` already does this — it can delegate to `load_rgb`.

---

## 6. "uint8 fromarray + clip" idiom duplicated

**Where:**
- `pipeline/gpu_ops.py:452` — `Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), "RGB")`
- `pipeline/processor.py:111` — same
- `pipeline/batch.py:88-90` — same, split across lines

**Suggested refactor:** add `to_pil_rgb(arr) -> Image.Image` next to `load_rgb` (§5) and call it from all three sites. Centralizes the `np.clip(..., 0, 255).astype(np.uint8)` policy in one place (e.g. if you later want to support 16-bit output).

---

## 7. scurve_custom override logic duplicated in gpu_ops.py and batch.py

**Where:**
- `pipeline/gpu_ops.py:417-427` (inside `gpu_process`)
- `pipeline/batch.py:60-72` (inside the CPU branch of `_process_single_file`)

```python
scurve_custom = params.get("scurve_custom")
s_curve_param = 0 if scurve_custom is not None else params["s_curve"]
# ... pass s_curve_param to contrast op ...
if scurve_custom is not None:
    # build 256-entry LUT from scurve_custom and index into it
```

The GPU path uses `torch.tensor(scurve_custom)[t.round().long()]`; the CPU path uses `np.asarray(scurve_custom)[np.clip(result.round(), 0, 255).astype(np.int64)]`. Same logic, different backend.

**Suggested refactor:** the existing `pipeline/processor.py` `Pipeline` class already has a `process(arr, params)` method that does this — `batch.py`'s CPU branch (`pipeline/batch.py:48-82`) reinvents it inline by importing each `apply_*` op separately. Drop the inline CPU branch and call `Pipeline().process(arr, params)` directly. That removes the duplication *and* the divergence risk (right now batch's CPU path can drift from the GPU path — see that batch also hard-codes the op order, which must match `gpu_process`).

---

## 8. Image-extension tuples duplicated

**Where:**
- `qt_app/workers.py:199-200` — `(".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp")`
- `pipeline/batch.py:122` — `(".tiff", ".tif", ".jpg", ".jpeg", ".png", ".webp")`
- `pipeline/processor.py:304` — `(".tiff", ".tif", ".jpg", ".jpeg", ".png", ".webp")`
- `pipeline/preview.py:92` — `(".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif")`
- `pipeline/cli.py:159` — `(".tiff", ".tif", ".jpg", ".jpeg", ".png", ".webp")`
- `pipeline/ops/resize.py:45` — `[".jpg", ".jpeg", ".webp", ".avif", ".tiff", ".tif", ".png"]` (adds `.avif`)
- `qt_app/main_window.py:364` — `"Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.bmp)"` (filter string)

Order varies; `.bmp` is included in some and missing from others (workers vs. batch). That inconsistency is itself a bug surface.

**Suggested refactor:** declare once in `pipeline/config.py` (or a new `pipeline/formats.py`):

```python
SUPPORTED_SUFFIXES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp")
SUPPORTED_GLOB = " ".join(f"*{s}" for s in SUPPORTED_SUFFIXES)
```

Import everywhere. The Qt file filter in `main_window.py:364` becomes `f"Images ({SUPPORTED_GLOB})"`.

---

## 9. blockSignals(True)/blockSignals(False) boilerplate

**Where:**
- `qt_app/widgets/adjustments.py:169-172` (slider in `set_value`)
- `qt_app/widgets/adjustments.py:340-342` (lut combo in `set_params`)
- `qt_app/widgets/adjustments.py:364-369` (lut combo in `refresh_luts`)
- `qt_app/main_window.py:348-354` (profile combo)
- `qt_app/widgets/profiles.py:98-109` (apply + delete combos)

**Suggested refactor:** add a context manager to `qt_app/widgets/__init__.py` (or a small `qt_app/widgets/_qthelpers.py`):

```python
from contextlib import contextmanager

@contextmanager
def blocked(*widgets):
    for w in widgets:
        w.blockSignals(True)
    try:
        yield
    finally:
        for w in widgets:
            w.blockSignals(False)
```

Then `with blocked(self._lut_combo): ...` replaces the try/finally-less pairs. Especially nice in `profiles.py:98-109` where two widgets are blocked together.

---

## 10. Worker "disconnect + terminate" boilerplate in main_window.py

**Where:**
- `qt_app/main_window.py:492-502` (preview worker teardown)
- `qt_app/main_window.py:537-547` (plots worker teardown)

```python
old = self._<worker>
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    try:
        old.<signal>.disconnect()
    except (RuntimeError, TypeError):
        pass
if old.isRunning():
    old.terminate()
```

The only differences are the attribute name and the signal name.

**Suggested refactor:** add a private helper on `MainWindow`:

```python
def _detach_worker(self, worker, signal_name: str) -> None:
    if worker is None:
        return
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            getattr(worker, signal_name).disconnect()
        except (RuntimeError, TypeError):
            pass
    if worker.isRunning():
        worker.terminate()
```

Call sites become one-liners: `self._detach_worker(self._preview_worker, "finished_preview")` and `self._detach_worker(self._plots_worker, "plots_ready")`. The same pattern is also used in `lut_picker.py:210-215`'s `closeEvent` (though it uses `requestInterruption + wait`, not `terminate` — worth standardizing).

---

## 11. `_lut_combo` find-or-add pattern duplicated

**Where:** `qt_app/widgets/adjustments.py:339-342, 363-368, 379-386`

Three call sites do variations of "block signals, find text in combo, fall back to index 0 / add item, unblock".

```python
idx = self._lut_combo.findText(lut)
self._lut_combo.setCurrentIndex(idx if idx >= 0 else 0)
```

…appears in `set_params`, `refresh_luts`, and `set_lut`.

**Suggested refactor:** add a `_set_combo(combo, text, add_if_missing=False)` method on the panel (or as a free function next to `blocked` in §9):

```python
def _select_combo(combo, text, add_if_missing=False):
    idx = combo.findText(text)
    if idx < 0:
        if add_if_missing:
            combo.addItem(text)
            combo.setCurrentText(text)
        else:
            combo.setCurrentIndex(0)
    else:
        combo.setCurrentIndex(idx)
```

Then wrap each call in `with blocked(combo): _select_combo(...)`. Removes ~15 lines and clarifies intent.

---

## 12. `_redraw + curveChanged.emit(self._compute_curve())` duplicated across scurve_editor.py

**Where:**
- `qt_app/widgets/scurve_editor.py:165-166` (`_on_release`)
- `qt_app/widgets/scurve_editor.py:177-179` (`_on_motion`)
- `qt_app/widgets/scurve_editor.py:203-205` (`wheelEvent`)
- `qt_app/widgets/scurve_editor.py:227-229` (`reset`)

Each does: mutate `_points_y`, `_redraw()`, `curveChanged.emit(self._compute_curve())`. The `_compute_curve()` call is wasted work when `_redraw` already calls it internally (`:94`).

**Suggested refactor:** add a private `_update(self, emit=True)` that does `self._redraw()` and optionally emits `curveChanged` with the cached curve from `_redraw`. Have `_redraw` stash `self._last_curve = y` so callers don't pay for a second `_compute_curve()`. Four call sites collapse to `self._update()`.

---

## 13. Param-key explicit listing repeated across state.py

**Where:** `qt_app/state.py:53-62` (`params_from_values`) and `:77-85` (`params_from_config`) and `:96-103` (`params_to_config`).

Each function enumerates the same 14 keys (`ev`, `gamma`, `highlights`, …, `lut_intensity`) by hand, even though `PARAM_KEYS` is already declared at `state.py:27-32`. `params_from_values` even re-merges with `PARAM_DEFAULTS` first, then re-lists every key — defeating the point of the merge.

**Suggested refactor:**

```python
def params_from_values(values):
    merged = {**PARAM_DEFAULTS, **{k: v for k, v in values.items() if v is not None}}
    lut = values.get("lut_path")
    params = {k: merged[k] for k in PARAM_KEYS}
    params["lut_path"] = None if lut in (None, "None", "") else lut
    scurve = values.get("scurve_custom")
    if scurve is not None:
        params["scurve_custom"] = np.asarray(scurve, dtype=np.float32)
    return params
```

For `params_from_config` / `params_to_config`, define a small mapping table (e.g. `PARAM_TO_CONFIG_SECTION = {"ev": ("exposure", "ev"), …}`) and iterate. Right now adding a new parameter means editing 4 places (defaults, `PARAM_KEYS`, `params_from_values`, `params_from_config`, `params_to_config`) — easy to miss one. A table-driven approach collapses it to 2.

---

## 14. `compute_tone_curve` math duplicated between state.py and gpu_ops.py

**Where:**
- `qt_app/state.py:206-228` — `compute_tone_curve` (numpy)
- `pipeline/gpu_ops.py:167-201` — `gpu_contrast` (torch) — same formula: `factor = 1 + amount/100`, `128 + (result - 128) * factor`, sigmoid `1/(1 + exp(-k*(norm - 0.5)))`, black/white point `np.where` / `torch.where`
- `pipeline/ops/contrast.py:8-49` — `apply_contrast` (numpy) — same formula again

The math is identical across all three; only the array backend differs.

**Suggested refactor:** this is a deeper one, but at minimum the `state.compute_tone_curve` function (used only for the plot preview) should share the formula with `apply_contrast`. Consider parameterizing by backend: a single `tone_curve(arr, ev, gamma, contrast, s_curve, black_point, white_point, backend="numpy"|"torch")` dispatcher, or — simpler — have `state.compute_tone_curve` delegate to `apply_contrast` with a 0-255 x-axis. Eliminates the risk that the plot shows a curve that doesn't match what the GPU actually applies (a real bug surface today — e.g. `compute_tone_curve` applies exposure *before* gamma, and so does `gpu_process`, but if anyone reorders one, the plot silently lies).

---

## 15. `prof_name == "None"` sentinel logic scattered

**Where:**
- `qt_app/main_window.py:303, 507, 550` — `if prof_name == "None": prof_name = None`
- `qt_app/workers.py:119` — `if prof_name and prof_name != "None":`
- `qt_app/state.py:150` — `if not name or name == "None": return None`
- `qt_app/widgets/adjustments.py:338, 377` — `params.get("lut_path") or "None"`, `if lut_path == "None":`
- `qt_app/widgets/lut_picker.py:46, 61` — `if self._lut_path and self._lut_path != "None":`, `if lut_path == "None":`

The string `"None"` is used as a sentinel throughout the Qt layer because QComboBox can't hold actual `None`. Conversion happens ad-hoc at every boundary.

**Suggested refactor:** centralize with two helpers in `qt_app/state.py`:

```python
def normalize_sentinel(value):
    """'None' / '' / None → None; anything else passes through."""
    return None if value in (None, "", "None") else value

def to_combo_value(value):
    """None → 'None' (for QComboBox storage); else str(value)."""
    return "None" if value is None else str(value)
```

Then every `if prof_name == "None": prof_name = None` becomes `prof_name = normalize_sentinel(prof_name)`, and every `params.get("lut_path") or "None"` becomes `to_combo_value(params.get("lut_path"))`. Makes the sentinel policy explicit and grep-able.

---

## 16. Plot dispatch ladder in plots_panel.py

**Where:** `qt_app/widgets/plots_panel.py:46-83` (`_draw_plot`)

An 8-branch `if/elif` chain dispatches on `plot_type` string, where 6 of the 8 branches call `draw_<x>(fig, data["orig"], data["live"], data["profile"], data["profile_name"])` with identical argument lists (only `Tone Curve` differs — it passes `params` instead).

**Suggested refactor:** use a dispatch dict:

```python
_PLOT_DISPATCH = {
    "Histograms":    draw_histograms_row,
    "Channel Deltas": draw_channel_deltas,
    "RGB Waveform":  draw_rgb_waveform,
    "Vectorscope":   draw_vectorscope,
    "Saturation Dist": draw_saturation_hist,
    "Zone System":   draw_zone_system,
    "Clipping Map":  draw_clipping_map,
}

def _draw_plot(fig, plot_type, data):
    if plot_type == "None":
        fig.clear(); return False
    if plot_type == "Tone Curve":
        draw_tone_curve(fig, data["params"], data["third_params"], data["profile_name"])
        return True
    fn = _PLOT_DISPATCH.get(plot_type)
    if fn:
        fn(fig, data["orig"], data["live"], data["profile"], data["profile_name"])
        return True
    return False
```

Removes ~30 lines and makes adding a new plot a one-line table change. Pair this with §1 to make the 6 standard-arg plots truly uniform.

---

## 17. Highlight/shadow recovery duplicated within gpu_exposure

**Where:** `pipeline/gpu_ops.py:142-162`

`highlights > 0` and `highlights < 0` branches share the `normalized = result / 255.0; mask = ((normalized - 0.5) * 2).clamp(0, 1)` setup; only the final blend differs. Same for the `shadows > 0` / `< 0` branches (which swap the mask sign and the blend coefficients).

```python
if highlights > 0:
    h_factor = highlights / 100.0
    normalized = result / 255.0
    mask = ((normalized - 0.5) * 2).clamp(0, 1)
    result = normalized * (1 - mask * h_factor * 0.5) * 255.0
elif highlights < 0:
    h_factor = abs(highlights) / 100.0
    normalized = result / 255.0
    mask = ((normalized - 0.5) * 2).clamp(0, 1)
    result = (normalized + mask * h_factor * 0.3).clamp(0, 1) * 255.0
```

**Suggested refactor:** hoist the shared lines and parameterize the blend:

```python
def _hl_shadows(result, amount, *, is_highlights):
    if amount == 0: return result
    normalized = result / 255.0
    mask = ((normalized - 0.5) * 2).clamp(0, 1) if is_highlights \
           else ((0.5 - normalized) * 2).clamp(0, 1)
    factor = abs(amount) / 100.0
    if (amount > 0) == is_highlights:
        # recover: pull back extremes
        return normalized * (1 - mask * factor * 0.5) * 255.0
    else:
        # boost: lift extremes
        return (normalized + mask * factor * 0.3).clamp(0, 1) * 255.0
```

Then `gpu_exposure` calls `_hl_shadows(result, highlights, is_highlights=True)` and `_hl_shadows(result, shadows, is_highlights=False)`. Removes ~12 lines and makes the symmetry between highlights and shadows explicit.

---

## 18. Catmull-Rom / sigmoid constants and `np.linspace(0, 255, 256)` duplicated

**Where:**
- `qt_app/widgets/scurve_editor.py:118` — `x_out = np.linspace(0, 255, 256)`
- `qt_app/state.py:211` — `x = np.linspace(0, 255, 256)`
- `qt_app/plots.py:210` — `x = np.linspace(0, 255, 256)`
- `qt_app/widgets/scurve_editor.py:42` — `POINT_X = np.array([0, 64, 128, 192, 255], …)` — fixed 256-domain assumption
- Sigmoid formula `1/(1 + exp(-k*(norm - 0.5)))` with `k = 5*strength`: `state.py:225-227`, `gpu_ops.py:194-199`, `pipeline/ops/contrast.py:41-48`.

**Suggested refactor:**
- Add a `CURVE_N = 256` constant (in `state.py` or a `pipeline/constants.py`) and a `_curve_x()` helper returning `np.linspace(0, 255, CURVE_N)`. Three call sites.
- Extract the sigmoid S-curve into a single function, e.g. `state.sigmoid_s_curve(arr_or_tensor, strength)`, with a numpy and a torch implementation (or use `np` everywhere and convert in `gpu_ops`). Today the same 4-line formula lives in three files with three different array types.

---

## 19. Preview cache path hardcoded twice

**Where:**
- `qt_app/workers.py:24` — `_PREVIEW_CACHE_DIR = Path.home() / ".cache" / "photo-pipeline" / "previews"`
- `qt_app/main_window.py:339` — `cache_dir = Path.home() / ".cache" / "photo-pipeline" / "previews"` (in `_clear_preview_cache`)

**Suggested refactor:** import `from qt_app.workers import _PREVIEW_CACHE_DIR` in `main_window.py`, or — cleaner — expose a public `preview_cache_dir()` function from `workers.py` and have both modules use it. Right now if you move the cache, you must edit two files.

---

## 20. Slider-spec tuple unpacking duplicated

**Where:** `qt_app/widgets/adjustments.py:178-197, 206`

Each spec is `(key, label, min, max, default, step, fmt)` and is unpacked by position at `:206`:

```python
for key, label, vmin, vmax, default, step, fmt in specs:
    slider = _LabeledSlider(label, vmin, vmax, default, step, fmt)
```

This 7-tuple is fragile — reordering or adding a field means touching every spec. Also the `_LabeledSlider` constructor (`:100`) takes those same 6 positional args.

**Suggested refactor:** replace tuples with `dataclass(slots=True)`:

```python
from dataclasses import dataclass

@dataclass(slots=True)
class SliderSpec:
    key: str
    label: str
    vmin: float
    vmax: float
    default: float
    step: float = 1.0
    fmt: str = "{:.2f}"
```

Spec tables become readable, and `_build_slider_group` iterates with `for spec in specs: slider = _LabeledSlider(spec.label, spec.vmin, …)`. Future fields (e.g. `tooltip`, `log_scale`) become opt-in.

---

## 21. `_lut_combo.currentText()` accessed inline in `_emit_params` and `get_params`

**Where:** `qt_app/widgets/adjustments.py:318-323` and `:327-332`

The two functions are essentially identical:

```python
def _emit_params(self):
    params = {key: slider.value() for key, slider in self._sliders.items()}
    params["lut_path"] = self._lut_combo.currentText()
    params["lut_intensity"] = self._intensity_slider.value()
    params["scurve_custom"] = self._scurve_y
    self.paramsChanged.emit(params)

def get_params(self):
    params = {key: slider.value() for key, slider in self._sliders.items()}
    params["lut_path"] = self._lut_combo.currentText()
    params["lut_intensity"] = self._intensity_slider.value()
    params["scurve_custom"] = self._scurve_y
    return params
```

**Suggested refactor:** have `_emit_params` call `get_params`:

```python
def _emit_params(self):
    self.paramsChanged.emit(self.get_params())
```

Trivial, but removes a 5-line copy that must be kept in sync by hand.

---

## 22. Two QThread subclasses with identical run() shape (try/except → emit failed)

**Where:** `qt_app/workers.py:106-128` (`PreviewWorker.run`), `:155-174` (`PlotsWorker.run`), `:194-221` (`BatchWorker.run`)

All three follow:

```python
def run(self):
    try:
        if self.isInterruptionRequested(): return
        # ... work ...
        self.<success_signal>.emit(<payload>)
    except Exception as exc:
        self.failed.emit(str(exc))
```

`PlotsWorker` is currently almost empty (it just re-emits its inputs in a dict — the real work happens on the UI thread in `plots_panel._redraw_plots`), so the entire `try/except/isInterruptionRequested` scaffolding is pure boilerplate.

**Suggested refactor:** introduce a small `_BaseWorker(QThread)` base class:

```python
class _BaseWorker(QThread):
    failed = Signal(str)
    def run(self):
        try:
            if self.isInterruptionRequested(): return
            self._do_work()
        except Exception as exc:
            self.failed.emit(str(exc))
    def _do_work(self): raise NotImplementedError
```

Each worker then only implements `_do_work()` and declares its success signal. Removes 3 copies of the try/except/interruption pattern. Additionally, evaluate whether `PlotsWorker` is needed at all right now — if all it does is forward inputs, the parallelism it provides is illusory (the heavy matplotlib draws still happen on the UI thread). Either move the `_draw_plot` calls into `PlotsWorker._do_work` (requires passing figures across threads, which is unsafe) or delete the worker until it does real work.

---

## 23. Inconsistent success/failure counting in batch.py vs workers.py

**Where:**
- `pipeline/batch.py:198-199` — `success = sum(1 for _, o, e in results if o and not e); failed = total - success`
- `qt_app/workers.py:216-217` — `success = sum(1 for _, o, e in results if o and not e); failed = sum(1 for _, _, e in results if e)`

Two different definitions of "failed" for the same `results` tuple list. `batch.py` defines `failed = total - success` (so a row with both `o` set and `e` set counts as success *and* is subtracted from failed); `workers.py` defines `failed` as "rows with `e` set" (independent of `o`). They diverge on the edge case where both `o` and `e` are set.

**Suggested refactor:** extract `count_results(results) -> tuple[int, int]` into `pipeline/batch.py` and have `workers.py` import it. Removes the silent divergence.

---

## 24. `_short_name("None")` special case mirrors `to_combo_value` (§15)

**Where:** `qt_app/widgets/lut_picker.py:59-63`

```python
def _short_name(lut_path: str) -> str:
    if lut_path == "None":
        return "None (no LUT)"
    return os.path.basename(lut_path)
```

A localized sentinel handling that should be unified with §15's `normalize_sentinel`. The display label `"None (no LUT)"` is a UI concern; the sentinel detection is the same logic repeated.

---

## 25. `qimage + bytes_per_line + Format_RGB888` pattern duplicated

**Where:**
- `qt_app/widgets/image_viewer.py:128-135` (`_build_qimage`)
- `qt_app/widgets/lut_picker.py:125-130` (`set_image`)

```python
h, w = arr.shape[:2]
bytes_per_line = 3 * w
self._bytes = arr.tobytes()
qimg = QImage(self._bytes, w, h, bytes_per_line, QImage.Format_RGB888)
```

Both keep a `self._bytes` reference to prevent GC of the underlying buffer (the same pitfall, documented in both places).

**Suggested refactor:** add `to_qimage_rgb888(arr) -> tuple[QImage, bytes]` to `qt_app/widgets/__init__.py` (or a new `_qthelpers.py`):

```python
def to_qimage_rgb888(arr: np.ndarray) -> tuple[QImage, bytes]:
    arr = np.ascontiguousarray(arr, dtype=np.uint8)
    h, w = arr.shape[:2]
    buf = arr.tobytes()
    return QImage(buf, w, h, 3 * w, QImage.Format_RGB888), buf
```

Callers keep the `buf` reference (same pattern, named once). Removes duplicated GC-footgun documentation and the inconsistent local variable names (`_image_bytes` vs `_bytes`).

---

## Priority / suggested order of attack

**High value, low risk (do first):**
- §1 (`_triplet` helper), §16 (plot dispatch dict) — pure plot.py simplification, ~50 lines removed
- §9 (`blocked` context manager) — trivial, prevents missing unblock bugs
- §10 (`_detach_worker` helper) — kills 20 lines in main_window
- §21 (`_emit_params` calls `get_params`) — 5 lines → 1
- §19 (preview cache path imported, not redeclared)
- §8 (image suffix tuple centralized) — fixes an actual `.bmp` inconsistency bug

**Medium value, medium risk:**
- §3 + §4 (central palette module) — touches many files but mechanical
- §13 (table-driven params in state.py) — reduces "add a parameter" edit cost from 4 sites to 2
- §7 (batch CPU path delegates to Pipeline.process) — removes ~35 lines and a real divergence risk
- §22 (`_BaseWorker` base class for QThread workers)
- §25 (shared `to_qimage_rgb888`)

**Higher risk / bigger design calls (worth a separate discussion):**
- §14 (unify tone-curve math across numpy/torch backends) — correct but non-trivial
- §17 (hoist highlight/shadow shared lines) — symmetry is nice but the magic numbers 0.5 / 0.3 should probably be named at the same time
- §18 (sigmoid + 256-domain constants) — easy if §14 is undertaken first
- §2 (shared spine styler) — trivial, but pairs with §3 to be worthwhile

---

## Summary

- **25 distinct DRY findings** across the 11 in-scope files (plus cross-references into 6 sibling modules).
- **Most repeated single pattern:** the 6-line `titles/arrays/n=3` block in `plots.py` (×4, §1).
- **Most repeated literal:** the dark-theme hex colors `#1e1e1e`, `#232323`, `#3a3a3a`, `#b0b0b0` (declared in `plots.py`, redeclared in `scurve_editor.py`, and inlined throughout `theme.py` / `dialogs.py` — §3, §4).
- **Highest-divergence-risk duplication:** the `scurve_custom` override logic in `gpu_ops.py` vs. `batch.py` (§7) and the tone-curve math in `state.py` vs. `gpu_ops.py` vs. `ops/contrast.py` (§14) — these can silently drift and cause the plot to lie about what the pipeline does.
- **Actual bug surface from DRY violation:** the `.bmp` extension inconsistency (§8) and the divergent `failed` count definition (§23).

No files were modified — this is a report only. Apply findings in the priority order above.