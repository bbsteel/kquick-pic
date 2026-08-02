import json
import tempfile
from pathlib import Path

import pytest

from kquick_pic.config import (
    AppConfig,
    ConfigManager,
    HISTORY_COUNT_DEFAULT,
    VALID_FORMATS,
    VALID_ICON_THEMES,
)


class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.save_path == "~/Pictures/kquick-pic"
        assert cfg.format == "png"
        assert cfg.hotkey == "<ctrl>+<shift>+p"
        assert cfg.icon_theme == "v1"
        assert cfg.autostart is False
        assert cfg.include_cursor is True
        assert cfg.history_hotkey == "<ctrl>+<shift>+h"
        assert cfg.history_count == HISTORY_COUNT_DEFAULT

    def test_resolved_save_path(self):
        cfg = AppConfig(save_path="~/test-dir")
        resolved = cfg.resolved_save_path()
        assert resolved == Path.home() / "test-dir"

    def test_custom_values(self):
        cfg = AppConfig(
            save_path="/tmp/pics",
            format="jpg",
            hotkey="<ctrl>+q",
            icon_theme="v2",
            autostart=True,
            include_cursor=False,
            history_hotkey="<alt>+h",
            history_count=8,
        )
        assert cfg.format == "jpg"
        assert cfg.hotkey == "<ctrl>+q"
        assert cfg.icon_theme == "v2"
        assert cfg.autostart is True
        assert cfg.include_cursor is False
        assert cfg.history_hotkey == "<alt>+h"
        assert cfg.history_count == 8


class TestConfigManager:
    def test_load_defaults_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nonexistent" / "config.json"
            mgr = ConfigManager(config_path=path)
            cfg = mgr.load()
            assert cfg.format == "png"
            assert cfg.save_path == "~/Pictures/kquick-pic"
            assert path.exists()  # saved defaults back

    def test_load_valid_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            data = {
                "save_path": "/tmp/pics",
                "format": "jpg",
                "hotkey": "<ctrl>+q",
                "icon_theme": "v2",
                "autostart": True,
                "language": "en",
                "include_cursor": False,
                "history_hotkey": "<alt>+h",
                "history_count": 3,
            }
            path.write_text(json.dumps(data))
            mgr = ConfigManager(config_path=path)
            cfg = mgr.load()
            assert cfg.save_path == "/tmp/pics"
            assert cfg.format == "jpg"
            assert cfg.hotkey == "<ctrl>+q"
            assert cfg.icon_theme == "v2"
            assert cfg.autostart is True
            assert cfg.include_cursor is False
            assert cfg.history_hotkey == "<alt>+h"
            assert cfg.history_count == 3

    def test_load_corrupt_json_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text("not valid json {{{")
            mgr = ConfigManager(config_path=path)
            cfg = mgr.load()
            assert cfg.format == "png"
            assert path.read_text() != "not valid json {{{"  # rewritten

    def test_load_invalid_format_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"format": "bmp"}))
            mgr = ConfigManager(config_path=path)
            cfg = mgr.load()
            assert cfg.format == "png"

    def test_load_invalid_icon_theme_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"icon_theme": "nonexistent"}))
            mgr = ConfigManager(config_path=path)
            cfg = mgr.load()
            assert cfg.icon_theme == "v1"

    def test_load_invalid_hotkey_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"hotkey": "<<<invalid>>>"}))
            mgr = ConfigManager(config_path=path)
            cfg = mgr.load()
            assert cfg.hotkey == "<ctrl>+<shift>+p"

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            mgr = ConfigManager(config_path=path)
            original = AppConfig(
                save_path="/custom/path",
                format="jpg",
                hotkey="<alt>+<shift>+s",
                icon_theme="v2",
                autostart=True,
                include_cursor=False,
                history_hotkey="<ctrl>+h",
                history_count=10,
            )
            mgr.save(original)
            loaded = mgr.load()
            assert loaded.save_path == original.save_path
            assert loaded.format == original.format
            assert loaded.hotkey == original.hotkey
            assert loaded.icon_theme == original.icon_theme
            assert loaded.autostart == original.autostart
            assert loaded.include_cursor is False
            assert loaded.history_hotkey == original.history_hotkey
            assert loaded.history_count == original.history_count

    def test_save_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep" / "nested" / "config.json"
            mgr = ConfigManager(config_path=path)
            mgr.save(AppConfig())
            assert path.exists()

    def test_save_atomic_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            mgr = ConfigManager(config_path=path)
            mgr.save(AppConfig())
            tmp_path = path.with_suffix(".tmp")
            assert not tmp_path.exists()  # tmp file cleaned up after os.replace

    def test_load_missing_keys_use_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"format": "jpg"}))
            mgr = ConfigManager(config_path=path)
            cfg = mgr.load()
            assert cfg.format == "jpg"
            assert cfg.save_path == "~/Pictures/kquick-pic"
            assert cfg.hotkey == "<ctrl>+<shift>+p"
            assert cfg.include_cursor is True
            assert cfg.history_hotkey == "<ctrl>+<shift>+h"
            assert cfg.history_count == HISTORY_COUNT_DEFAULT

    def test_load_invalid_history_count_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"history_count": 99, "hotkey": "<ctrl>+a", "history_hotkey": "<ctrl>+b"}))
            mgr = ConfigManager(config_path=path)
            cfg = mgr.load()
            assert cfg.history_count == HISTORY_COUNT_DEFAULT

    def test_migrates_legacy_quick_pic_config(self, tmp_path, monkeypatch):
        import kquick_pic.config as config_mod

        legacy_dir = tmp_path / "quick-pic"
        legacy_dir.mkdir()
        legacy_cfg = legacy_dir / "config.json"
        legacy_cfg.write_text(
            json.dumps(
                {
                    "save_path": "/tmp/legacy-shots",
                    "format": "jpg",
                    "hotkey": "<ctrl>+a",
                    "history_hotkey": "<ctrl>+b",
                    "language": "en",
                    "history_count": 4,
                }
            )
        )
        new_path = tmp_path / "kquick-pic" / "config.json"
        monkeypatch.setattr(config_mod, "DEFAULT_CONFIG_PATH", new_path)
        monkeypatch.setattr(config_mod, "LEGACY_CONFIG_PATH", legacy_cfg)
        monkeypatch.setattr(config_mod, "LEGACY_CONFIG_DIR", legacy_dir)

        mgr = ConfigManager(config_path=new_path)
        cfg = mgr.load()
        assert new_path.is_file()
        assert cfg.save_path == "/tmp/legacy-shots"
        assert cfg.format == "jpg"
        assert cfg.history_count == 4
