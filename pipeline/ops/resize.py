"""Resize and save in various output formats (WebP, JPEG, AVIF, TIFF)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


def resize_and_save(
    img: Image.Image,
    output_path: str | Path,
    width: int | None = None,
    height: int | None = None,
    fmt: str = "jpeg",
    quality: int = 90,
) -> Path:
    """Resize image and save in specified format.

    Args:
        img: PIL Image.
        output_path: Destination file path.
        width: Target width in px. None = keep aspect from height.
        height: Target height in px. None = keep aspect from width.
            If both None, keep original size.
        fmt: "jpeg", "webp", "avif", "tiff".
        quality: 1–100 (for jpeg, webp, avif).

    Returns:
        Path to saved file (format extension may override input).
    """
    # Determine output format and extension
    fmt = fmt.lower()
    ext_map = {
        "jpeg": ".jpg",
        "jpg": ".jpg",
        "webp": ".webp",
        "avif": ".avif",
        "tiff": ".tiff",
        "tif": ".tiff",
    }
    ext = ext_map.get(fmt, ".jpg")
    output_path = Path(output_path)
    if output_path.suffix.lower() not in [".jpg", ".jpeg", ".webp", ".avif", ".tiff", ".tif"]:
        output_path = output_path.with_suffix(ext)

    # Resize if needed
    if width is not None or height is not None:
        orig_w, orig_h = img.size
        if width is not None and height is not None:
            # Both specified — resize to exact dimensions
            new_size = (width, height)
        elif width is not None:
            # Width specified — maintain aspect ratio
            new_h = int(orig_h * width / orig_w)
            new_size = (width, new_h)
        else:
            # Height specified — maintain aspect ratio
            new_w = int(orig_w * height / orig_h)
            new_size = (new_w, height)

        img = img.resize(new_size, Image.LANCZOS)

    # Save
    pil_format = {
        "jpeg": "JPEG",
        "jpg": "JPEG",
        "webp": "WEBP",
        "avif": "AVIF",
        "tiff": "TIFF",
        "tif": "TIFF",
    }.get(fmt, "JPEG")

    save_kwargs = {}
    if pil_format in ("JPEG", "WEBP", "AVIF"):
        save_kwargs["quality"] = quality
        if pil_format == "JPEG":
            save_kwargs["subsampling"] = 0  # 4:4:4 chroma, best quality
        if pil_format == "WEBP":
            save_kwargs["method"] = 6  # best compression

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), format=pil_format, **save_kwargs)

    return output_path