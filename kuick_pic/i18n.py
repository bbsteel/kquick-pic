from dataclasses import dataclass
from pathlib import Path
import json
import locale
import logging
import sys

logger = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    BUILTIN_LOCALE_DIR = Path(sys._MEIPASS) / "kuick_pic" / "locales"
else:
    BUILTIN_LOCALE_DIR = Path(__file__).resolve().parent / "locales"
USER_LOCALE_DIR = Path.home() / ".config" / "kuick-pic" / "locales"


@dataclass(frozen=True)
class LanguagePlugin:
    code: str
    name: str
    messages: dict[str, str]


class I18nManager:
    def __init__(self):
        self._plugins = self._load_plugins()
        self._fallback_language = "en"
        self._language = self.default_language()

    def default_language(self) -> str:
        locale_name = locale.getlocale()[0] or locale.getdefaultlocale()[0]
        if locale_name and locale_name.lower().startswith("zh"):
            return "zh-CN"
        return self._fallback_language

    def set_language(self, language: str) -> None:
        if language in self._plugins:
            self._language = language
        else:
            logger.warning(f"Unknown language '{language}', falling back to {self.default_language()}")
            self._language = self.default_language()

    def language(self) -> str:
        return self._language

    def available_languages(self) -> list[tuple[str, str]]:
        return sorted(
            ((code, plugin.name) for code, plugin in self._plugins.items()),
            key=lambda item: item[1].lower(),
        )

    def t(self, key: str, **kwargs) -> str:
        message = self._resolve(self._language, key) or self._resolve(self._fallback_language, key) or key
        return message.format(**kwargs) if kwargs else message

    def _resolve(self, language: str, key: str) -> str | None:
        plugin = self._plugins.get(language)
        if plugin is None:
            return None
        return plugin.messages.get(key)

    def _load_plugins(self) -> dict[str, LanguagePlugin]:
        plugins: dict[str, LanguagePlugin] = {}
        for directory in (BUILTIN_LOCALE_DIR, USER_LOCALE_DIR):
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    logger.exception(f"Failed to load language plugin: {path}")
                    continue
                code = data.get("code")
                name = data.get("name")
                messages = data.get("messages")
                if not code or not name or not isinstance(messages, dict):
                    logger.warning(f"Skipping invalid language plugin: {path}")
                    continue
                plugins[code] = LanguagePlugin(code=code, name=name, messages=messages)
        return plugins


_manager = I18nManager()


def set_language(language: str) -> None:
    _manager.set_language(language)


def current_language() -> str:
    return _manager.language()


def available_languages() -> list[tuple[str, str]]:
    return _manager.available_languages()


def t(key: str, **kwargs) -> str:
    return _manager.t(key, **kwargs)
