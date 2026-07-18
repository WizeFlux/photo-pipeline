"""Batch processing — compact 2-row panel (dirs | GPU + run + status)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)


class BatchPanel(QWidget):
    """Directory inputs + GPU toggle + process button."""

    runBatch = Signal(str, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        group = QGroupBox("📁 Batch")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(6, 10, 6, 6)
        layout.setSpacing(4)

        # Input row
        in_row = QHBoxLayout()
        in_row.setSpacing(4)
        in_row.addWidget(QLabel("In"))
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("/path/to/images")
        in_row.addWidget(self.input_edit, 1)
        in_btn = QPushButton("…")
        in_btn.setMaximumWidth(28)
        in_btn.clicked.connect(lambda: self._browse(self.input_edit))
        in_row.addWidget(in_btn)
        layout.addLayout(in_row)

        # Output row
        out_row = QHBoxLayout()
        out_row.setSpacing(4)
        out_row.addWidget(QLabel("Out"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("/path/to/output")
        out_row.addWidget(self.output_edit, 1)
        out_btn = QPushButton("…")
        out_btn.setMaximumWidth(28)
        out_btn.clicked.connect(lambda: self._browse(self.output_edit))
        out_row.addWidget(out_btn)
        layout.addLayout(out_row)

        # GPU + run
        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        self.gpu_check = QCheckBox("GPU")
        self.gpu_check.setChecked(True)
        bottom.addWidget(self.gpu_check)
        bottom.addStretch()
        run_btn = QPushButton("Process All")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self._on_run)
        bottom.addWidget(run_btn)
        layout.addLayout(bottom)

        self.status_label = QLabel("")
        self.status_label.setObjectName("value-label")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _browse(self, edit: QLineEdit) -> None:
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "Select directory")
        if path:
            edit.setText(path)

    def _on_run(self) -> None:
        self.runBatch.emit(
            self.input_edit.text().strip(),
            self.output_edit.text().strip(),
            self.gpu_check.isChecked(),
        )

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)