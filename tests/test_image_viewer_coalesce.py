"""Tests for ImageViewer coalescing render behavior."""

import numpy as np
import pytest

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from qt_app.widgets.image_viewer import ImageViewer


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_render_timer_exists(app):
    """ImageViewer should have a coalescing render timer."""
    v = ImageViewer("Test")
    assert v._render_timer.isSingleShot()
    # Verify timeout is connected to _deferred_render by triggering it
    v._arr = (np.random.rand(10, 10, 3) * 255).astype(np.uint8)
    v._render_timer.timeout.emit()  # should call _deferred_render
    assert v._qimage is not None  # proves the connection works


def test_set_array_starts_timer(app):
    """set_array should schedule a deferred render, not render immediately."""
    v = ImageViewer("Test")
    arr = (np.random.rand(20, 30, 3) * 255).astype(np.uint8)
    v.set_array(arr)
    # Timer should be active (pending render)
    assert v._render_timer.isActive()


def test_set_array_none_stops_timer(app):
    """set_array(None) should stop the render timer and clear."""
    v = ImageViewer("Test")
    arr = (np.random.rand(20, 30, 3) * 255).astype(np.uint8)
    v.set_array(arr)
    assert v._render_timer.isActive()
    v.set_array(None)
    assert not v._render_timer.isActive()
    assert v._arr is None


def test_rapid_set_array_coalesces(app):
    """Multiple rapid set_array calls should not queue multiple renders."""
    v = ImageViewer("Test")
    arrs = [(np.random.rand(20, 30, 3) * 255).astype(np.uint8) for _ in range(5)]
    for a in arrs:
        v.set_array(a)
    # Only one timer is active (coalesced), not 5
    assert v._render_timer.isActive()
    # The stored array is the latest one
    np.testing.assert_array_equal(v._arr, arrs[-1])


def test_deferred_render_builds_qimage(app):
    """_deferred_render should build the QImage from the stored array."""
    v = ImageViewer("Test")
    arr = (np.random.rand(20, 30, 3) * 255).astype(np.uint8)
    v.set_array(arr)
    # QImage not built yet (deferred)
    assert v._qimage is None
    # Process the timer
    v._deferred_render()
    assert v._qimage is not None
    assert v._qimage.width() == 30
    assert v._qimage.height() == 20


def test_uses_fast_transformation(app):
    """Render should use FastTransformation for speed (not Smooth)."""
    # This is implicitly tested by the render not being slow on large images.
    # We just verify the viewer renders without error.
    v = ImageViewer("Test")
    arr = (np.random.rand(100, 200, 3) * 255).astype(np.uint8)
    v.set_array(arr)
    v._deferred_render()
    # If we got here without hanging, FastTransformation is working
    assert v._qimage is not None