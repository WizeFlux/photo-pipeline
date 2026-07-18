"""Batch processing panel — directory inputs + run button.

Signals:
    runBatch(str, str, bool): emitted with (input_dir, output_dir, use_gpu).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)


class BatchPanel(QWidget):
    """Input/output directory pickers + GPU toggle + process button."""

    runBatch = Signal(str, str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        group = QGroupBox("📁 Batch Process")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(group)
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # Input dir
        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("Input"))
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("/path/to/images")
        in_row.addWidget(self.input_edit, 1)
        in_btn = QPushButton("Browse")
        in_btn.clicked.connect(lambda: self._browse(self.input_edit))
        in_row.addWidget(in_btn)
        layout.addLayout(in_row)

        # Output dir
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("/path/to/output")
        out_row.addWidget(self.output_edit, 1)
        out_btn = QPushButton("Browse")
        out_btn.clicked.connect(lambda: self._browse(self.output_edit, is_dir=True))
        out_row.addWidget(out_btn)
        layout.addLayout(out_row)

        # GPU + button
        bottom = QHBoxLayout()
        self.gpu_check = QCheckBox("Use GPU")
        self.gpu_check.setChecked(True)
        bottom.addWidget(self.gpu_check)
        bottom.addStretch()
        run_btn = QPushButton("Process All")
        run_btn.setObjectName("primary")
        run_btn.clicked.connect(self._on_run)
        bottom.addWidget(run_btn)
        layout.addLayout(bottom)

        # Status line
        self.status_label = QLabel("")
        self.status_label.setObjectName("value-label")
        layout.addWidget(self.status_label)

    def _browse(self, edit: QLineEdit, is_dir: bool = True) -> None:
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