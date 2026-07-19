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

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSpinBox, QSplitter, QVBoxLayout,
    QWidget,
)

from pipeline.gpu_ops import DEVICE
from qt_app.state import (
    load_profile_params, params_from_values, save_profile,
)
from qt_app.theme import apply_theme
from qt_app.widgets.adjustments import AdjustmentsPanel
from qt_app.widgets.dialogs import BatchDialog, ProfilesDialog, SettingsDialog
from qt_app.widgets.image_viewer import ImageViewer
from qt_app.widgets.plots_panel import PlotsPanel
from qt_app.workers import BatchWorker, PlotsWorker, PreviewWorker


# Throttle interval: while dragging a slider, the preview is regenerated at
# most once per this many milliseconds. A final render always fires after the
# user stops moving. Kept low (250ms) for responsive feel.
_THROTTLE_MS = 250


def _terminate_worker(worker, signal) -> None:
    """Terminate a QThread-based worker: disconnect signal + terminate thread.

    Shared by _run_preview (PreviewWorker) and _start_plots_worker (PlotsWorker).
    Does NOT wait — the old thread dies in the background, freeing CPU for the
    new worker. The signal is disconnected so stale results can't update the UI.
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            signal.disconnect()
        except (RuntimeError, TypeError):
            pass
    if worker.isRunning():
        worker.terminate()


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
        self._plots_worker: PlotsWorker | None = None
        self._batch_worker: BatchWorker | None = None
        # Throttle: render immediately on first change, then at most once per
        # _THROTTLE_MS. A trailing render guarantees the final state is shown.
        self._throttle = QTimer(self)
        self._throttle.setSingleShot(True)
        self._throttle.timeout.connect(self._run_preview)
        self._last_render_ts: float = 0.0
        self._pending_final: bool = False
        # Status reset timer — transient messages revert to the device label
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._reset_status)

        # Popup dialogs (created lazily)
        self._profiles_dialog: ProfilesDialog | None = None
        self._batch_dialog: BatchDialog | None = None
        self._settings_dialog: SettingsDialog | None = None
        # Output settings (shared by Save and Batch)
        self._format: str = "JPEG"
        self._quality: int = 90
        # Preview cache quality (used by workers)
        self._cache_quality: int = 95
        # Preview max width (used by workers)
        self._preview_w: int = 1200
        # Plots enabled toggle
        self._plots_enabled: bool = True

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

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.clicked.connect(self._show_settings)
        toolbar.addWidget(settings_btn)

        profiles_btn = QPushButton("📋 Profiles")
        profiles_btn.clicked.connect(self._show_profiles)
        toolbar.addWidget(profiles_btn)

        batch_btn = QPushButton("📁 Batch")
        batch_btn.clicked.connect(self._show_batch)
        toolbar.addWidget(batch_btn)

        toolbar.addSpacing(8)
        lbl = QLabel("Preview profile:")
        lbl.setObjectName("value-label")
        toolbar.addWidget(lbl)
        self.third_profile_combo = QComboBox()
        self.third_profile_combo.setMinimumWidth(140)
        self._refresh_profile_combo(self.third_profile_combo)
        self.third_profile_combo.currentTextChanged.connect(self._on_third_profile_changed)
        toolbar.addWidget(self.third_profile_combo)

        toolbar.addSpacing(12)
        self.plots_checkbox = QCheckBox("Plots")
        self.plots_checkbox.setChecked(True)
        self.plots_checkbox.setToolTip("Enable/disable analysis plots panel")
        self.plots_checkbox.toggled.connect(self._on_plots_toggled)
        toolbar.addWidget(self.plots_checkbox)

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
        # viewer_profile added/removed dynamically via _set_profile_viewer_visible()
        self.viewer_profile.setVisible(False)
        self.main_splitter.addWidget(self.previews_widget)

        # Synchronize zoom & pan across all viewers
        self._sync_viewers()

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
        self.adjustments.lutPickerRequested.connect(self._show_lut_picker)

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

    def _sync_viewers(self) -> None:
        """Connect zoom/pan signals so all viewers stay in sync.

        Called once during UI construction. No disconnect needed since
        this is the first (and only) time these signals are connected.
        """
        viewers = [self.viewer_original, self.viewer_live, self.viewer_profile]
        for src in viewers:
            for dst in viewers:
                if src is dst:
                    continue
                src.zoomChanged.connect(dst.set_zoom)
                src.panChanged.connect(dst.set_pan)

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

    def _show_settings(self) -> None:
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self)
            self._settings_dialog.settingsChanged.connect(self._on_settings_changed)
        self._settings_dialog.set_settings(
            self._format, self._quality, self._cache_quality,
            self._preview_w, self._plots_enabled
        )
        self._settings_dialog.show()
        self._settings_dialog.raise_()

    def _on_settings_changed(self, fmt: str, quality: int, cache_quality: int,
                             preview_w: int, plots_enabled: bool) -> None:
        self._format = fmt
        self._quality = quality
        # Cache quality changed → clear old cache so new quality takes effect
        if cache_quality != self._cache_quality:
            self._cache_quality = cache_quality
            self._clear_preview_cache()
            from qt_app.workers import set_preview_quality
            set_preview_quality(cache_quality)
        # Preview width changed → clear cache (old entries are wrong size)
        if preview_w != self._preview_w:
            self._preview_w = preview_w
            self._clear_preview_cache()
            from qt_app.workers import set_preview_max_w
            set_preview_max_w(preview_w)
        # Plots toggle — sync the toolbar checkbox (source of truth is now there)
        if plots_enabled != self._plots_enabled:
            self.plots_checkbox.setChecked(plots_enabled)  # triggers _on_plots_toggled
        self._set_status(f"⚙ {fmt} q{quality} | preview {preview_w}px | cache {cache_quality}%")

    def _on_plots_toggled(self, plots_enabled: bool) -> None:
        """Show/hide the plots panel. Triggered by the toolbar checkbox."""
        plots_toggled = plots_enabled != self._plots_enabled
        self._plots_enabled = plots_enabled
        self.plots_panel.setVisible(plots_enabled)
        if plots_toggled and plots_enabled and self._live_arr is not None:
            prof_name = self.third_profile_combo.currentText()
            if prof_name == "None":
                prof_name = None
            params = params_from_values(self.adjustments.get_params())
            self.plots_panel.update_all(
                self._orig_arr, self._live_arr, self._profile_arr, prof_name, params
            )

    def _show_lut_picker(self) -> None:
        """Open the LUT picker dialog with preview thumbnails."""
        if not self._image_path:
            self._set_status("Open an image first to pick a LUT.")
            return
        from qt_app.widgets.lut_picker import LutPickerDialog
        from qt_app.workers import _load_preview_image
        # Build base params WITHOUT LUT path — each thumbnail adds its own.
        # Keep lut_intensity so the picker reflects the current intensity.
        params = params_from_values(self.adjustments.get_params())
        current_intensity = params.get("lut_intensity", 1.0)
        params["lut_path"] = None
        try:
            img = _load_preview_image(self._image_path)
        except Exception as exc:
            self._set_status(f"⚠ Cannot load image: {exc}")
            return
        dialog = LutPickerDialog(img, params, current_intensity, self)
        dialog.lutSelected.connect(self._on_lut_selected)
        dialog.exec()

    def _on_lut_selected(self, lut_path: str) -> None:
        """Called when user picks a LUT from the picker dialog."""
        self.adjustments.set_lut(lut_path)  # updates combo → triggers preview

    def _clear_preview_cache(self) -> None:
        """Clear the preview cache directory."""
        import shutil
        from pathlib import Path
        cache_dir = Path.home() / ".cache" / "photo-pipeline" / "previews"
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)

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
        """Save the live-processed image using the toolbar format/quality."""
        if not self._image_path or self._live_arr is None:
            self._set_status("Nothing to save — open an image first.")
            return

        fmt = self._format
        quality = self._quality
        ext = {"JPEG": "jpg", "WebP": "webp", "TIFF": "tiff", "PNG": "png"}[fmt]

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save image",
            Path(self._image_path).stem + "_edited." + ext,
            f"{fmt} (*.{ext})",
        )
        if not save_path:
            return

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
        # Inject toolbar format/quality so batch uses the same settings as Save
        params["output_format"] = self._format.lower()
        params["output_quality"] = self._quality
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
        """Throttle preview renders to ≤1 per _THROTTLE_MS during drag.

        - If enough time elapsed since the last render → render now.
        - Otherwise → schedule a trailing render after _THROTTLE_MS.
          The trailing timer is restarted on each new change, so continuous
          dragging produces a steady ~1-render/500ms cadence plus a final
          render when the user stops.
        """
        import time as _time
        now = _time.perf_counter()
        elapsed_ms = (now - self._last_render_ts) * 1000.0
        if elapsed_ms >= _THROTTLE_MS:
            # Enough time passed — render immediately and stamp the clock.
            self._throttle.stop()
            self._pending_final = False
            self._last_render_ts = now
            self._run_preview()
        else:
            # Too soon — schedule a trailing render. Restarting the timer
            # on every change keeps the cadence bounded while dragging.
            self._pending_final = True
            self._throttle.start(_THROTTLE_MS - int(elapsed_ms))

    def _run_preview(self) -> None:
        if not self._image_path:
            return
        # Stamp the throttle clock: a render is actually starting.
        self._last_render_ts = time.perf_counter()
        self._pending_final = False

        # Detach any in-flight preview worker — terminate it immediately
        # so it stops consuming CPU/torch threads. The old worker's signal
        # is disconnected so it can't update the UI even if it finishes.
        if self._preview_worker is not None:
            _terminate_worker(self._preview_worker, self._preview_worker.finished_preview)

        params = self.adjustments.get_params()
        third = self.third_profile_combo.currentText()
        self._preview_worker = PreviewWorker(
            self._image_path, params, third if third != "None" else None
        )
        self._preview_worker.finished_preview.connect(self._on_preview_ready)
        self._preview_worker.failed.connect(self._on_preview_failed)
        self._render_start = time.perf_counter()
        self._preview_worker.start()

    def _on_preview_ready(self, orig, live, profile) -> None:
        elapsed = time.perf_counter() - getattr(self, "_render_start", time.perf_counter())
        self._orig_arr = orig
        self._live_arr = live
        self._profile_arr = profile
        # Update viewers immediately — preview is ready, don't wait for plots
        self.viewer_original.set_array(orig)
        self.viewer_live.set_array(live)
        if profile is not None:
            self.viewer_profile.set_array(profile)
            prof_name = self.third_profile_combo.currentText()
            self.viewer_profile.set_title(prof_name)
        else:
            self.viewer_profile.set_array(None)
            self.viewer_profile.set_title("Profile")
        self._set_status(f"⏱ {elapsed:.2f}s")

        # Launch plots worker in parallel — don't block the UI thread.
        # Plots update as soon as they're computed, independently of preview.
        self._start_plots_worker(orig, live, profile)

    def _start_plots_worker(self, orig, live, profile) -> None:
        """Terminate any in-flight plots worker and start a new one. No waiting."""
        if self._plots_worker is not None:
            _terminate_worker(self._plots_worker, self._plots_worker.plots_ready)
        params = params_from_values(self.adjustments.get_params())
        prof_name = self.third_profile_combo.currentText()
        if prof_name == "None":
            prof_name = None
        third_params = None
        if prof_name:
            third_params = load_profile_params(prof_name)
        self._plots_worker = PlotsWorker(
            orig, live, profile, prof_name, params, third_params
        )
        self._plots_worker.plots_ready.connect(self._on_plots_ready)
        self._plots_worker.failed.connect(self._on_plots_failed)
        self._plots_worker.start()

    def _on_plots_ready(self, bundle: dict) -> None:
        """Plots data computed — now render onto canvases (fast, UI thread)."""
        self.plots_panel.update_all(
            bundle["orig"], bundle["live"], bundle["profile"],
            bundle["profile_name"], bundle["params"],
        )

    def _on_plots_failed(self, msg: str) -> None:
        self._set_status(f"⚠ Plots error: {msg}")

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