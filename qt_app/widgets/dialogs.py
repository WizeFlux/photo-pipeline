"""Popup dialogs for Profiles, Batch, and Format — launched from the toolbar.

These dialogs use a normal (non-reduced) font size, overriding the app's
global 10px compact stylesheet.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QSpinBox, QVBoxLayout, QWidget,
)

from qt_app.widgets.batch import BatchPanel
from qt_app.widgets.profiles import ProfilesPanel

# Normal font size for popup dialogs (overrides the global compact 10px).
_DIALOG_QSS = """
QDialog, QDialog QWidget {
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    margin-top: 14px;
    padding: 12px 8px 8px 8px;
    font-weight: 600;
    color: #b0b0b0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    padding: 0 4px;
    color: #00d4aa;
}
QLabel, QLineEdit, QComboBox, QPushButton {
    font-size: 13px;
}
"""


def _apply_dialog_font(dialog: QDialog) -> None:
    """Apply normal-size font + relaxed layout QSS to a popup dialog."""
    dialog.setStyleSheet(_DIALOG_QSS)
    font = QFont()
    font.setPointSize(10)  # ~13px on most platforms
    dialog.setFont(font)


class ProfilesDialog(QDialog):
    """Modal-ish popup wrapping the ProfilesPanel."""

    applyProfile = Signal(str)
    saveProfile = Signal(str)
    profilesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Profiles")
        self.setModal(False)
        self.setMinimumWidth(380)
        _apply_dialog_font(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.panel = ProfilesPanel()
        layout.addWidget(self.panel)

        self.panel.applyProfile.connect(self.applyProfile)
        self.panel.saveProfile.connect(self.saveProfile)
        self.panel.profilesChanged.connect(self.profileChanged)

    def profileChanged(self) -> None:
        self.panel.refresh()
        self.profilesChanged.emit()

    def refresh(self) -> None:
        self.panel.refresh()


class SettingsDialog(QDialog):
    """Popup for output format, quality, cache quality, preview size, and plot toggle."""

    settingsChanged = Signal(str, int, int, int, bool)  # format, quality, cache_quality, preview_w, plots_enabled

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙ Settings")
        self.setModal(False)
        self.setMinimumWidth(320)
        self._plots_enabled = True  # synced by set_settings; toggle is in toolbar
        _apply_dialog_font(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ── Output section ──
        out_group = QGroupBox("Output")
        out_form = QFormLayout(out_group)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG", "WebP", "TIFF", "PNG"])
        self.format_combo.setCurrentText("JPEG")
        out_form.addRow("Format:", self.format_combo)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(90)
        out_form.addRow("Quality:", self.quality_spin)
        layout.addWidget(out_group)

        # ── Preview section ──
        preview_group = QGroupBox("Preview")
        preview_form = QFormLayout(preview_group)
        self.preview_w_spin = QSpinBox()
        self.preview_w_spin.setRange(400, 2400)
        self.preview_w_spin.setSingleStep(100)
        self.preview_w_spin.setValue(1200)
        self.preview_w_spin.setSuffix(" px")
        preview_form.addRow("Max width:", self.preview_w_spin)
        self.cache_quality_spin = QSpinBox()
        self.cache_quality_spin.setRange(50, 100)
        self.cache_quality_spin.setValue(95)
        self.cache_quality_spin.setSuffix(" %")
        preview_form.addRow("Cache quality:", self.cache_quality_spin)
        layout.addWidget(preview_group)

        # Plots toggle moved to the main toolbar (next to Preview profile).
        # Performance section removed — was only the plots checkbox.

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self._on_accept)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        self.settingsChanged.emit(
            self.format_combo.currentText(),
            self.quality_spin.value(),
            self.cache_quality_spin.value(),
            self.preview_w_spin.value(),
            self._plots_enabled,  # kept in sync by set_settings
        )
        self.accept()

    def get_settings(self) -> tuple[str, int, int, int, bool]:
        return (self.format_combo.currentText(),
                self.quality_spin.value(),
                self.cache_quality_spin.value(),
                self.preview_w_spin.value(),
                self._plots_enabled)

    def set_settings(self, fmt: str, quality: int, cache_quality: int,
                     preview_w: int, plots_enabled: bool) -> None:
        self._plots_enabled = plots_enabled
        idx = self.format_combo.findText(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        self.quality_spin.setValue(quality)
        self.cache_quality_spin.setValue(cache_quality)
        self.preview_w_spin.setValue(preview_w)


class BatchDialog(QDialog):
    """Popup wrapping the BatchPanel."""

    runBatch = Signal(str, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📁 Batch Process")
        self.setModal(False)
        self.setMinimumWidth(460)
        _apply_dialog_font(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.panel = BatchPanel()
        layout.addWidget(self.panel)
        self.panel.runBatch.connect(self.runBatch)

    def set_status(self, text: str) -> None:
        self.panel.set_status(text)