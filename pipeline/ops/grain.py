"""Film grain: Gaussian noise with adjustable size and monochrome/color mode."""

from __future__ import annotations

import numpy as np


def apply_grain(
    arr: np.ndarray,
    amount: int = 0,
    size: int = 1,
    monochrome: bool = True,
) -> np.ndarray:
    """Add film grain to image.

    Args:
        arr: float32 array (H, W, 3), 0–255.
        amount: 0–100, grain intensity.
        size: 1–10, grain particle size (applied via Gaussian blur of noise).
        monochrome: True = grayscale grain, False = color noise.

    Returns:
        Processed array, 0–255.
    """
    if amount == 0:
        return arr

    h, w = arr.shape[:2]
    strength = amount / 100.0 * 25.0  # max ±25 brightness

    if monochrome:
        # Single noise channel, applied equally to R, G, B
        noise = np.random.randn(h, w).astype(np.float32) * strength
        noise = np.stack([noise, noise, noise], axis=-1)
    else:
        # Independent noise per channel
        noise = np.random.randn(h, w, 3).astype(np.float32) * strength

    # If size > 1, blur the noise for larger grain particles
    if size > 1:
        from PIL import Image, ImageFilter

        # Convert noise to PIL for blurring
        noise_img = Image.fromarray(
            np.clip((noise + 128), 0, 255).astype(np.uint8), 'RGB'
        )
        blur_radius = size - 1
        noise_img = noise_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        noise = np.array(noise_img, dtype=np.float32) - 128.0

    result = arr + noise

    return np.clip(result, 0, 255)