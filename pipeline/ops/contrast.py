"""Contrast: linear, S-curve (sigmoid), and black/white point clipping."""

from __future__ import annotations

import numpy as np


def apply_contrast(
    arr: np.ndarray,
    amount: int = 0,
    s_curve: int = 0,
    black_point: int = 0,
    white_point: int = 255,
) -> np.ndarray:
    """Apply contrast adjustments.

    Args:
        arr: float32 array (H, W, 3), 0–255.
        amount: -100 to 100, linear contrast around 128.
        s_curve: 0–100, sigmoid S-curve contrast (more film-like).
        black_point: 0–50, values below this are clipped to 0.
        white_point: 205–255, values above this are clipped to 255.

    Returns:
        Processed array, 0–255.
    """
    result = arr.copy()

    # Black/white point clipping
    if black_point > 0:
        result = np.where(result < black_point, 0, (result - black_point) * 255.0 / (255 - black_point))
    if white_point < 255:
        result = np.where(result > white_point, 255, result * 255.0 / white_point)

    # Linear contrast
    if amount != 0:
        factor = 1.0 + amount / 100.0
        result = 128.0 + (result - 128.0) * factor

    # S-curve contrast (sigmoid)
    if s_curve > 0:
        strength = s_curve / 100.0
        normalized = np.clip(result / 255.0, 0, 1)
        # Sigmoid: centered at 0.5, strength controls steepness
        k = 5.0 * strength  # steepness
        sigmoid = 1.0 / (1.0 + np.exp(-k * (normalized - 0.5)))
        # Blend between linear and sigmoid
        result = (normalized * (1 - strength) + sigmoid * strength) * 255.0

    return np.clip(result, 0, 255)