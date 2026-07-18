"""Aspect ratio crop with gravity and offset control."""

from __future__ import annotations

import numpy as np
from PIL import Image

# Gravity to (offset_x, offset_y) multipliers
GRAVITY_MAP = {
    "center":      (0.0, 0.0),
    "left":        (-0.5, 0.0),
    "right":       (0.5, 0.0),
    "top":         (0.0, -0.5),
    "bottom":      (0.0, 0.5),
    "topleft":     (-0.5, -0.5),
    "topright":    (0.5, -0.5),
    "bottomleft":  (-0.5, 0.5),
    "bottomright": (0.5, 0.5),
}


def parse_aspect_ratio(ratio: str | None) -> float | None:
    """Parse '4:3' → 4/3. None → None."""
    if ratio is None:
        return None
    if ":" in ratio:
        w, h = ratio.split(":")
        return float(w) / float(h)
    return float(ratio)


def crop_image(
    img: Image.Image,
    aspect_ratio: str | None = None,
    gravity: str = "center",
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> Image.Image:
    """Crop image to target aspect ratio.

    Args:
        img: PIL Image.
        aspect_ratio: "4:3", "16:9", "1:1", or None (no crop).
        gravity: Anchor point for crop.
        offset_x: -1.0 to 1.0, additional horizontal shift.
        offset_y: -1.0 to 1.0, additional vertical shift.

    Returns:
        Cropped PIL Image.
    """
    target_ratio = parse_aspect_ratio(aspect_ratio)
    if target_ratio is None:
        return img

    w, h = img.size
    current_ratio = w / h

    if current_ratio > target_ratio:
        # Image is wider — crop width
        new_w = int(h * target_ratio)
        new_h = h
    else:
        # Image is taller — crop height
        new_w = w
        new_h = int(w / target_ratio)

    # Calculate offset from gravity
    gx, gy = GRAVITY_MAP.get(gravity, (0.0, 0.0))

    # Center + gravity + user offset
    x = (w - new_w) // 2 + int(gx * (w - new_w) * 0.5) + int(offset_x * (w - new_w) * 0.5)
    y = (h - new_h) // 2 + int(gy * (h - new_h) * 0.5) + int(offset_y * (h - new_h) * 0.5)

    # Clamp to valid range
    x = max(0, min(x, w - new_w))
    y = max(0, min(y, h - new_h))

    return img.crop((x, y, x + new_w, y + new_h))