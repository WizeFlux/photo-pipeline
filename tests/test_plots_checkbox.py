"""Tests for the toolbar Plots checkbox (moved from Settings dialog)."""

import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from qt_app.main_window import MainWindow
from qt_app.theme import apply_theme


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    apply_theme(a)
    return a


def test_plots_checkbox_exists(app):
    """MainWindow should have a plots_checkbox in the toolbar."""
    w = MainWindow()
    assert hasattr(w, "plots_checkbox")
    assert w.plots_checkbox.isChecked() is True  # default on


def test_plots_toggled_hides_panel(app):
    """Unchecking the checkbox should hide the plots panel."""
    w = MainWindow()
    w.show()
    app.processEvents()
    w.plots_checkbox.setChecked(False)
    app.processEvents()
    assert w._plots_enabled is False
    assert w.plots_panel.isVisible() is False


def test_plots_toggled_shows_panel(app):
    """Re-checking the checkbox should show the plots panel."""
    w = MainWindow()
    w.show()
    app.processEvents()
    w.plots_checkbox.setChecked(False)
    app.processEvents()
    w.plots_checkbox.setChecked(True)
    app.processEvents()
    assert w._plots_enabled is True
    assert w.plots_panel.isVisible() is True


def test_settings_dialog_no_plots_checkbox(app):
    """SettingsDialog should no longer have a plots_checkbox."""
    from qt_app.widgets.dialogs import SettingsDialog
    dlg = SettingsDialog()
    assert not hasattr(dlg, "plots_checkbox")


def test_settings_dialog_stores_plots_enabled(app):
    """SettingsDialog should still pass through plots_enabled via set_settings."""
    from qt_app.widgets.dialogs import SettingsDialog
    dlg = SettingsDialog()
    dlg.set_settings("JPEG", 90, 85, 1200, False)
    assert dlg._plots_enabled is False
    settings = dlg.get_settings()
    assert settings[4] is False  # plots_enabled is 5th element


def test_settings_changed_syncs_checkbox(app):
    """When settings dialog emits plots_enabled, the toolbar checkbox should sync."""
    w = MainWindow()
    w._plots_enabled = True
    w.plots_checkbox.setChecked(True)
    # Simulate settings dialog emitting with plots_enabled=False
    w._on_settings_changed("JPEG", 90, 85, 1200, False)
    assert w.plots_checkbox.isChecked() is False
    assert w._plots_enabled is False