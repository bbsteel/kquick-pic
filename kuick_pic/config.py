from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import logging
import os
import shutil

from kuick_pic.i18n import available_languages, current_language

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "kuick-pic" / "config.json"
# Newest rename first: kquick-pic → kuick-pic, then the original quick-pic.
LEGACY_CONFIG_DIRS = (
    Path.home() / ".config" / "kquick-pic",
    Path.home() / ".config" / "quick-pic",
)

VALID_FORMATS = ["png", "jpg"]
VALID_ICON_THEMES = ["v1", "v2"]
HISTORY_COUNT_MIN = 1
HISTORY_COUNT_MAX = 20
HISTORY_COUNT_DEFAULT = 5


@dataclass
class AppConfig:
    save_path: str = "~/Pictures/kuick-pic"
    format: str = "png"
    hotkey: str = "<ctrl>+<shift>+p"
    icon_theme: str = "v1"
    autostart: bool = False
    language: str = field(default_factory=current_language)
    # Include the mouse cursor in the freeze-frame capture.
    include_cursor: bool = True
    # Recent-history picker (thumbnail strip).
    history_hotkey: str = "<ctrl>+<shift>+h"
    history_count: int = HISTORY_COUNT_DEFAULT

    def resolved_save_path(self) -> Path:
        return Path(self.save_path).expanduser().resolve()


class ConfigManager:

    def __init__(self, config_path: Path | None = None):
        self._path = config_path or DEFAULT_CONFIG_PATH

    def load(self) -> AppConfig:
        if self._path == DEFAULT_CONFIG_PATH:
            self._maybe_migrate_legacy_config()
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info("Config file missing or corrupt, using defaults")
            config = AppConfig()
            self.save(config)
            return config

        history_count = data.get("history_count", AppConfig.history_count)
        try:
            history_count = int(history_count)
        except (TypeError, ValueError):
            history_count = HISTORY_COUNT_DEFAULT

        config = AppConfig(
            save_path=data.get("save_path", AppConfig.save_path),
            format=data.get("format", AppConfig.format),
            hotkey=data.get("hotkey", AppConfig.hotkey),
            icon_theme=data.get("icon_theme", AppConfig.icon_theme),
            autostart=data.get("autostart", AppConfig.autostart),
            language=data.get("language", current_language()),
            include_cursor=bool(data.get("include_cursor", AppConfig.include_cursor)),
            history_hotkey=data.get("history_hotkey", AppConfig.history_hotkey),
            history_count=history_count,
        )

        if config.icon_theme not in VALID_ICON_THEMES:
            logger.info(f"Unknown icon_theme '{config.icon_theme}', falling back to default")
            config.icon_theme = AppConfig.icon_theme
        valid_languages = {code for code, _ in available_languages()}
        if config.language not in valid_languages:
            logger.info(f"Unknown language '{config.language}', falling back to current language")
            config.language = current_language()
        if not (HISTORY_COUNT_MIN <= config.history_count <= HISTORY_COUNT_MAX):
            logger.info(
                f"history_count {config.history_count} out of range, "
                f"falling back to {HISTORY_COUNT_DEFAULT}"
            )
            config.history_count = HISTORY_COUNT_DEFAULT

        if not self._validate(config):
            logger.warning("Config validation failed, using defaults")
            config = AppConfig()
            self.save(config)

        return config

    def save(self, config: AppConfig) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            json.dump(asdict(config), f, indent=2)
            f.write("\n")
        os.replace(tmp_path, self._path)
        logger.info(f"Config saved to {self._path}")

    def _maybe_migrate_legacy_config(self) -> None:
        """Copy the newest legacy config dir into ~/.config/kuick-pic once."""
        if self._path.exists():
            return
        for legacy_dir in LEGACY_CONFIG_DIRS:
            legacy_path = legacy_dir / "config.json"
            if not legacy_path.is_file():
                continue
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_path, self._path)
                legacy_locales = legacy_dir / "locales"
                new_locales = self._path.parent / "locales"
                if legacy_locales.is_dir() and not new_locales.exists():
                    shutil.copytree(legacy_locales, new_locales)
                logger.info(
                    "Migrated config from %s to %s",
                    legacy_path,
                    self._path,
                )
            except OSError:
                logger.warning("Failed to migrate legacy config", exc_info=True)
            return

    def _validate(self, config: AppConfig) -> bool:
        if config.format not in VALID_FORMATS:
            logger.warning(f"Invalid format '{config.format}', must be one of {VALID_FORMATS}")
            return False
        if config.icon_theme not in VALID_ICON_THEMES:
            logger.warning(f"Invalid icon_theme '{config.icon_theme}', must be one of {VALID_ICON_THEMES}")
            return False
        if not (HISTORY_COUNT_MIN <= config.history_count <= HISTORY_COUNT_MAX):
            logger.warning(
                f"Invalid history_count '{config.history_count}', "
                f"must be {HISTORY_COUNT_MIN}..{HISTORY_COUNT_MAX}"
            )
            return False
        try:
            from pynput.keyboard import HotKey
            HotKey.parse(config.hotkey)
            HotKey.parse(config.history_hotkey)
        except Exception:
            logger.warning(
                f"Invalid hotkey string hotkey={config.hotkey!r} "
                f"history_hotkey={config.history_hotkey!r}"
            )
            return False
        if config.hotkey == config.history_hotkey:
            logger.warning("Screenshot and history hotkeys must differ")
            return False
        return True
