"""3D LUT parser and applier for .cube files.

Supports:
- 1D LUTs (LUT_1D_SIZE)
- 3D LUTs (LUT_3D_SIZE) with trilinear interpolation
- Intensity blending with original image
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def parse_cube(path: str | Path) -> dict:
    """Parse a .cube LUT file.

    Args:
        path: Path to .cube file.

    Returns:
        Dict with keys:
        - 'type': '1D' or '3D'
        - 'size': int (1D size or 3D size per axis)
        - 'table': np.ndarray, shape (size,) or (size, size, size, 3) for 3D
        - 'domain_min': np.ndarray (3,)
        - 'domain_max': np.ndarray (3,)
    """
    path = Path(path)
    lut_type = None
    size = None
    domain_min = np.array([0.0, 0.0, 0.0])
    domain_max = np.array([1.0, 1.0, 1.0])
    rows = []

    with open(path) as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if line.startswith("#") or not line:
                continue

            # Parse header keywords
            upper = line.upper()
            if upper.startswith("LUT_1D_SIZE"):
                lut_type = "1D"
                size = int(line.split()[1])
                continue
            if upper.startswith("LUT_3D_SIZE"):
                lut_type = "3D"
                size = int(line.split()[1])
                continue
            if upper.startswith("DOMAIN_MIN"):
                vals = line.split()[1:4]
                domain_min = np.array([float(v) for v in vals])
                continue
            if upper.startswith("DOMAIN_MAX"):
                vals = line.split()[1:4]
                domain_max = np.array([float(v) for v in vals])
                continue
            if upper.startswith("TITLE"):
                continue

            # Data row: R G B
            parts = line.split()
            if len(parts) >= 3:
                rows.append([float(parts[0]), float(parts[1]), float(parts[2])])

    if lut_type is None:
        raise ValueError(f"Could not determine LUT type from {path}")

    table = np.array(rows, dtype=np.float32)

    if lut_type == "1D":
        table = table.reshape(size, 3)
    elif lut_type == "3D":
        # .cube 3D order: R varies fastest, then G, then B
        table = table.reshape(size, size, size, 3)
        # Reorder to [B, G, R] for numpy indexing compatibility
        # Actually keep as [R, G, B] and index accordingly

    return {
        "type": lut_type,
        "size": size,
        "table": table,
        "domain_min": domain_min,
        "domain_max": domain_max,
    }


def apply_3d_lut(arr: np.ndarray, lut: dict, intensity: float = 1.0) -> np.ndarray:
    """Apply a 3D LUT to an RGB image array using trilinear interpolation.

    Args:
        arr: float32 array, shape (H, W, 3), values 0–255.
        lut: parsed LUT dict from parse_cube().
        intensity: 0.0–1.0, blend with original.

    Returns:
        np.ndarray, shape (H, W, 3), values 0–255.
    """
    if lut["type"] != "3D":
        raise ValueError("apply_3d_lut expects a 3D LUT")

    size = lut["size"]
    table = lut["table"]  # (size, size, size, 3) — [R, G, B]
    dmin = lut["domain_min"]
    dmax = lut["domain_max"]

    # Normalize image to 0–1, then to LUT domain
    normalized = arr / 255.0
    domain_range = dmax - dmin
    # Clamp to domain
    normalized = np.clip(normalized, dmin, dmax)
    # Map to 0–(size-1) index space
    idx = (normalized - dmin) / domain_range * (size - 1)

    # Split into R, G, B indices
    r_idx = idx[..., 0]
    g_idx = idx[..., 1]
    b_idx = idx[..., 2]

    # Floor and fractional parts
    r0 = np.floor(r_idx).astype(np.int32)
    g0 = np.floor(g_idx).astype(np.int32)
    b0 = np.floor(b_idx).astype(np.int32)
    r1 = np.minimum(r0 + 1, size - 1)
    g1 = np.minimum(g0 + 1, size - 1)
    b1 = np.minimum(b0 + 1, size - 1)

    rf = r_idx - r0
    gf = g_idx - g0
    bf = b_idx - b0

    # Trilinear interpolation
    # table shape: (size, size, size, 3) indexed as [R, G, B, channel]
    def sample(r, g, b):
        return table[r, g, b]  # returns (H, W, 3)

    c000 = sample(r0, g0, b0)
    c100 = sample(r1, g0, b0)
    c010 = sample(r0, g1, b0)
    c110 = sample(r1, g1, b0)
    c001 = sample(r0, g0, b1)
    c101 = sample(r1, g0, b1)
    c011 = sample(r0, g1, b1)
    c111 = sample(r1, g1, b1)

    # Interpolate along R
    c00 = c000 * (1 - rf[..., None]) + c100 * rf[..., None]
    c01 = c001 * (1 - rf[..., None]) + c101 * rf[..., None]
    c10 = c010 * (1 - rf[..., None]) + c110 * rf[..., None]
    c11 = c011 * (1 - rf[..., None]) + c111 * rf[..., None]

    # Interpolate along G
    c0 = c00 * (1 - gf[..., None]) + c10 * gf[..., None]
    c1 = c01 * (1 - gf[..., None]) + c11 * gf[..., None]

    # Interpolate along B
    result = c0 * (1 - bf[..., None]) + c1 * bf[..., None]

    # Convert back to 0–255
    result = result * 255.0

    # Blend with original
    if intensity < 1.0:
        result = arr * (1.0 - intensity) + result * intensity

    return np.clip(result, 0, 255)


def apply_1d_lut(arr: np.ndarray, lut: dict, intensity: float = 1.0) -> np.ndarray:
    """Apply a 1D LUT (per-channel lookup)."""
    if lut["type"] != "1D":
        raise ValueError("apply_1d_lut expects a 1D LUT")

    size = lut["size"]
    table = lut["table"]  # (size, 3)
    dmin = lut["domain_min"]
    dmax = lut["domain_max"]

    normalized = arr / 255.0
    normalized = np.clip(normalized, dmin, dmax)
    idx = ((normalized - dmin) / (dmax - dmin) * (size - 1)).astype(np.int32)
    idx = np.clip(idx, 0, size - 1)

    # Apply per-channel LUT
    result = np.zeros_like(arr)
    for ch in range(3):
        result[..., ch] = table[idx[..., ch], ch] * 255.0

    if intensity < 1.0:
        result = arr * (1.0 - intensity) + result * intensity

    return np.clip(result, 0, 255)


def apply_lut(arr: np.ndarray, lut_path: str | None, intensity: float = 1.0) -> np.ndarray:
    """Parse and apply a LUT file. No-op if path is None.

    Args:
        arr: float32 array (H, W, 3), 0–255.
        lut_path: Path to .cube file or None.
        intensity: Blend factor 0–1.

    Returns:
        Processed array, same shape and range.
    """
    if lut_path is None:
        return arr

    lut = parse_cube(lut_path)
    if lut["type"] == "3D":
        return apply_3d_lut(arr, lut, intensity)
    else:
        return apply_1d_lut(arr, lut, intensity)