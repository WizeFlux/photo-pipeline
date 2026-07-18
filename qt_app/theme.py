"""Dark theme stylesheet for the application."""

DARK_QSS = """
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-size: 13px;
    font-family: -apple-system, "Helvetica Neue", "Segoe UI", "Roboto", sans-serif;
}

QMainWindow, QDialog {
    background-color: #1e1e1e;
}

/* ─── Group boxes ─────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #3a3a3a;
    border-radius: 6px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: 600;
    color: #b0b0b0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #00d4aa;
}

/* ─── Sliders ─────────────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 4px;
    background: #3a3a3a;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00d4aa;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #00f0c0;
}
QSlider::sub-page:horizontal {
    background: #00705a;
    border-radius: 2px;
}

/* ─── Buttons ─────────────────────────────────────────────────── */
QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 6px 16px;
    color: #e0e0e0;
}
QPushButton:hover {
    background-color: #383838;
    border-color: #00d4aa;
}
QPushButton:pressed {
    background-color: #00d4aa;
    color: #1e1e1e;
}
QPushButton#primary {
    background-color: #00d4aa;
    color: #1e1e1e;
    font-weight: 600;
    border: none;
}
QPushButton#primary:hover {
    background-color: #00f0c0;
}

/* ─── Inputs ──────────────────────────────────────────────────── */
QLineEdit, QSpinBox, QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 5px 8px;
    color: #e0e0e0;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #00d4aa;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    selection-background-color: #00d4aa;
    selection-color: #1e1e1e;
}

/* ─── Scroll bars (kept subtle — shown only when a widget truly overflows) ── */
QScrollBar:vertical {
    background: #1e1e1e;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3a3a3a;
    min-height: 30px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #505050;
}
QScrollBar::add-line, QScrollBar::sub-line {
    height: 0;
}
QScrollBar:horizontal {
    background: #1e1e1e;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #3a3a3a;
    min-width: 30px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: #505050;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ─── Status bar ──────────────────────────────────────────────── */
QStatusBar {
    background-color: #181818;
    color: #888;
    border-top: 1px solid #2a2a2a;
}

/* ─── Labels ──────────────────────────────────────────────────── */
QLabel#section-title {
    color: #00d4aa;
    font-size: 14px;
    font-weight: 600;
    padding: 4px 0;
}
QLabel#value-label {
    color: #888;
    font-size: 11px;
}
"""


def apply_theme(app) -> None:
    """Apply the dark stylesheet to a QApplication."""
    app.setStyleSheet(DARK_QSS)