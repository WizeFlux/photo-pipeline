"""Main application window — toolbar + previews + adjustments + plots.

Layout:
  ┌─────────────────────────────────────────────────────────────┐
  │ [📂 Open] [📋 Profiles] [📁 Batch] [3rd ▾]     [↺ Reset]    │
  ├═════════════════════════════════════════════════════════════┤  ← drag
  │ Previews (3 in a row) — height resizable via splitter        │
  ├─────────────────────────────────────────────────────────────┤
  │ Adjustments: Exposure | Contrast | WB | Sat | LUT           │
  ├═════════════════════════════════════════════════════════════┤  ← drag
  │ Plots: [Left ▾] [Right ▾] + 2 canvases                       │
  └─────────────────────────────────────────────────────────────┘

Profiles and Batch are popup dialogs launched from toolbar buttons.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from pipeline.gpu_ops import DEVICE
from qt_app.state import (
    load_profile_params, params_from_values, save_profile,
)
from qt_app.theme import apply_theme
from qt_app.widgets.adjustments import AdjustmentsPanel
from qt_app.widgets.dialogs import BatchDialog, ProfilesDialog
from qt_app.widgets.image_viewer import ImageViewer
from qt_app.widgets.plots_panel import PlotsPanel
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
        # Status reset timer — transient messages revert to the device label
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._reset_status)

        # Popup dialogs (created lazily)
        self._profiles_dialog: ProfilesDialog | None = None
        self._batch_dialog: BatchDialog | None = None

        self._build_ui()
        self._connect_signals()

    # ─── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── Toolbar ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        open_btn = QPushButton("📂 Open")
        open_btn.clicked.connect(self._on_open)
        toolbar.addWidget(open_btn)

        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self._on_save)
        toolbar.addWidget(save_btn)

        profiles_btn = QPushButton("📋 Profiles")
        profiles_btn.clicked.connect(self._show_profiles)
        toolbar.addWidget(profiles_btn)

        batch_btn = QPushButton("📁 Batch")
        batch_btn.clicked.connect(self._show_batch)
        toolbar.addWidget(batch_btn)

        toolbar.addSpacing(8)
        lbl = QLabel("3rd:")
        lbl.setObjectName("value-label")
        toolbar.addWidget(lbl)
        self.third_profile_combo = QComboBox()
        self.third_profile_combo.setMinimumWidth(140)
        self._refresh_profile_combo(self.third_profile_combo)
        self.third_profile_combo.currentTextChanged.connect(self._on_third_profile_changed)
        toolbar.addWidget(self.third_profile_combo)

        toolbar.addStretch()

        # Status indicator (replaces the bottom status bar)
        self.status_label = QLabel(f"⚙ {DEVICE}")
        self.status_label.setObjectName("value-label")
        toolbar.addWidget(self.status_label)

        reset_btn = QPushButton("↺ Reset")
        reset_btn.clicked.connect(self._on_reset)
        toolbar.addWidget(reset_btn)
        root.addLayout(toolbar)

        # ── Accent separator between toolbar and content ──
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #3a3a3a; border: none;")
        root.addWidget(separator)
        root.addSpacing(4)

        # ── Adjustments row (fixed height) ──
        self.adjustments = AdjustmentsPanel()
        self.adjustments.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        root.addWidget(self.adjustments)

        # ── Splitter: previews (top) | plots (bottom) — both resizable ──
        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setHandleWidth(8)

        # Previews — 2 or 3 viewers depending on 3rd profile selection
        self.previews_widget = QWidget()
        self.previews_layout = QHBoxLayout(self.previews_widget)
        self.previews_layout.setContentsMargins(0, 0, 0, 0)
        self.previews_layout.setSpacing(3)
        self.viewer_original = ImageViewer("Original")
        self.viewer_live = ImageViewer("Sliders")
        self.viewer_profile = ImageViewer("Profile")
        self.previews_layout.addWidget(self.viewer_original, 1)
        self.previews_layout.addWidget(self.viewer_live, 1)
        # viewer_profile added/removed dynamically via _update_preview_count()
        self.viewer_profile.setVisible(False)
        self.main_splitter.addWidget(self.previews_widget)

        # Plots
        self.plots_panel = PlotsPanel()
        self.main_splitter.addWidget(self.plots_panel)

        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 4)
        self.main_splitter.setSizes([300, 400])
        root.addWidget(self.main_splitter, 1)

    # ─── Signal wiring ────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.adjustments.paramsChanged.connect(self._schedule_preview)

    def _reset_status(self) -> None:
        """Revert the status label to the device indicator."""
        self.status_label.setText(f"⚙ {DEVICE}")

    def _set_status(self, text: str, transient: bool = True) -> None:
        """Show a status message; revert to device after 5s if transient."""
        self.status_label.setText(text)
        if transient:
            self._status_timer.start(5000)
        else:
            self._status_timer.stop()

    def _on_third_profile_changed(self, *_args) -> None:
        """Show/hide the 3rd preview and reprocess."""
        has_third = self.third_profile_combo.currentText() != "None"
        self._set_profile_viewer_visible(has_third)
        self._schedule_preview()

    def _set_profile_viewer_visible(self, visible: bool) -> None:
        """Add or remove the 3rd viewer from the previews layout."""
        if visible and self.viewer_profile.parent() is not self.previews_widget:
            self.previews_layout.addWidget(self.viewer_profile, 1)
            self.viewer_profile.setVisible(True)
        elif not visible:
            self.previews_layout.removeWidget(self.viewer_profile)
            self.viewer_profile.setParent(None)
            self.viewer_profile.setVisible(False)
            self.viewer_profile.set_array(None)
            self.viewer_profile.set_title("Profile")

    # ─── Popup dialogs ────────────────────────────────────────────────────────

    def _show_profiles(self) -> None:
        if self._profiles_dialog is None:
            self._profiles_dialog = ProfilesDialog(self)
            self._profiles_dialog.applyProfile.connect(self._on_apply_profile)
            self._profiles_dialog.saveProfile.connect(self._on_save_profile)
            self._profiles_dialog.profilesChanged.connect(self._on_profiles_changed)
        self._profiles_dialog.refresh()
        self._profiles_dialog.show()
        self._profiles_dialog.raise_()

    def _show_batch(self) -> None:
        if self._batch_dialog is None:
            self._batch_dialog = BatchDialog(self)
            self._batch_dialog.runBatch.connect(self._on_run_batch)
        self._batch_dialog.show()
        self._batch_dialog.raise_()

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
        self._refresh_profile_combo(self.third_profile_combo)

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _on_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open image", "",
            "Images (*.jpg *.jpeg *.png *.tif *.tiff *.webp *.bmp)",
        )
        if path:
            self._image_path = path
            self._set_status(f"📂 {Path(path).name}")
            self._run_preview()

    def _on_reset(self) -> None:
        self.adjustments.reset()

    def _on_save(self) -> None:
        """Save the live-processed image with a format/quality dialog."""
        if not self._image_path or self._live_arr is None:
            self._set_status("Nothing to save — open an image first.")
            return

        # Format selection dialog
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QSpinBox
        fmt_dialog = QDialog(self)
        fmt_dialog.setWindowTitle("💾 Save options")
        fmt_dialog.setMinimumWidth(280)
        form = QFormLayout(fmt_dialog)
        from qt_app.widgets.dialogs import _apply_dialog_font
        _apply_dialog_font(fmt_dialog)

        from PySide6.QtWidgets import QComboBox
        fmt_combo = QComboBox()
        fmt_combo.addItems(["JPEG", "WebP", "TIFF", "PNG"])
        form.addRow("Format:", fmt_combo)
        quality_spin = QSpinBox()
        quality_spin.setRange(1, 100)
        quality_spin.setValue(90)
        form.addRow("Quality:", quality_spin)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(fmt_dialog.accept)
        buttons.rejected.connect(fmt_dialog.reject)
        form.addRow(buttons)
        if fmt_dialog.exec() != QDialog.Accepted:
            return

        fmt = fmt_combo.currentText()
        quality = quality_spin.value()
        ext = {"JPEG": "jpg", "WebP": "webp", "TIFF": "tiff", "PNG": "png"}[fmt]

        # File save dialog
        default_name = Path(self._image_path).stem + "_edited." + ext
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save image", default_name,
            f"{fmt} (*.{ext})",
        )
        if not save_path:
            return

        # Process at full resolution and save
        from PIL import Image
        from pipeline.gpu_ops import gpu_process_from_pil
        img = Image.open(self._image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        params = params_from_values(self.adjustments.get_params())
        result = gpu_process_from_pil(img, params)

        save_kwargs = {}
        if fmt in ("JPEG", "WebP"):
            save_kwargs["quality"] = quality
        if fmt == "JPEG":
            save_kwargs["subsampling"] = 0
        result.save(save_path, format=fmt, **save_kwargs)
        self._set_status(f"💾 {Path(save_path).name} ({fmt} q{quality})")

    def _on_apply_profile(self, name: str) -> None:
        params = load_profile_params(name)
        if params is not None:
            self.adjustments.set_params(params)
            self._schedule_preview()

    def _on_save_profile(self, name: str) -> None:
        params = params_from_values(self.adjustments.get_params())
        path = save_profile(name, params)
        self._set_status(f"📋 {Path(path).name}")
        self._on_profiles_changed()
        if self._profiles_dialog:
            self._profiles_dialog.refresh()

    def _on_run_batch(self, input_dir: str, output_dir: str, use_gpu: bool) -> None:
        if not input_dir or not output_dir:
            if self._batch_dialog:
                self._batch_dialog.set_status("Enter both directories.")
            return
        if not Path(input_dir).is_dir():
            if self._batch_dialog:
                self._batch_dialog.set_status("Input directory not found.")
            return
        params = params_from_values(self.adjustments.get_params())
        if self._batch_dialog:
            self._batch_dialog.set_status("Processing…")
        self._batch_worker = BatchWorker(input_dir, output_dir, params, use_gpu)
        self._batch_worker.finished_batch.connect(self._on_batch_done)
        self._batch_worker.failed.connect(self._on_batch_failed)
        self._batch_worker.start()

    def _on_batch_done(self, success: int, failed: int, output_dir: str) -> None:
        msg = f"✅ {success} ok, ❌ {failed} failed → {output_dir}"
        if self._batch_dialog:
            self._batch_dialog.set_status(msg)
        self._set_status(f"✅ {success} ok, ❌ {failed} failed")

    def _on_batch_failed(self, msg: str) -> None:
        if self._batch_dialog:
            self._batch_dialog.set_status(f"Error: {msg}")

    # ─── Preview pipeline ─────────────────────────────────────────────────────

    def _schedule_preview(self, *_args) -> None:
        self._debounce.start(120)

    def _run_preview(self) -> None:
        if not self._image_path:
            return
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
        params = params_from_values(self.adjustments.get_params())
        prof_name = self.third_profile_combo.currentText()
        if prof_name == "None":
            prof_name = None
        self.plots_panel.update_all(orig, live, profile, prof_name, params)

    def _on_preview_failed(self, msg: str) -> None:
        self._set_status(f"⚠ Preview error: {msg}")


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