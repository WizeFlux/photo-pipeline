"""Background workers for image processing — keep the UI responsive.

PreviewWorker — processes one image with live params + optional 3rd profile.
BatchWorker   — processes a directory of images, emitting progress.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image
from PySide6.QtCore import QThread, Signal

from pipeline.batch import batch_process_parallel
from pipeline.gpu_ops import gpu_process_from_pil
from qt_app.state import load_profile_params, params_from_values


# ─── Preview ─────────────────────────────────────────────────────────────────

class PreviewWorker(QThread):
    """Process one image: returns (original, live, profile?) arrays.

    Downsizes large images for fast interactive preview.
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
            img = Image.open(self._image_path)
            if img.mode != "RGB":
                img = img.convert("RGB")
            # Downscale for preview
            max_w = 1200
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)

            orig = np.array(img)
            live = np.array(gpu_process_from_pil(img, self._params))

            profile = None
            prof_name = self._third_profile_name
            if prof_name and prof_name != "None":
                prof_params = load_profile_params(prof_name)
                if prof_params is not None:
                    profile = np.array(gpu_process_from_pil(img, prof_params))

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