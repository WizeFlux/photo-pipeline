# Photo Pipeline

Batch photo processing with LUTs, color grading, and format conversion.
Native PySide6 desktop GUI with live preview, plus CLI for automation.

Built for macOS (Apple Silicon) with optional GPU (MPS) acceleration.

## Quick Start

```bash
# Setup (one-time)
git clone https://github.com/WizeFlux/photo-pipeline.git
cd photo-pipeline
./setup.sh

# Desktop GUI (recommended)
python -m qt_app.main

# CLI — batch process a folder
python -m pipeline process ./input -o ./output -p profiles/cinematic.yaml

# CLI — preview a single image (before/after)
python -m pipeline preview ./input/photo.tiff -p profiles/cinematic.yaml

# CLI — analyze images (brightness, color temp, dimensions)
python -m pipeline analyze ./input
```

## Desktop GUI

Native Qt application — no browser needed.

```
┌─────────────────────────────────────────────────────────────┐
│ [📂 Open] [📋 Profiles] [📁 Batch] [⚙ Settings]  [↺ Reset] │
├──────────────────────┬──────────────────────────────────────┤
│                      │  Exposure  Contrast  WB  Sat  LUT   │
│   Before │ Live      │  Profiles  Batch                    │
│   (synced zoom/pan)   ├──────────────────────────────────────┤
│                      │  [Histograms ▾]  [Tone Curve ▾]      │
│                      │  ┌────────────┬─────────────────┐    │
│                      │  │  stats     │  plots          │    │
└──────────────────────┴──────────────────────────────────────┘
```

**Features:**
- Before/Live preview with synchronized zoom & pan (Retina/HiDPI-aware)
- 14 adjustment parameters in 5 groups: Exposure, Contrast, WB, Saturation, LUT
- Optional 3rd profile overlay for comparison
- Live histograms, channel deltas, and tone curve plots
- Image statistics (brightness, median, percentiles, channel ratios)
- Profile save/load/delete (YAML)
- Batch processing with GPU acceleration
- Adjustable preview quality and max width (Settings)

## Features

| Operation | Parameters | Range |
|---|---|---|
| **Crop** | aspect_ratio, gravity, offset | 4:3, 16:9, 1:1, custom |
| **Exposure** | EV, gamma, highlights, shadows | ±3 EV, 0.5–2.5 gamma |
| **Contrast** | linear, S-curve, black/white point | -100 to 100 |
| **White Balance** | temperature, tint, presets | -100 to 100 |
| **Saturation** | global, vibrance (skin-aware) | -100 to 100 |
| **LUT** | .cube 3D LUTs with intensity blend | 0.0–1.0 |
| **Vignette** | amount, size, feather, roundness | -100 to 100 |
| **Grain** | amount, size, monochrome/color | 0–100 |
| **Output** | resize, WebP/JPEG/AVIF/TIFF | quality 1–100 |

## Profiles

YAML profiles define all parameters. Edit or create new ones in `profiles/`.

```yaml
# profiles/my_look.yaml
crop:
  aspect_ratio: "4:3"

exposure:
  ev: -0.3
  shadows: 15

contrast:
  amount: 15
  s_curve: 30

white_balance:
  temperature: 12

lut:
  path: luts/warm_film.cube
  intensity: 0.8

vignette:
  amount: -25

grain:
  amount: 15
  size: 2

output:
  width: 1920
  format: webp
  quality: 90
```

## CLI Overrides

Any profile parameter can be overridden on the command line:

```bash
python -m pipeline process ./input -o ./output \
  -p profiles/cinematic.yaml \
  --exposure 0.5 \
  --contrast 20 \
  --temperature 15 \
  --lut luts/my_lut.cube \
  --lut-intensity 0.7 \
  --aspect 4:3 \
  --format webp \
  --quality 95
```

## LUTs

Place `.cube` files in the `luts/` directory. Supports both 1D and 3D LUTs with trilinear interpolation.

See [`luts/README.md`](luts/README.md) for usage details.

## Processing Order

```
crop → exposure → contrast → white_balance → saturation → LUT → vignette → grain → resize → save
```

## GPU Acceleration

Uses PyTorch with the best available backend:
- **MPS** (Apple Silicon) — default on M1/M2/M3
- **CUDA** — if available
- **CPU** — fallback

Large images (>50MP) are processed in strips to avoid memory overflow.

## Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
photo-pipeline/
├── qt_app/              # PySide6 desktop GUI
│   ├── main.py          # Entry point
│   ├── main_window.py   # Main window layout
│   ├── state.py         # Pure logic (no Qt) — params, profiles, stats
│   ├── workers.py       # Background processing threads
│   ├── plots.py         # Matplotlib render functions
│   ├── theme.py         # Dark theme QSS
│   └── widgets/         # Reusable UI components
├── pipeline/            # Core processing library
│   ├── cli.py           # Click-based CLI
│   ├── processor.py     # Pipeline orchestrator
│   ├── batch.py         # Multiprocessing batch processor
│   ├── gpu_ops.py       # GPU-accelerated operations (PyTorch)
│   ├── preview.py       # Before/after & grid previews
│   ├── config.py        # YAML config loader with defaults
│   └── ops/             # Individual operations (crop, exposure, etc.)
├── profiles/            # YAML profiles
├── luts/                # .cube LUT files
├── tests/               # pytest test suite
├── requirements.txt
└── setup.sh
```

## Requirements

- Python 3.10+
- macOS / Linux / Windows
- All dependencies installed via `setup.sh` into local `.venv/`