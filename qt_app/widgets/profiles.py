"""Profile management — compact 3-row panel (Apply | Save | Delete)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from qt_app.state import delete_profile, list_profiles


class ProfilesPanel(QWidget):
    """3 rows: Apply / Save / Delete."""

    applyProfile = Signal(str)
    saveProfile = Signal(str)
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
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(4)

        # Apply
        apply_row = QHBoxLayout()
        apply_row.setSpacing(4)
        apply_row.addWidget(QLabel("Apply"))
        self.apply_combo = QComboBox()
        apply_row.addWidget(self.apply_combo, 1)
        apply_btn = QPushButton("⬆️")
        apply_btn.setMaximumWidth(32)
        apply_btn.clicked.connect(self._on_apply)
        apply_row.addWidget(apply_btn)
        layout.addLayout(apply_row)

        # Save
        save_row = QHBoxLayout()
        save_row.setSpacing(4)
        save_row.addWidget(QLabel("Save"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("name")
        save_row.addWidget(self.name_input, 1)
        save_btn = QPushButton("💾")
        save_btn.setMaximumWidth(32)
        save_btn.clicked.connect(self._on_save)
        save_row.addWidget(save_btn)
        layout.addLayout(save_row)

        # Delete
        del_row = QHBoxLayout()
        del_row.setSpacing(4)
        del_row.addWidget(QLabel("Delete"))
        self.delete_combo = QComboBox()
        del_row.addWidget(self.delete_combo, 1)
        del_btn = QPushButton("🗑️")
        del_btn.setMaximumWidth(32)
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
        if QMessageBox.question(self, "Delete", f"Delete '{name}'?") != QMessageBox.Yes:
            return
        if delete_profile(name):
            self.profilesChanged.emit()

    def refresh(self) -> None:
        profiles = list_profiles()
        cur_a = self.apply_combo.currentText()
        cur_d = self.delete_combo.currentText()
        self.apply_combo.blockSignals(True)
        self.delete_combo.blockSignals(True)
        self.apply_combo.clear()
        self.delete_combo.clear()
        self.apply_combo.addItems(profiles)
        self.delete_combo.addItems(profiles)
        if cur_a and self.apply_combo.findText(cur_a) >= 0:
            self.apply_combo.setCurrentText(cur_a)
        if cur_d and self.delete_combo.findText(cur_d) >= 0:
            self.delete_combo.setCurrentText(cur_d)
        self.apply_combo.blockSignals(False)
        self.delete_combo.blockSignals(False)