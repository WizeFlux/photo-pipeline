"""Tests for PlotsWorker — parallel plot data preparation."""

import numpy as np
import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from qt_app.state import PARAM_DEFAULTS, params_from_values
from qt_app.workers import PlotsWorker


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_plots_worker_emits_bundle(app):
    """PlotsWorker should emit a dict bundle with all expected keys."""
    from PySide6.QtCore import QEventLoop, QTimer
    orig = (np.random.rand(50, 80, 3) * 255).astype(np.uint8)
    live = (np.random.rand(50, 80, 3) * 255).astype(np.uint8)
    profile = (np.random.rand(50, 80, 3) * 255).astype(np.uint8)
    params = params_from_values(PARAM_DEFAULTS)

    worker = PlotsWorker(orig, live, profile, "Cine", params, params)
    received = []
    loop = QEventLoop()
    worker.plots_ready.connect(lambda b: (received.append(b), loop.quit()))
    worker.start()
    QTimer.singleShot(3000, loop.quit)  # safety net
    loop.exec()
    worker.wait(2000)
    assert len(received) == 1
    bundle = received[0]
    assert set(bundle.keys()) == {
        "orig", "live", "profile", "profile_name",
        "params", "third_params",
    }
    np.testing.assert_array_equal(bundle["orig"], orig)
    np.testing.assert_array_equal(bundle["live"], live)
    np.testing.assert_array_equal(bundle["profile"], profile)
    assert bundle["profile_name"] == "Cine"


def test_plots_worker_without_profile(app):
    """PlotsWorker should handle None profile."""
    from PySide6.QtCore import QEventLoop
    orig = (np.random.rand(50, 80, 3) * 255).astype(np.uint8)
    live = (np.random.rand(50, 80, 3) * 255).astype(np.uint8)
    params = params_from_values(PARAM_DEFAULTS)

    worker = PlotsWorker(orig, live, None, None, params, None)
    received = []
    loop = QEventLoop()
    worker.plots_ready.connect(lambda b: (received.append(b), loop.quit()))
    worker.start()
    # If the worker finishes very fast, the signal may have already been
    # emitted before we enter the loop — use a timer as a safety net.
    from PySide6.QtCore import QTimer
    QTimer.singleShot(3000, loop.quit)
    loop.exec()
    worker.wait(2000)
    assert len(received) == 1
    assert received[0]["profile"] is None
    assert received[0]["profile_name"] is None


def test_plots_worker_interruption(app):
    """Requesting interruption before run should prevent emission."""
    orig = (np.random.rand(50, 80, 3) * 255).astype(np.uint8)
    live = (np.random.rand(50, 80, 3) * 255).astype(np.uint8)
    params = params_from_values(PARAM_DEFAULTS)

    worker = PlotsWorker(orig, live, None, None, params, None)
    worker.requestInterruption()
    received = []
    worker.plots_ready.connect(lambda b: received.append(b))
    worker.start()
    worker.wait(2000)
    # Interruption was requested — no bundle should be emitted
    assert len(received) == 0