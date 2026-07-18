"""YAML config loader with sensible defaults for all pipeline parameters."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ─── Defaults ───────────────────────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    # Crop
    "crop": {
        "aspect_ratio": None,       # "4:3", "16:9", "1:1", None = no crop
        "gravity": "center",        # center, left, right, top, bottom, topleft, etc.
        "offset_x": 0.0,            # -1.0 to 1.0, shifts crop horizontally
        "offset_y": 0.0,            # -1.0 to 1.0, shifts crop vertically
    },
    # Exposure
    "exposure": {
        "ev": 0.0,                  # exposure compensation in EV (-3 to +3)
        "gamma": 1.0,               # gamma curve (0.5–2.5)
        "highlights": 0,            # -100 to 100, recover highlights
        "shadows": 0,               # -100 to 100, lift shadows
    },
    # Contrast
    "contrast": {
        "amount": 0,                # -100 to 100, linear contrast
        "s_curve": 0,               # 0–100, sigmoid S-curve contrast
        "black_point": 0,           # 0–50, clip blacks
        "white_point": 255,         # 205–255, clip whites
    },
    # White balance
    "white_balance": {
        "temperature": 0,           # -100 (cool) to 100 (warm)
        "tint": 0,                  # -100 (green) to 100 (magenta)
        "preset": None,             # "daylight", "cloudy", "tungsten", "fluorescent", None
    },
    # Saturation
    "saturation": {
        "amount": 0,                # -100 to 100, global saturation
        "vibrance": 0,              # -100 to 100, smart saturation (protects skin)
    },
    # LUT
    "lut": {
        "path": None,               # path to .cube file
        "intensity": 1.0,           # 0.0–1.0, blend with original
    },
    # Vignette
    "vignette": {
        "amount": 0,                # -100 to 100, negative = darken edges
        "size": 50,                 # 0–100, radius of vignette
        "feather": 50,              # 0–100, softness of edge
        "roundness": 0,             # -100 to 100, shape 0=circle 100=rectangle
    },
    # Film grain
    "grain": {
        "amount": 0,                # 0–100
        "size": 1,                  # 1–10, grain particle size
        "monochrome": True,         # True=grayscale grain, False=color grain
    },
    # Resize & output
    "output": {
        "width": None,              # target width in px, None = original
        "height": None,             # target height in px, None = original
        "format": "jpeg",           # "jpeg", "webp", "avif", "tiff"
        "quality": 90,              # 1–100 for jpeg/webp/avif
        "suffix": "_processed",     # suffix for output filename
    },
}


# ─── Presets ────────────────────────────────────────────────────────────────

WB_PRESETS: dict[str, tuple[int, int]] = {
    # (temperature, tint) — approximated
    "daylight":     (0, 0),
    "cloudy":       (15, 5),
    "shade":        (30, 10),
    "tungsten":     (-40, 0),
    "fluorescent":  (-20, 15),
    "flash":        (10, 0),
}


# ─── Loader ─────────────────────────────────────────────────────────────────

def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins."""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def load_config(profile_path: str | Path | None = None) -> dict[str, Any]:
    """Load config from YAML profile, merged with defaults.

    Args:
        profile_path: Path to YAML profile file. If None, returns defaults.

    Returns:
        Merged config dict.
    """
    config = copy.deepcopy(DEFAULT_CONFIG)

    if profile_path is not None:
        path = Path(profile_path)
        if not path.exists():
            raise FileNotFoundError(f"Profile not found: {path}")
        with open(path) as f:
            user_config = yaml.safe_load(f) or {}
        config = deep_merge(config, user_config)

    # Apply WB preset if set
    wb = config.get("white_balance", {})
    preset = wb.get("preset")
    if preset and preset in WB_PRESETS:
        t, tint = WB_PRESETS[preset]
        # Preset adds to explicit values
        wb["temperature"] = wb.get("temperature", 0) + t
        wb["tint"] = wb.get("tint", 0) + tint

    return config


def apply_overrides(config: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Apply CLI overrides on top of config.

    Overrides use dotted notation: {"exposure.ev": 0.5, "contrast.amount": 15}
    """
    result = copy.deepcopy(config)
    for dotted_key, value in overrides.items():
        keys = dotted_key.split(".")
        d = result
        for k in keys[:-1]:
            if k not in d:
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
    return result