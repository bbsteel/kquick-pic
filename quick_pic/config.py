from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "quick-pic" / "config.json"

VALID_FORMATS = ["png", "jpg"]
VALID_ICON_THEMES = ["v1", "v2"]


@dataclass
class AppConfig:
    save_path: str = "~/Pictures/quick-pic"
    format: str = "png"
    hotkey: str = "<ctrl>+<shift>+p"
    icon_theme: str = "v1"

    def resolved_save_path(self) -> Path:
        return Path(self.save_path).expanduser().resolve()


class ConfigManager:

    def __init__(self, config_path: Path | None = None):
        self._path = config_path or DEFAULT_CONFIG_PATH

    def load(self) -> AppConfig:
        try:
            with open(self._path, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.info("Config file missing or corrupt, using defaults")
            config = AppConfig()
            self.save(config)
            return config

        config = AppConfig(
            save_path=data.get("save_path", AppConfig.save_path),
            format=data.get("format", AppConfig.format),
            hotkey=data.get("hotkey", AppConfig.hotkey),
            icon_theme=data.get("icon_theme", AppConfig.icon_theme),
        )

        if config.icon_theme not in VALID_ICON_THEMES:
            logger.info(f"Unknown icon_theme '{config.icon_theme}', falling back to default")
            config.icon_theme = AppConfig.icon_theme

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

    def _validate(self, config: AppConfig) -> bool:
        if config.format not in VALID_FORMATS:
            logger.warning(f"Invalid format '{config.format}', must be one of {VALID_FORMATS}")
            return False
        if config.icon_theme not in VALID_ICON_THEMES:
            logger.warning(f"Invalid icon_theme '{config.icon_theme}', must be one of {VALID_ICON_THEMES}")
            return False
        try:
            from pynput.keyboard import HotKey
            HotKey.parse(config.hotkey)
        except Exception:
            logger.warning(f"Invalid hotkey string '{config.hotkey}'")
            return False
        return True
