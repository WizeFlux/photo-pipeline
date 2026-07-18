"""Background workers for image processing — keep the UI responsive.

PreviewWorker — processes one image with live params + optional 3rd profile.
BatchWorker   — processes a directory of images, emitting progress.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal

from pipeline.batch import batch_process_parallel
from pipeline.gpu_ops import gpu_process_from_pil
from qt_app.state import load_profile_params, params_from_values


# ─── Preview cache ────────────────────────────────────────────────────────────

_PREVIEW_CACHE_DIR = Path.home() / ".cache" / "photo-pipeline" / "previews"
_PREVIEW_MAX_W = 800
_PREVIEW_QUALITY = 95


def _preview_cache_key(image_path: str) -> str:
    """md5(path + mtime + size) — invalidates when the file changes."""
    st = os.stat(image_path)
    key = f"{image_path}|{st.st_mtime_ns}|{st.st_size}"
    return hashlib.md5(key.encode()).hexdigest()


def _preview_cache_path(key: str) -> Path:
    return _PREVIEW_CACHE_DIR / f"{key}.jpg"


def _load_preview_image(image_path: str) -> Image.Image:
    """Load a downscaled preview image, using the on-disk cache when possible.

    On a cache hit we skip PIL.open of the (potentially large) original file
    entirely and decode the small JPEG instead — ~50-100x faster for big raws.
    On a miss we open + downscale the original and write the cache entry.
    """
    key = _preview_cache_key(image_path)
    cache_file = _preview_cache_path(key)

    if cache_file.exists():
        return Image.open(cache_file).convert("RGB")

    img = Image.open(image_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.width > _PREVIEW_MAX_W:
        ratio = _PREVIEW_MAX_W / img.width
        img = img.resize((_PREVIEW_MAX_W, int(img.height * ratio)), Image.LANCZOS)

    # Write cache (best-effort — never fail the preview over a cache write error)
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        img.save(cache_file, "JPEG", quality=_PREVIEW_QUALITY)
    except OSError:
        pass

    return img


# ─── Preview ─────────────────────────────────────────────────────────────────

class PreviewWorker(QThread):
    """Process one image: returns (original, live, profile?) arrays.

    Downsizes large images for fast interactive preview. Downscaled previews
    are cached on disk (~/.cache/photo-pipeline/previews/) keyed by the source
    file's path + mtime + size, so repeated slider tweaks on the same image
    skip re-decoding the full original.

    Checks isInterruptionRequested() between heavy steps so the caller
    can cancel an in-flight job before it finishes.
    """

    finished_preview = Signal(object, object, object)  # orig, live, profile
    failed = Signal(str)

    def __init__(self, image_path: str, params: dict,
                 third_profile_name: str | None = None, parent=None):
        super().__init__(parent)
        self._image_path = image_path
        self._params = params_from_values(params)
        self._third_profile_name = third_profile_name

    def run(self) -> None:
        try:
            img = _load_preview_image(self._image_path)

            if self.isInterruptionRequested():
                return
            orig = np.array(img)
            live = np.array(gpu_process_from_pil(img, self._params))

            if self.isInterruptionRequested():
                return
            profile = None
            prof_name = self._third_profile_name
            if prof_name and prof_name != "None":
                prof_params = load_profile_params(prof_name)
                if prof_params is not None:
                    profile = np.array(gpu_process_from_pil(img, prof_params))

            if self.isInterruptionRequested():
                return
            self.finished_preview.emit(orig, live, profile)
        except Exception as exc:
            self.failed.emit(str(exc))


# ─── Batch ───────────────────────────────────────────────────────────────────

class BatchWorker(QThread):
    """Process a whole directory in parallel."""

    progress = Signal(int, int)  # done, total
    finished_batch = Signal(int, int, str)  # success, failed, output_dir
    failed = Signal(str)

    def __init__(self, input_dir: str, output_dir: str, params: dict,
                 use_gpu: bool = True, parent=None):
        super().__init__(parent)
        self._input_dir = input_dir
        self._output_dir = output_dir
        self._params = params_from_values(params)
        self._use_gpu = use_gpu

    def run(self) -> None:
        try:
            in_path = Path(self._input_dir)
            files = sorted(
                f for f in in_path.iterdir()
                if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".tif", ".tiff",
                                         ".webp", ".bmp")
            )
            total = len(files)
            if total == 0:
                self.failed.emit("No images found in input directory.")
                return

            # batch_process_parallel does the heavy lifting; we wrap it to
            # emit progress. For simplicity we run it synchronously — on M1 Ultra
            # with 20 workers it's fast enough. For true streaming progress,
            # switch to as_completed.
            results = batch_process_parallel(
                str(in_path), self._output_dir, self._params,
                max_workers=min(os.cpu_count() or 8, 20),
                use_gpu=self._use_gpu,
            )
            success = sum(1 for _, o, e in results if o and not e)
            failed = sum(1 for _, _, e in results if e)
            self.progress.emit(total, total)
            self.finished_batch.emit(success, failed, self._output_dir)
        except Exception as exc:
            self.failed.emit(str(exc))