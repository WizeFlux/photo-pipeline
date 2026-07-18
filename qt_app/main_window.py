"""Main application window — assembles all panels and wires signals.

Layout:
  ┌─────────────────────────────────────────────────────────────┐
  │ Toolbar: [Open Image] [3rd Profile ▾] [Reset]               │
  ├──────────────────────────┬──────────────────────────────────┤
  │ Previews (3 in a row)     │ Adjustments  │ Profiles         │
  │                           │              │ Batch            │
  │                           │              │                  │
  ├───────────────────────────┴──────────────┴──────────────────┤
  │ Plots + Stats table (scrollable)                            │
  └─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from pipeline.gpu_ops import DEVICE, gpu_process_from_pil
from qt_app.state import (
    load_profile_params, params_from_values, save_profile,
)
from qt_app.theme import apply_theme
from qt_app.widgets.adjustments import AdjustmentsPanel
from qt_app.widgets.batch import BatchPanel
from qt_app.widgets.image_viewer import ImageViewer
from qt_app.widgets.plots_panel import PlotsPanel
from qt_app.widgets.profiles import ProfilesPanel
from qt_app.workers import BatchWorker, PreviewWorker


class MainWindow(QMainWindow):
    """Top-level window orchestrating all panels."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Photo Pipeline")
        self.resize(1400, 900)

        self._image_path: str | None = None
        self._orig_arr = None
        self._live_arr = None
        self._profile_arr = None
        self._preview_worker: PreviewWorker | None = None
        self._batch_worker: BatchWorker | None = None
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._run_preview)

        self._build_ui()
        self._connect_signals()

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ── Toolbar ──
        toolbar = QHBoxLayout()
        open_btn = QPushButton("📂 Open Image")
        open_btn.clicked.connect(self._on_open)
        toolbar.addWidget(open_btn)

        toolbar.addSpacing(16)
        toolbar.addWidget(self._label("3rd Profile:"))
        self.third_profile_combo = QComboBox()
        self.third_profile_combo.setMinimumWidth(160)
        self._refresh_profile_combo(self.third_profile_combo)
        self.third_profile_combo.currentTextChanged.connect(self._schedule_preview)
        toolbar.addWidget(self.third_profile_combo)

        toolbar.addStretch()
        reset_btn = QPushButton("↺ Reset")
        reset_btn.clicked.connect(self._on_reset)
        toolbar.addWidget(reset_btn)
        root.addLayout(toolbar)

        # ── Previews row ──
        previews_row = QHBoxLayout()
        self.viewer_original = ImageViewer("Original")
        self.viewer_live = ImageViewer("Live Sliders")
        self.viewer_profile = ImageViewer("Profile")
        for v in (self.viewer_original, self.viewer_live, self.viewer_profile):
            previews_row.addWidget(v, 1)
        root.addLayout(previews_row, 0)

        # ── Middle: adjustments + right column (profiles, batch) ──
        splitter = QSplitter(Qt.Horizontal)

        self.adjustments = AdjustmentsPanel()
        splitter.addWidget(self._wrap_scroll(self.adjustments))

        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.profiles_panel = ProfilesPanel()
        right_layout.addWidget(self.profiles_panel)
        self.batch_panel = BatchPanel()
        right_layout.addWidget(self.batch_panel)
        right_layout.addStretch()
        splitter.addWidget(self._wrap_scroll(right_col))

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        # ── Bottom: plots + stats ──
        self.plots_panel = PlotsPanel()
        root.addWidget(self._wrap_scroll(self.plots_panel), 2)

        # ── Status bar ──
        self.statusBar().showMessage(f"Device: {DEVICE}")

    def _label(self, text: str):
        from PySide6.QtWidgets import QLabel
        lbl = QLabel(text)
        lbl.setObjectName("value-label")
        return lbl

    def _wrap_scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    # ─── Signal wiring ────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.adjustments.paramsChanged.connect(self._schedule_preview)
        self.profiles_panel.applyProfile.connect(self._on_apply_profile)
        self.profiles_panel.saveProfile.connect(self._on_save_profile)
        self.profiles_panel.profilesChanged.connect(self._on_profiles_changed)
        self.batch_panel.runBatch.connect(self._on_run_batch)

    # ─── Profile combo helpers ────────────────────────────────────────────────

    def _refresh_profile_combo(self, combo: QComboBox) -> None:
        from qt_app.state import list_profiles
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("None")
        combo.addItems(list_profiles())
        if combo.findText(current) >= 0:
            combo.setCurrentText(current)
        combo.blockSignals(False)

    def _on_profiles_changed(self) -> None:
        self.profiles_panel.refresh()
        self._refresh_profile_combo(self.third_profile_combo)

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open image", "",
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.bmp)",
        )
        if path:
            self._image_path = path
            self.statusBar().showMessage(f"Loaded: {Path(path).name}")
            self._run_preview()

    def _on_reset(self) -> None:
        self.adjustments.reset()

    def _on_apply_profile(self, name: str) -> None:
        params = load_profile_params(name)
        if params is not None:
            self.adjustments.set_params(params)
            self._schedule_preview()

    def _on_save_profile(self, name: str) -> None:
        params = params_from_values(self.adjustments.get_params())
        path = save_profile(name, params)
        self.statusBar().showMessage(f"Saved profile: {Path(path).name}")
        self._on_profiles_changed()

    def _on_run_batch(self, input_dir: str, output_dir: str, use_gpu: bool) -> None:
        if not input_dir or not output_dir:
            self.batch_panel.set_status("Enter both directories.")
            return
        if not Path(input_dir).is_dir():
            self.batch_panel.set_status("Input directory not found.")
            return
        params = params_from_values(self.adjustments.get_params())
        self.batch_panel.set_status("Processing…")
        self._batch_worker = BatchWorker(input_dir, output_dir, params, use_gpu)
        self._batch_worker.finished_batch.connect(self._on_batch_done)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_worker.start()

    def _on_batch_done(self, success: int, failed: int, output_dir: str) -> None:
        self.batch_panel.set_status(
            f"✅ {success} processed, ❌ {failed} failed → {output_dir}"
        )
        self.statusBar().showMessage(f"Batch done: {success} ok, {failed} failed")

    def _on_batch_failed(self, msg: str) -> None:
        self.batch_panel.set_status(f"Error: {msg}")

    # ─── Preview pipeline ─────────────────────────────────────────────────────

    def _schedule_preview(self, *_args) -> None:
        """Debounce slider changes — wait 120ms before reprocessing."""
        self._debounce.start(120)

    def _run_preview(self) -> None:
        if not self._image_path:
            return
        # Cancel an in-flight worker
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.quit()
            self._preview_worker.wait(200)

        params = self.adjustments.get_params()
        third = self.third_profile_combo.currentText()
        self._preview_worker = PreviewWorker(
            self._image_path, params, third if third != "None" else None
        )
        self._preview_worker.finished_preview.connect(self._on_preview_ready)
        self._preview_worker.failed.connect(self._on_preview_failed)
        self._preview_worker.start()

    def _on_preview_ready(self, orig, live, profile) -> None:
        self._orig_arr = orig
        self._live_arr = live
        self._profile_arr = profile
        self.viewer_original.set_array(orig)
        self.viewer_live.set_array(live)
        if profile is not None:
            self.viewer_profile.set_array(profile)
            prof_name = self.third_profile_combo.currentText()
            self.viewer_profile.set_title(prof_name)
        else:
            self.viewer_profile.set_array(None)
            self.viewer_profile.set_title("Profile")
        # Update plots
        params = params_from_values(self.adjustments.get_params())
        prof_name = self.third_profile_combo.currentText()
        if prof_name == "None":
            prof_name = None
        self.plots_panel.update_all(orig, live, profile, prof_name, params)

    def _on_preview_failed(self, msg: str) -> None:
        self.statusBar().showMessage(f"Preview error: {msg}")


def run() -> None:
    """Application entry point."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run()