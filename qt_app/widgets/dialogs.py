"""Popup dialogs for Profiles, Batch, and Format — launched from the toolbar.

These dialogs use a normal (non-reduced) font size, overriding the app's
global 10px compact stylesheet.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QVBoxLayout,
    QWidget,
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


class FormatDialog(QDialog):
    """Popup for choosing output format and quality."""

    formatChanged = Signal(str, int)  # format, quality

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎨 Format")
        self.setModal(False)
        self.setMinimumWidth(260)
        _apply_dialog_font(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        form = QFormLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPEG", "WebP", "TIFF", "PNG"])
        self.format_combo.setCurrentText("JPEG")
        form.addRow("Format:", self.format_combo)
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(90)
        form.addRow("Quality:", self.quality_spin)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self._on_accept)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        self.formatChanged.emit(self.format_combo.currentText(),
                                self.quality_spin.value())
        self.accept()

    def get_format(self) -> tuple[str, int]:
        return self.format_combo.currentText(), self.quality_spin.value()

    def set_format(self, fmt: str, quality: int) -> None:
        idx = self.format_combo.findText(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        self.quality_spin.setValue(quality)


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