"""Popup dialogs for Profiles and Batch — launched from the toolbar."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QWidget,
)

from qt_app.widgets.batch import BatchPanel
from qt_app.widgets.profiles import ProfilesPanel


class ProfilesDialog(QDialog):
    """Modal-ish popup wrapping the ProfilesPanel."""

    applyProfile = Signal(str)
    saveProfile = Signal(str)
    profilesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Profiles")
        self.setModal(False)
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
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


class BatchDialog(QDialog):
    """Popup wrapping the BatchPanel."""

    runBatch = Signal(str, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📁 Batch Process")
        self.setModal(False)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.panel = BatchPanel()
        layout.addWidget(self.panel)
        self.panel.runBatch.connect(self.runBatch)

    def set_status(self, text: str) -> None:
        self.panel.set_status(text)