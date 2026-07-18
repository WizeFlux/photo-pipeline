"""Main application window — assembles all panels and wires signals.

Layout:
  ┌─────────────────────────────────────────────────────────────┐
  │ Toolbar: [Open Image] [3rd Profile ▾] [Reset]               │
  ├═════════════════════════════════════════════════════════════┤  ← drag
  │ Previews (3 in a row) — height resizable via splitter        │
  ├─────────────────────────────────────────────────────────────┤
  │ Row 1: Exposure | Contrast | WB | Saturation  (one row)     │
  │ Row 2: LUT | Profiles | Batch                  (one row)     │
  ├─────────────────────────────────────────────────────────────┤
  │ Stats (transposed) + Plots (scrollable, resizable heights)   │
  └─────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from pipeline.gpu_ops import DEVICE
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
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── Toolbar (fixed) ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        open_btn = QPushButton("📂 Open")
        open_btn.clicked.connect(self._on_open)
        toolbar.addWidget(open_btn)

        toolbar.addSpacing(8)
        lbl = QLabel("3rd:")
        lbl.setObjectName("value-label")
        toolbar.addWidget(lbl)
        self.third_profile_combo = QComboBox()
        self.third_profile_combo.setMinimumWidth(140)
        self._refresh_profile_combo(self.third_profile_combo)
        self.third_profile_combo.currentTextChanged.connect(self._schedule_preview)
        toolbar.addWidget(self.third_profile_combo)

        toolbar.addStretch()
        reset_btn = QPushButton("↺ Reset")
        reset_btn.clicked.connect(self._on_reset)
        toolbar.addWidget(reset_btn)
        root.addLayout(toolbar)

        # ── Row 1: adjustments (5 groups: Exposure|Contrast|WB|Sat|LUT) ──
        self.adjustments = AdjustmentsPanel()
        self.adjustments.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        root.addWidget(self.adjustments)

        # ── Row 2: Profiles + Batch (fixed height) ──
        controls2 = QWidget()
        controls2.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls2_layout = QHBoxLayout(controls2)
        controls2_layout.setContentsMargins(0, 0, 0, 0)
        controls2_layout.setSpacing(4)
        self.profiles_panel = ProfilesPanel()
        self.batch_panel = BatchPanel()
        controls2_layout.addWidget(self.profiles_panel, 1)
        controls2_layout.addWidget(self.batch_panel, 2)
        root.addWidget(controls2)

        # ── Splitter: previews (top, resizable) | plots (bottom, resizable) ──
        # Only these two sections are resizable. Controls above are fixed.
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setHandleWidth(8)

        # Previews row
        previews_widget = QWidget()
        previews_layout = QHBoxLayout(previews_widget)
        previews_layout.setContentsMargins(0, 0, 0, 0)
        previews_layout.setSpacing(3)
        self.viewer_original = ImageViewer("Original")
        self.viewer_live = ImageViewer("Live Sliders")
        self.viewer_profile = ImageViewer("Profile")
        for v in (self.viewer_original, self.viewer_live, self.viewer_profile):
            previews_layout.addWidget(v, 1)
        self.main_splitter.addWidget(previews_widget)

        # Plots panel
        self.plots_panel = PlotsPanel()
        self.main_splitter.addWidget(self.plots_panel)

        # Only previews and plots stretch; both resizable via the splitter handle
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 4)
        self.main_splitter.setSizes([300, 400])

        root.addWidget(self.main_splitter, 1)

        # ── Status bar ──
        self.statusBar().showMessage(f"Device: {DEVICE}")

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
        params = params_from_values(self._collect_params())
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
        params = params_from_values(self._collect_params())
        self.batch_panel.set_status("Processing…")
        self._batch_worker = BatchWorker(input_dir, output_dir, params, use_gpu)
        self._batch_worker.finished_batch.connect(self._on_batch_done)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_worker.start()

    def _on_batch_done(self, success: int, failed: int, output_dir: str) -> None:
        self.batch_panel.set_status(
            f"✅ {success} ok, ❌ {failed} failed → {output_dir}"
        )
        self.statusBar().showMessage(f"Batch done: {success} ok, {failed} failed")

    def _on_batch_failed(self, msg: str) -> None:
        self.batch_panel.set_status(f"Error: {msg}")

    # ─── Params collection ────────────────────────────────────────────────────

    def _collect_params(self) -> dict:
        return self.adjustments.get_params()

    # ─── Preview pipeline ─────────────────────────────────────────────────────

    def _schedule_preview(self, *_args) -> None:
        """Debounce slider changes — wait 120ms before reprocessing."""
        self._debounce.start(120)

    def _run_preview(self) -> None:
        if not self._image_path:
            return
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.quit()
            self._preview_worker.wait(200)

        params = self._collect_params()
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
        params = params_from_values(self._collect_params())
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