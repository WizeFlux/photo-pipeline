# LUTs

Place `.cube` LUT files in this directory.

## Usage

In your profile YAML:

```yaml
lut:
  path: luts/my_lut.cube    # relative to project root
  intensity: 0.8            # 0.0–1.0 blend with original
```

Or via CLI:

```bash
python -m pipeline process input/ -o output/ --lut luts/my_lut.cube --lut-intensity 0.8
```

## Finding LUTs

- [RocketStock Free LUTs](https://rocketstock.com/free-luts/)
- [Lutify.me](https://lutify.me/)
- DaVinci Resolve built-in LUTs (export as .cube)
- Any .cube file from color grading tools