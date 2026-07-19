"""Pure application logic — no Qt imports.

Contains: parameter mapping, profile I/O, image statistics, tone-curve math.
Kept GUI-agnostic so it can be reused by CLI, tests, or alternative frontends.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pipeline.config import load_config


# ─── Paths ───────────────────────────────────────────────────────────────────

PROFILES_DIR = Path("profiles")
LUT_DIR = Path("luts")


# ─── Parameter model ─────────────────────────────────────────────────────────
# Canonical parameter order — shared between UI sliders, profiles, and processing.

PARAM_KEYS: tuple[str, ...] = (
    "ev", "gamma", "highlights", "shadows",
    "contrast_amount", "s_curve", "black_point", "white_point",
    "temperature", "tint", "saturation", "vibrance",
    "lut_path", "lut_intensity",
)

PARAM_DEFAULTS: dict[str, Any] = {
    "ev": 0.0, "gamma": 1.0, "highlights": 0, "shadows": 0,
    "contrast_amount": 0, "s_curve": 0, "black_point": 0, "white_point": 255,
    "temperature": 0, "tint": 0, "saturation": 0, "vibrance": 0,
    "lut_path": None, "lut_intensity": 1.0,
}


def params_from_values(values: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw slider values into processing params dict.

    Values for removed sliders (gamma, contrast_amount, s_curve,
    black_point, white_point — now handled by the S-Curve editor) fall
    back to PARAM_DEFAULTS so the processing pipeline always gets a
    complete params dict.
    """
    lut = values.get("lut_path")
    # Merge defaults with provided values — missing keys use defaults.
    merged = {**PARAM_DEFAULTS, **{k: v for k, v in values.items() if v is not None}}
    params = {
        "ev": merged["ev"], "gamma": merged["gamma"],
        "highlights": merged["highlights"], "shadows": merged["shadows"],
        "contrast_amount": merged["contrast_amount"], "s_curve": merged["s_curve"],
        "black_point": merged["black_point"], "white_point": merged["white_point"],
        "temperature": merged["temperature"], "tint": merged["tint"],
        "saturation": merged["saturation"], "vibrance": merged["vibrance"],
        "lut_path": None if lut in (None, "None", "") else lut,
        "lut_intensity": merged["lut_intensity"],
    }
    # Optional custom S-Curve from interactive editor (256 y-values or None)
    scurve = values.get("scurve_custom")
    if scurve is not None:
        params["scurve_custom"] = np.asarray(scurve, dtype=np.float32)
    return params


def params_from_config(cfg: dict) -> dict[str, Any]:
    """Extract a flat params dict from a YAML config structure."""
    exp = cfg.get("exposure", {})
    con = cfg.get("contrast", {})
    wb = cfg.get("white_balance", {})
    sat = cfg.get("saturation", {})
    lut = cfg.get("lut", {})
    params = {
        "ev": exp.get("ev", 0.0), "gamma": exp.get("gamma", 1.0),
        "highlights": exp.get("highlights", 0), "shadows": exp.get("shadows", 0),
        "contrast_amount": con.get("amount", 0), "s_curve": con.get("s_curve", 0),
        "black_point": con.get("black_point", 0), "white_point": con.get("white_point", 255),
        "temperature": wb.get("temperature", 0), "tint": wb.get("tint", 0),
        "saturation": sat.get("amount", 0), "vibrance": sat.get("vibrance", 0),
        "lut_path": lut.get("path"), "lut_intensity": lut.get("intensity", 1.0),
    }
    # Load custom S-Curve (256 y-values) if present
    scurve = cfg.get("scurve_custom")
    if scurve is not None:
        params["scurve_custom"] = np.asarray(scurve, dtype=np.float32)
    return params


def params_to_config(params: dict[str, Any]) -> dict:
    """Serialize a flat params dict into YAML config structure."""
    cfg = {
        "exposure": {"ev": params["ev"], "gamma": params["gamma"],
                      "highlights": params["highlights"], "shadows": params["shadows"]},
        "contrast": {"amount": params["contrast_amount"], "s_curve": params["s_curve"],
                      "black_point": params["black_point"], "white_point": params["white_point"]},
        "white_balance": {"temperature": params["temperature"], "tint": params["tint"]},
        "saturation": {"amount": params["saturation"], "vibrance": params["vibrance"]},
        "lut": {"path": params.get("lut_path"), "intensity": params["lut_intensity"]},
    }
    # Save custom S-Curve (256 y-values) if present
    scurve = params.get("scurve_custom")
    if scurve is not None:
        arr = np.asarray(scurve, dtype=np.float32)
        cfg["scurve_custom"] = arr.tolist()
    return cfg


# ─── Profile discovery & I/O ─────────────────────────────────────────────────

def list_profiles() -> list[str]:
    """Return sorted list of YAML profile filenames."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(f.name for f in PROFILES_DIR.glob("*.yaml"))


def list_luts() -> list[str]:
    """Return ['None', ...cube files]."""
    if not LUT_DIR.exists():
        return ["None"]
    return ["None"] + sorted(str(f) for f in LUT_DIR.glob("*.cube"))


def save_profile(name: str, params: dict[str, Any]) -> Path:
    """Persist params as a YAML profile. Returns the saved path."""
    if not name.endswith(".yaml"):
        name += ".yaml"
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / name
    with open(path, "w") as f:
        yaml.dump(params_to_config(params), f, default_flow_style=False, sort_keys=False)
    return path


def delete_profile(name: str) -> bool:
    """Remove a profile file. Returns True if deleted."""
    path = PROFILES_DIR / name
    if path.exists():
        path.unlink()
        return True
    return False


def load_profile_params(name: str) -> dict[str, Any] | None:
    """Load a profile and return its flat params dict, or None if missing."""
    if not name or name == "None":
        return None
    path = PROFILES_DIR / name
    if not path.exists():
        return None
    return params_from_config(load_config(path))


# ─── Image statistics ────────────────────────────────────────────────────────

def compute_stats(img_arr: np.ndarray) -> dict[str, float]:
    """Compute a battery of image statistics for comparison tables/plots."""
    arr = np.asarray(img_arr, dtype=np.float64)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return {
        "Brightness": lum.mean(),
        "B_median": float(np.median(lum)),
        "B_std": lum.std(),
        "B_min": lum.min(),
        "B_max": lum.max(),
        "Range": lum.max() - lum.min(),
        "R_mean": r.mean(), "G_mean": g.mean(), "B_mean": b.mean(),
        "R_std": r.std(), "G_std": g.std(), "B_std": b.std(),
        "R/B": r.mean() / max(b.mean(), 1),
        "R/G": r.mean() / max(g.mean(), 1),
        "G/B": g.mean() / max(b.mean(), 1),
        "Saturation": np.std(arr, axis=-1).mean(),
        "SNR": lum.mean() / max(lum.std(), 1),
        "Shadows%": (lum < 50).sum() / lum.size * 100,
        "Midtones%": ((lum >= 50) & (lum < 200)).sum() / lum.size * 100,
        "Highlights%": (lum >= 200).sum() / lum.size * 100,
        "Clip_S%": (arr.min(axis=-1) < 3).sum() / arr.shape[0] / arr.shape[1] * 100,
        "Clip_H%": (arr.max(axis=-1) > 252).sum() / arr.shape[0] / arr.shape[1] * 100,
    }


def stats_rows(orig: np.ndarray, live: np.ndarray | None,
               profile: np.ndarray | None) -> list[dict[str, float]]:
    """Build comparison rows: [{Metric, Original, Live, Profile?}, ...]."""
    s_orig = compute_stats(orig)
    s_live = compute_stats(live) if live is not None else {}
    s_prof = compute_stats(profile) if profile is not None else {}
    rows = []
    for key in s_orig:
        row = {"Metric": key,
               "Original": round(s_orig[key], 2),
               "Live": round(s_live.get(key, 0), 2)}
        if profile is not None:
            row["Profile"] = round(s_prof.get(key, 0), 2)
        rows.append(row)
    return rows


# ─── Tone curve math (shared with plots) ─────────────────────────────────────

def compute_tone_curve(
    ev: float, gamma: float, contrast: int, s_curve: int,
    black_point: int, white_point: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute the input→output tone curve as (x, y) arrays of length 256."""
    x = np.linspace(0, 255, 256)
    y = x.copy().astype(np.float64)
    y = y * (2.0 ** ev)
    y = np.clip(y / 255.0, 0, 1) ** (1.0 / gamma) * 255.0
    if black_point > 0:
        y = np.where(y < black_point, 0, (y - black_point) * 255.0 / (255 - black_point))
    if white_point < 255:
        y = np.where(y > white_point, 255, y * 255.0 / white_point)
    if contrast != 0:
        factor = 1.0 + contrast / 100.0
        y = 128.0 + (y - 128.0) * factor
    if s_curve > 0:
        strength = s_curve / 100.0
        norm = np.clip(y / 255.0, 0, 1)
        k = 5.0 * strength
        sigmoid = 1.0 / (1.0 + np.exp(-k * (norm - 0.5)))
        y = (norm * (1 - strength) + sigmoid * strength) * 255.0
    return x, np.clip(y, 0, 255)


def curve_from_params(params: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Convenience wrapper: compute tone curve from a full params dict."""
    return compute_tone_curve(
        params["ev"], params["gamma"], params["contrast_amount"],
        params["s_curve"], params["black_point"], params["white_point"],
    )