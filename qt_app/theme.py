"""Dark theme stylesheet for the application."""

DARK_QSS = """
QWidget {
    background-color: #1e1e1e;
    color: #e0e0e0;
    font-size: 10px;
    font-family: -apple-system, "Helvetica Neue", "Segoe UI", "Roboto", sans-serif;
}

QMainWindow, QDialog {
    background-color: #1e1e1e;
}

/* ─── Group boxes ─────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    margin-top: 11px;
    padding: 10px 6px 6px 6px;
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

/* ─── Sliders ─────────────────────────────────────────────────── */
QSlider::groove:horizontal {
    height: 3px;
    background: #3a3a3a;
    border-radius: 1px;
}
QSlider::handle:horizontal {
    background: #00d4aa;
    width: 10px;
    height: 10px;
    margin: -4px 0;
    border-radius: 5px;
}
QSlider::handle:horizontal:hover {
    background: #00f0c0;
}
QSlider::sub-page:horizontal {
    background: #00705a;
    border-radius: 1px;
}

/* ─── Buttons ─────────────────────────────────────────────────── */
QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 3px 10px;
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
    border-radius: 3px;
    padding: 2px 6px;
    color: #e0e0e0;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #00d4aa;
}
QComboBox::drop-down {
    border: none;
    width: 18px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    selection-background-color: #00d4aa;
    selection-color: #1e1e1e;
}

/* ─── Splitter handles (visible, grabbable) ───────────────────── */
QSplitter::handle:horizontal {
    background: #2a2a2a;
    width: 6px;
    margin: 2px 1px;
    border-radius: 2px;
}
QSplitter::handle:horizontal:hover {
    background: #00d4aa;
}
QSplitter::handle:vertical {
    background: #2a2a2a;
    height: 8px;
    margin: 1px 2px;
    border-radius: 2px;
}
QSplitter::handle:vertical:hover {
    background: #00d4aa;
}
/* Grip dots on vertical handles for discoverability */
QSplitter::handle:vertical {
    image: none;
}
QSplitter::handle:vertical:pressed {
    background: #00f0c0;
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
    font-size: 11px;
    font-weight: 600;
    padding: 2px 0;
}
QLabel#value-label {
    color: #888;
    font-size: 10px;
}
"""


def apply_theme(app) -> None:
    """Apply the dark stylesheet to a QApplication."""
    app.setStyleSheet(DARK_QSS)