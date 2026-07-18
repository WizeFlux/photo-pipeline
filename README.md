# Photo Pipeline

Batch photo processing CLI with LUTs, color grading, and format conversion. Built for macOS (Apple Silicon), self-contained with local venv.

## Quick Start

```bash
# Setup (one-time)
git clone https://github.com/WizeFlux/photo-pipeline.git
cd photo-pipeline
./setup.sh

# Process a folder of images
python -m pipeline process ./input -o ./output -p profiles/cinematic.yaml

# Preview a single image (before/after)
python -m pipeline preview ./input/photo.tiff -p profiles/cinematic.yaml

# Analyze images (brightness, color temp, dimensions)
python -m pipeline analyze ./input
```

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

## Processing Order

```
crop → exposure → contrast → white_balance → saturation → LUT → vignette → grain → resize → save
```

## Tests

```bash
python -m pytest tests/ -v
```

## Requirements

- Python 3.10+
- macOS / Linux / Windows
- All dependencies installed via `setup.sh` into local `.venv/`