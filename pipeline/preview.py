"""Preview generation: before/after comparison and grid layouts."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .processor import Pipeline


def generate_preview(
    pipe: Pipeline,
    input_path: str | Path,
    output_path: str | Path,
    preview_width: int = 800,
) -> None:
    """Generate a before/after side-by-side preview.

    Args:
        pipe: Configured Pipeline instance.
        input_path: Original image path.
        output_path: Where to save the preview.
        preview_width: Width of each half (before/after) in pixels.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    # Load original
    with Image.open(input_path) as img:
        if img.mode != "RGB":
            img = img.convert("RGB")
        # Apply same crop as pipeline for fair comparison
        from .ops.crop import crop_image
        cfg = pipe.config.get("crop", {})
        img = crop_image(
            img,
            aspect_ratio=cfg.get("aspect_ratio"),
            gravity=cfg.get("gravity", "center"),
            offset_x=cfg.get("offset_x", 0.0),
            offset_y=cfg.get("offset_y", 0.0),
        )
        # Resize for preview
        w, h = img.size
        new_h = int(h * preview_width / w)
        before = img.resize((preview_width, new_h), Image.LANCZOS)

    # Process image
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        out = pipe.process_image(input_path, tmp)
        if out is None:
            raise RuntimeError("Processing failed")
        with Image.open(out) as img:
            w, h = img.size
            new_h = int(h * preview_width / w)
            after = img.resize((preview_width, new_h), Image.LANCZOS)

    # Ensure same height
    target_h = max(before.size[1], after.size[1])
    if before.size[1] != target_h:
        before = before.resize((preview_width, target_h), Image.LANCZOS)
    if after.size[1] != target_h:
        after = after.resize((preview_width, target_h), Image.LANCZOS)

    # Side-by-side
    combined = Image.new("RGB", (preview_width * 2, target_h), (20, 20, 20))
    combined.paste(before, (0, 0))
    combined.paste(after, (preview_width, 0))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.save(str(output_path), "JPEG", quality=90)


def generate_grid(
    input_dir: str | Path,
    output_path: str | Path,
    cols: int = 5,
    thumb_width: int = 400,
) -> None:
    """Generate a grid of thumbnails from all images in a directory.

    Args:
        input_dir: Directory with images.
        output_path: Output file path.
        cols: Number of columns in grid.
        thumb_width: Width of each thumbnail.
    """
    input_dir = Path(input_dir)
    files = sorted([
        f for f in input_dir.iterdir()
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif")
        and f.is_file()
    ])

    if not files:
        return

    thumbs = []
    thumb_height = None

    for f in files:
        with Image.open(f) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            w, h = img.size
            th = int(h * thumb_width / w)
            if thumb_height is None:
                thumb_height = th
            thumb = img.resize((thumb_width, th), Image.LANCZOS)
            # Normalize height
            if thumb.size[1] != thumb_height:
                thumb = thumb.resize((thumb_width, thumb_height), Image.LANCZOS)
            thumbs.append(thumb)

    rows = (len(thumbs) + cols - 1) // cols
    grid = Image.new("RGB", (thumb_width * cols, thumb_height * rows), (20, 20, 20))

    for i, thumb in enumerate(thumbs):
        x = (i % cols) * thumb_width
        y = (i // cols) * thumb_height
        grid.paste(thumb, (x, y))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    grid.save(str(output_path), "JPEG", quality=90)