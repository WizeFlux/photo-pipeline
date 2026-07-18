"""Saturation and vibrance (smart saturation that protects skin tones)."""

from __future__ import annotations

import numpy as np


def rgb_to_hsl(arr: np.ndarray) -> np.ndarray:
    """Convert RGB array (0–255) to HSL (H: 0–360, S: 0–1, L: 0–1)."""
    rgb = arr / 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    maxc = np.max(rgb, axis=-1)
    minc = np.min(rgb, axis=-1)
    delta = maxc - minc

    # Lightness
    l = (maxc + minc) / 2.0

    # Saturation
    s = np.where(delta == 0, 0.0, np.where(l < 0.5, delta / (maxc + minc + 1e-10), delta / (2.0 - maxc - minc + 1e-10)))

    # Hue
    rc = np.where(delta == 0, 0.0, (maxc - r) / (delta + 1e-10))
    gc = np.where(delta == 0, 0.0, (maxc - g) / (delta + 1e-10))
    bc = np.where(delta == 0, 0.0, (maxc - b) / (delta + 1e-10))

    h = np.where(maxc == r, bc - gc, np.where(maxc == g, 2.0 + rc - bc, 4.0 + gc - rc))
    h = (h / 6.0) % 1.0  # 0–1
    h = h * 360.0        # 0–360

    return np.stack([h, s, l], axis=-1)


def hsl_to_rgb(hsl: np.ndarray) -> np.ndarray:
    """Convert HSL back to RGB (0–255)."""
    h = hsl[..., 0] / 360.0
    s = hsl[..., 1]
    l = hsl[..., 2]

    c = (1.0 - np.abs(2.0 * l - 1.0)) * s
    x = c * (1.0 - np.abs((h * 6.0) % 2.0 - 1.0))
    m = l - c / 2.0

    # Sector
    sector = (h * 6.0).astype(int) % 6

    r = np.choose(sector, [c, x, 0, 0, x, c]) + m
    g = np.choose(sector, [x, c, c, x, 0, 0]) + m
    b = np.choose(sector, [0, 0, x, c, c, x]) + m

    return np.clip(np.stack([r, g, b], axis=-1) * 255.0, 0, 255)


def apply_saturation(
    arr: np.ndarray,
    amount: int = 0,
    vibrance: int = 0,
) -> np.ndarray:
    """Apply saturation and vibrance adjustments.

    Args:
        arr: float32 array (H, W, 3), 0–255.
        amount: -100 to 100, global saturation (all colors equally).
        vibrance: -100 to 100, smart saturation (boosts muted colors,
            protects already-saturated colors and skin tones).

    Returns:
        Processed array, 0–255.
    """
    if amount == 0 and vibrance == 0:
        return arr

    hsl = rgb_to_hsl(arr)
    s = hsl[..., 1]

    # Global saturation: simple multiply
    if amount != 0:
        s = s * (1.0 + amount / 100.0)
        s = np.clip(s, 0, 1)

    # Vibrance: boost low-saturation more than high
    if vibrance != 0:
        v = vibrance / 100.0
        # Weight: less adjustment for already-saturated pixels
        weight = 1.0 - s * 0.8  # 1.0 at s=0, 0.2 at s=1
        s = s + v * weight * 0.6
        s = np.clip(s, 0, 1)

        # Protect skin tones (hue ~10–50 degrees)
        h = hsl[..., 0]
        skin_mask = ((h > 10) & (h < 50)).astype(np.float32)
        s = s * (1.0 - skin_mask * abs(v) * 0.3)

    hsl[..., 1] = s
    return hsl_to_rgb(hsl)