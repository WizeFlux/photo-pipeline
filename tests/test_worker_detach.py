"""Tests for non-blocking worker detachment in MainWindow.

Verifies that old preview/plots workers are interrupted and detached
without blocking the UI thread via wait().
"""

import numpy as np
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


def test_throttle_interval_is_250ms():
    """Throttle should be 250ms (reduced from 500 for responsiveness)."""
    import qt_app.main_window as mw
    assert mw._THROTTLE_MS == 250


def test_torch_threads_limited():
    """torch CPU threads should be limited to ≤3 to avoid worker contention."""
    import torch
    from pipeline.gpu_ops import DEVICE
    if DEVICE.type == "cpu":
        assert torch.get_num_threads() <= 3


def test_run_preview_does_not_wait(app, monkeypatch):
    """_run_preview should not call wait() on the old worker."""
    w = MainWindow()
    w._image_path = "/tmp/fake.jpg"
    
    wait_called = []
    
    # Stub PreviewWorker with a real Signal-like object
    from PySide6.QtCore import QObject, Signal
    
    class StubWorker(QObject):
        finished_preview = Signal(object, object, object)
        failed = Signal(str)
        def __init__(self, *a, **k):
            super().__init__()
        def start(self):
            pass
        def requestInterruption(self):
            pass
        def terminate(self):
            pass
        def isRunning(self):
            return False
        def wait(self, ms=0):
            wait_called.append(ms)
    
    # Set an old worker (StubWorker instance)
    old = StubWorker()
    w._preview_worker = old
    
    import qt_app.main_window as mw_mod
    monkeypatch.setattr(mw_mod, "PreviewWorker", StubWorker)
    w._run_preview()
    # The old worker's wait() should NOT have been called
    assert len(wait_called) == 0, f"wait() called {len(wait_called)} times"


def test_plots_worker_detachment_does_not_wait(app, monkeypatch):
    """_start_plots_worker should not call wait() on the old worker."""
    w = MainWindow()
    
    wait_called = []
    from PySide6.QtCore import QObject, Signal
    
    class StubWorker(QObject):
        plots_ready = Signal(dict)
        failed = Signal(str)
        def __init__(self, *a, **k):
            super().__init__()
        def start(self):
            pass
        def requestInterruption(self):
            pass
        def terminate(self):
            pass
        def isRunning(self):
            return False
        def wait(self, ms=0):
            wait_called.append(ms)
    
    old = StubWorker()
    w._plots_worker = old
    
    import qt_app.main_window as mw_mod
    monkeypatch.setattr(mw_mod, "PlotsWorker", StubWorker)
    arr = (np.random.rand(10, 10, 3) * 255).astype(np.uint8)
    w._start_plots_worker(arr, arr, None)
    assert len(wait_called) == 0, f"wait() called {len(wait_called)} times"


def test_preview_worker_signal_disconnected(app, monkeypatch):
    """_run_preview should disconnect the old worker's finished_preview."""
    w = MainWindow()
    w._image_path = "/tmp/fake.jpg"
    
    from PySide6.QtCore import QObject, Signal
    
    class StubWorker(QObject):
        finished_preview = Signal(object, object, object)
        failed = Signal(str)
        def __init__(self, *a, **k):
            super().__init__()
        def start(self):
            pass
        def requestInterruption(self):
            pass
        def terminate(self):
            pass
        def isRunning(self):
            return False
        def wait(self, ms=0):
            pass
    
    old = StubWorker()
    connected = []
    old.finished_preview.connect(lambda *a: connected.append(True))
    w._preview_worker = old
    
    import qt_app.main_window as mw_mod
    monkeypatch.setattr(mw_mod, "PreviewWorker", StubWorker)
    w._run_preview()
    # After _run_preview, emitting from old should NOT call our handler
    connected.clear()
    old.finished_preview.emit(None, None, None)
    assert len(connected) == 0, "Old worker signal was not disconnected"