import tempfile
from pathlib import Path
from datetime import datetime

import pytest

from quick_pic.screenshot import ScreenshotCapture
from quick_pic.config import AppConfig


class TestNextOutputPath:
    def test_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(save_path=f"{tmp}/screenshots", format="png")
            path = ScreenshotCapture._next_output_path(config)
            assert path.parent == Path(f"{tmp}/screenshots")
            assert path.parent.exists()

    def test_uses_correct_format_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(save_path=tmp, format="jpg")
            path = ScreenshotCapture._next_output_path(config)
            assert path.suffix == ".jpg"

        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(save_path=tmp, format="png")
            path = ScreenshotCapture._next_output_path(config)
            assert path.suffix == ".png"

    def test_generates_unique_names_when_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(save_path=tmp, format="png")
            path1 = ScreenshotCapture._next_output_path(config)
            path1.write_text("")  # create file so collision detection triggers
            path2 = ScreenshotCapture._next_output_path(config)
            assert path1 != path2

    def test_filename_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = AppConfig(save_path=tmp, format="png")
            path = ScreenshotCapture._next_output_path(config)
            assert path.name.startswith("quick-pic-")
            assert path.name.endswith(".png")

    def test_resolves_home_directory(self, tmp_path, monkeypatch):
        # Expand ~ via HOME so we never mkdir under the real $HOME root
        # (agent sandboxes often forbid creating /home/<user>/tmp*).
        monkeypatch.setenv("HOME", str(tmp_path))
        config = AppConfig(save_path="~/screenshots", format="png")
        path = ScreenshotCapture._next_output_path(config)
        assert isinstance(path, Path)
        assert path.parent == tmp_path / "screenshots"
        assert path.parent.exists()
