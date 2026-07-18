"""Radial vignette effect with adjustable size, feather, and roundness."""

from __future__ import annotations

import numpy as np


def apply_vignette(
    arr: np.ndarray,
    amount: int = 0,
    size: int = 50,
    feather: int = 50,
    roundness: int = 0,
) -> np.ndarray:
    """Apply radial vignette to image.

    Args:
        arr: float32 array (H, W, 3), 0–255.
        amount: -100 to 100. Negative = darken edges, positive = brighten edges.
        size: 0–100, radius of unaffected center (0=small, 100=full).
        feather: 0–100, softness of vignette edge (0=hard, 100=very soft).
        roundness: -100 to 100, shape (-100=oval vertical, 0=circle, 100=rectangle).

    Returns:
        Processed array, 0–255.
    """
    if amount == 0:
        return arr

    h, w = arr.shape[:2]

    # Create coordinate grids centered at image center
    y, x = np.ogrid[:h, :w]
    cy, cx = h / 2.0, w / 2.0

    # Normalize coordinates to -1..1
    yn = (y - cy) / cy
    xn = (x - cx) / cx

    # Apply roundness: interpolate between circle and rectangle
    # roundness=0 → circle (euclidean), roundness=100 → rectangle (chebyshev)
    r_norm = roundness / 100.0
    # Circle distance
    dist_circle = np.sqrt(xn**2 + yn**2)
    # Rectangle distance (max of normalized coords)
    dist_rect = np.maximum(np.abs(xn), np.abs(yn))
    # Blend
    dist = dist_circle * (1 - r_norm) + dist_rect * r_norm

    # Size: controls where vignette starts (0=center, 100=edges)
    # radius = 1.0 - size/100 * 0.8 → at size=100, vignette starts at 0.2
    radius = 1.0 - (size / 100.0) * 0.8

    # Feather: controls transition softness
    feather_width = 0.1 + (feather / 100.0) * 0.9  # 0.1 to 1.0

    # Vignette mask: 1.0 inside radius, 0.0 outside
    # Smooth transition over feather_width
    mask = np.clip(1.0 - (dist - radius) / feather_width, 0, 1)

    # Amount: -100 to 100 → 0.0 to 2.0 multiplier for edges
    # amount=-100 → edges at 0.0 (black), amount=100 → edges at 2.0 (bright)
    # amount=0 → no change (mask * 1.0 everywhere)
    strength = abs(amount) / 100.0

    if amount < 0:
        # Darken edges: multiply by (1 - strength * (1 - mask))
        factor = 1.0 - strength * (1.0 - mask)
    else:
        # Brighten edges: add strength * (1 - mask) * avg_brightness
        avg = arr.mean()
        factor = 1.0 + strength * (1.0 - mask) * 0.5

    # Apply per-pixel
    result = arr * factor[..., np.newaxis]

    return np.clip(result, 0, 255)