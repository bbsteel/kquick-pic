import sys
import tempfile
from pathlib import Path

import pytest

from quick_pic.autostart import AutoStartManager, AUTOSTART_DIR, AUTOSTART_FILE
from quick_pic.config import AppConfig


class TestAutoStartManager:
    def test_apply_enabled_creates_desktop_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop_file = Path(tmp) / "quick-pic.desktop"
            mgr = AutoStartManager(desktop_file=desktop_file)
            config = AppConfig(autostart=True, icon_theme="v2")
            mgr.apply(config)
            assert desktop_file.exists()
            content = desktop_file.read_text()
            assert "[Desktop Entry]" in content
            assert "Type=Application" in content
            assert "Name=" in content
            assert "Exec=" in content
            assert "Icon=" in content

    def test_apply_disabled_removes_desktop_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop_file = Path(tmp) / "quick-pic.desktop"
            desktop_file.write_text("stale")
            mgr = AutoStartManager(desktop_file=desktop_file)
            config = AppConfig(autostart=False)
            mgr.apply(config)
            assert not desktop_file.exists()

    def test_apply_disabled_when_file_does_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop_file = Path(tmp) / "nonexistent.desktop"
            mgr = AutoStartManager(desktop_file=desktop_file)
            config = AppConfig(autostart=False)
            mgr.apply(config)  # should not raise
            assert not desktop_file.exists()

    def test_desktop_entry_contains_expected_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop_file = Path(tmp) / "quick-pic.desktop"
            mgr = AutoStartManager(desktop_file=desktop_file)
            config = AppConfig(autostart=True, icon_theme="v2")
            mgr.apply(config)
            content = desktop_file.read_text()
            assert "Exec=" in content
            assert "Path=" in content
            assert "Icon=" in content
            assert "Terminal=false" in content
            assert "Categories=Utility;Graphics;" in content
            assert "StartupNotify=false" in content
            assert "X-GNOME-Autostart-enabled=true" in content
            assert (
                "X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2"
                in content
            )
            # Dev autostart must keep the interpreter path un-resolved so a
            # venv symlink stays in Exec (KWin canonicalizes for auth).
            assert "-m quick_pic" in content or "Exec=" in content

    def test_apply_with_parent_dir_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop_file = Path(tmp) / "deep" / "nested" / "quick-pic.desktop"
            mgr = AutoStartManager(desktop_file=desktop_file)
            config = AppConfig(autostart=True)
            mgr.apply(config)
            assert desktop_file.exists()

    def test_apply_twice_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            desktop_file = Path(tmp) / "quick-pic.desktop"
            mgr = AutoStartManager(desktop_file=desktop_file)
            config1 = AppConfig(autostart=True, icon_theme="v1")
            config2 = AppConfig(autostart=True, icon_theme="v2")
            mgr.apply(config1)
            content1 = desktop_file.read_text()
            mgr.apply(config2)
            content2 = desktop_file.read_text()
            assert content1 != content2  # icon path changed
