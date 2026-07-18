"""Profile management panel — load/save/delete YAML presets.

Signals:
    applyProfile(str):  user clicked Apply → main window pushes to sliders.
    profilesChanged():  a profile was saved or deleted → refresh dropdowns.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from qt_app.state import delete_profile, list_profiles


class ProfilesPanel(QWidget):
    """Three-row panel: Apply | Save | Delete."""

    applyProfile = Signal(str)
    saveProfile = Signal(str)   # user requested save → main window provides params
    profilesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        group = QGroupBox("📋 Profiles")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # ── Apply row ──
        apply_row = QHBoxLayout()
        apply_row.addWidget(QLabel("YAML → Sliders"))
        self.apply_combo = QComboBox()
        self.apply_combo.setMinimumWidth(160)
        apply_row.addWidget(self.apply_combo, 1)
        apply_btn = QPushButton("⬆️ Apply")
        apply_btn.clicked.connect(self._on_apply)
        apply_row.addWidget(apply_btn)
        layout.addLayout(apply_row)

        # ── Save row ──
        save_row = QHBoxLayout()
        save_row.addWidget(QLabel("Sliders → YAML"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("profile name")
        save_row.addWidget(self.name_input, 1)
        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self._on_save)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

        # ── Delete row ──
        del_row = QHBoxLayout()
        del_row.addWidget(QLabel("Delete"))
        self.delete_combo = QComboBox()
        self.delete_combo.setMinimumWidth(160)
        del_row.addWidget(self.delete_combo, 1)
        del_btn = QPushButton("🗑️ Delete")
        del_btn.clicked.connect(self._on_delete)
        del_row.addWidget(del_btn)
        layout.addLayout(del_row)

        self.refresh()

    def _on_apply(self) -> None:
        name = self.apply_combo.currentText()
        if name:
            self.applyProfile.emit(name)

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Save profile", "Enter a profile name.")
            return
        self.saveProfile.emit(name)

    def _on_delete(self) -> None:
        name = self.delete_combo.currentText()
        if not name:
            return
        confirm = QMessageBox.question(
            self, "Delete profile",
            f"Delete '{name}'?",
        )
        if confirm != QMessageBox.Yes:
            return
        if delete_profile(name):
            self.profilesChanged.emit()

    # Public API ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        profiles = list_profiles()
        # Preserve current selection where possible
        current_apply = self.apply_combo.currentText()
        current_delete = self.delete_combo.currentText()
        self.apply_combo.blockSignals(True)
        self.delete_combo.blockSignals(True)
        self.apply_combo.clear()
        self.delete_combo.clear()
        self.apply_combo.addItems(profiles)
        self.delete_combo.addItems(profiles)
        if current_apply and self.apply_combo.findText(current_apply) >= 0:
            self.apply_combo.setCurrentText(current_apply)
        if current_delete and self.delete_combo.findText(current_delete) >= 0:
            self.delete_combo.setCurrentText(current_delete)
        self.apply_combo.blockSignals(False)
        self.delete_combo.blockSignals(False)