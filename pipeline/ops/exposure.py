"""Exposure, gamma, highlight/shadow recovery."""

from __future__ import annotations

import numpy as np


def apply_exposure(
    arr: np.ndarray,
    ev: float = 0.0,
    gamma: float = 1.0,
    highlights: int = 0,
    shadows: int = 0,
) -> np.ndarray:
    """Apply exposure, gamma, and highlight/shadow adjustments.

    Args:
        arr: float32 array (H, W, 3), 0–255.
        ev: Exposure compensation in EV (-3 to +3).
        gamma: Gamma curve (0.5–2.5, 1.0 = no change).
        highlights: -100 to 100, positive = recover highlights (darken).
        shadows: -100 to 100, positive = lift shadows (brighten).

    Returns:
        Processed array, 0–255.
    """
    result = arr.copy()

    # Exposure: linear multiplication (EV stops)
    if ev != 0.0:
        result = result * (2.0 ** ev)

    # Gamma: apply gamma curve in 0–1 space
    if gamma != 1.0:
        normalized = result / 255.0
        normalized = np.clip(normalized, 0, 1) ** (1.0 / gamma)
        result = normalized * 255.0

    # Highlights recovery: compress bright areas
    if highlights > 0:
        h_factor = highlights / 100.0
        normalized = result / 255.0
        # Only affect upper range (0.5–1.0)
        mask = np.clip((normalized - 0.5) * 2, 0, 1)
        compressed = normalized * (1 - mask * h_factor * 0.5)
        result = compressed * 255.0
    elif highlights < 0:
        h_factor = abs(highlights) / 100.0
        normalized = result / 255.0
        mask = np.clip((normalized - 0.5) * 2, 0, 1)
        boosted = normalized + mask * h_factor * 0.3
        result = np.clip(boosted, 0, 1) * 255.0

    # Shadows lift: brighten dark areas
    if shadows > 0:
        s_factor = shadows / 100.0
        normalized = result / 255.0
        # Only affect lower range (0.0–0.5)
        mask = np.clip((0.5 - normalized) * 2, 0, 1)
        lifted = normalized + mask * s_factor * 0.3
        result = np.clip(lifted, 0, 1) * 255.0
    elif shadows < 0:
        s_factor = abs(shadows) / 100.0
        normalized = result / 255.0
        mask = np.clip((0.5 - normalized) * 2, 0, 1)
        crushed = normalized * (1 - mask * s_factor * 0.5)
        result = crushed * 255.0

    return np.clip(result, 0, 255)