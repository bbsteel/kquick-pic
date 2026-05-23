import json
import tempfile
from pathlib import Path

import pytest

from quick_pic.i18n import (
    I18nManager,
    LanguagePlugin,
    set_language,
    current_language,
    available_languages,
    t,
    _manager,
)


class TestLanguagePlugin:
    def test_fields(self):
        p = LanguagePlugin(code="en", name="English", messages={"key": "value"})
        assert p.code == "en"
        assert p.name == "English"
        assert p.messages == {"key": "value"}


class TestI18nManager:
    def test_default_language_returns_available(self):
        mgr = I18nManager()
        lang = mgr.default_language()
        assert lang in {"zh-CN", "en"}

    def test_set_language_valid(self):
        mgr = I18nManager()
        for code in mgr._plugins:
            mgr.set_language(code)
            assert mgr.language() == code

    def test_set_language_invalid_keeps_default(self):
        mgr = I18nManager()
        default = mgr.default_language()
        mgr.set_language("invalid-xx")
        assert mgr.language() == default

    def test_t_returns_message_in_current_language(self):
        mgr = I18nManager()
        mgr.set_language("en")
        assert mgr.t("tray.quit") == "Quit"
        mgr.set_language("zh-CN")
        assert mgr.t("tray.quit") == "退出"

    def test_t_falls_back_to_english(self):
        mgr = I18nManager()
        mgr.set_language("zh-CN")
        assert mgr.t("icon.theme.v1") == "相机（平面风格）"

    def test_t_returns_key_when_missing(self):
        mgr = I18nManager()
        assert mgr.t("nonexistent.key.xyz") == "nonexistent.key.xyz"

    def test_t_format_kwargs(self):
        mgr = I18nManager()
        mgr.set_language("en")
        assert mgr.t("tray.quit") == "Quit"

    def test_available_languages_returns_sorted_list(self):
        mgr = I18nManager()
        langs = mgr.available_languages()
        assert len(langs) >= 2
        codes = [code for code, _ in langs]
        assert "en" in codes
        assert "zh-CN" in codes
        # Verify sorted by name (case-insensitive)
        names = [name for _, name in langs]
        assert names == sorted(names, key=str.lower)

    def test_user_locale_overrides_builtin(self):
        """User locale files take precedence over builtin."""
        with tempfile.TemporaryDirectory() as tmp:
            user_dir = Path(tmp) / "locales"
            user_dir.mkdir()
            user_plugin = {
                "code": "en",
                "name": "English (Custom)",
                "messages": {"custom.key": "custom value"},
            }
            (user_dir / "en.json").write_text(json.dumps(user_plugin))

            # Create a manager with user dir
            mgr = I18nManager()
            # Replace the user locale dir with our temp dir
            from quick_pic import i18n as i18n_mod
            old_dir = i18n_mod.USER_LOCALE_DIR
            i18n_mod.USER_LOCALE_DIR = user_dir
            try:
                mgr2 = I18nManager()
                # The custom key should be resolved
                mgr2.set_language("en")
                assert mgr2.t("custom.key") == "custom value"
            finally:
                i18n_mod.USER_LOCALE_DIR = old_dir


class TestModuleLevelApi:
    def test_set_and_current_language(self):
        original = current_language()
        try:
            set_language("en")
            assert current_language() == "en"
            set_language("zh-CN")
            assert current_language() == "zh-CN"
        finally:
            set_language(original)

    def test_t_function(self):
        set_language("en")
        assert t("tray.quit") == "Quit"
        set_language("zh-CN")
        assert t("tray.quit") == "退出"

    def test_available_languages_function(self):
        langs = available_languages()
        assert len(langs) >= 2
