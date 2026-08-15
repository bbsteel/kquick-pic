"""Tests for pinned screenshot windows."""

from pathlib import Path

import pytest
from PIL import Image

from kuick_pic.pin import BORDER_PX, PinManager, PinnedScreenshot


def _make_png(path: Path, size=(40, 30), color=(20, 40, 60)) -> Path:
    Image.new("RGB", size, color).save(path, format="PNG")
    return path


class TestPinManager:
    def test_count_starts_at_zero(self):
        mgr = PinManager()
        assert mgr.count == 0

    def test_close_all_on_empty_is_safe(self):
        mgr = PinManager()
        mgr.close_all()
        assert mgr.count == 0

    def test_pin_missing_file_returns_none(self, tmp_path):
        mgr = PinManager()
        result = mgr.pin(tmp_path / "does-not-exist.png", position=(10, 20))
        assert result is None
        assert mgr.count == 0


@pytest.mark.skipif(
    __import__("os").environ.get("DISPLAY") is None
    and __import__("os").environ.get("WAYLAND_DISPLAY") is None,
    reason="GTK display required",
)
class TestPinnedScreenshotGtk:
    def test_pin_show_and_close(self, tmp_path):
        path = _make_png(tmp_path / "shot.png")
        closed = []

        pin = PinnedScreenshot(
            path,
            position=(100, 80),
            on_closed=lambda p: closed.append(p),
        )
        pin.show()
        assert pin.is_open
        assert pin.image_path == path

        pin.close()
        assert not pin.is_open
        assert closed == [pin]
        # second close is a no-op
        pin.close()
        assert closed == [pin]

    def test_manager_tracks_open_pins(self, tmp_path):
        path_a = _make_png(tmp_path / "a.png", size=(20, 20), color=(255, 0, 0))
        path_b = _make_png(tmp_path / "b.png", size=(30, 20), color=(0, 255, 0))
        mgr = PinManager()

        pin_a = mgr.pin(path_a, position=(0, 0))
        pin_b = mgr.pin(path_b, position=(50, 50))
        assert pin_a is not None and pin_b is not None
        assert mgr.count == 2

        pin_a.close()
        assert mgr.count == 1

        mgr.close_all()
        assert mgr.count == 0
        assert not pin_b.is_open

    def test_border_constant_positive(self):
        assert BORDER_PX >= 3
