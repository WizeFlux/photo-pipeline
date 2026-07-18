"""White balance: temperature (warm/cool) and tint (green/magenta)."""

from __future__ import annotations

import numpy as np


def apply_white_balance(
    arr: np.ndarray,
    temperature: int = 0,
    tint: int = 0,
) -> np.ndarray:
    """Adjust white balance via temperature and tint.

    Args:
        arr: float32 array (H, W, 3), 0–255.
        temperature: -100 (cool/blue) to 100 (warm/amber).
            Positive: increase R, decrease B.
            Negative: decrease R, increase B.
        tint: -100 (green) to 100 (magenta).
            Positive: increase R and B, decrease G.
            Negative: decrease R and B, increase G.

    Returns:
        Processed array, 0–255.
    """
    result = arr.copy().astype(np.float32)

    # Temperature: scale R and B
    if temperature != 0:
        t = temperature / 100.0
        # Warm: R up, B down. Cool: R down, B up.
        r_gain = 1.0 + t * 0.15
        b_gain = 1.0 - t * 0.15
        result[..., 0] *= r_gain
        result[..., 2] *= b_gain

    # Tint: scale G vs R+B
    if tint != 0:
        t = tint / 100.0
        # Magenta: G down, R and B up slightly
        # Green: G up, R and B down slightly
        g_gain = 1.0 - t * 0.12
        rb_gain = 1.0 + t * 0.06
        result[..., 0] *= rb_gain
        result[..., 1] *= g_gain
        result[..., 2] *= rb_gain

    return np.clip(result, 0, 255)