from pathlib import Path
import logging
import sys

from quick_pic.icon import get_icon_path
from quick_pic.i18n import t

logger = logging.getLogger(__name__)

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "quick-pic.desktop"


class AutoStartManager:
    def __init__(self, desktop_file: Path | None = None):
        self._desktop_file = desktop_file or AUTOSTART_FILE

    def apply(self, config) -> None:
        if config.autostart:
            self._write_desktop_entry(config)
        else:
            self._desktop_file.unlink(missing_ok=True)
            logger.info("Autostart disabled")

    def _write_desktop_entry(self, config) -> None:
        project_root = Path(__file__).resolve().parent.parent
        python_executable = Path(sys.executable).resolve()
        icon_path = get_icon_path(config.icon_theme).resolve()

        desktop_entry = "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Version=1.0",
                f"Name={t('autostart.name')}",
                f"Comment={t('autostart.comment')}",
                f"Exec={python_executable} -m quick_pic",
                f"Path={project_root}",
                f"Icon={icon_path}",
                "Terminal=false",
                "Categories=Utility;Graphics;",
                "X-GNOME-Autostart-enabled=true",
                "",
            ]
        )

        self._desktop_file.parent.mkdir(parents=True, exist_ok=True)
        self._desktop_file.write_text(desktop_entry, encoding="utf-8")
        logger.info(f"Autostart enabled at {self._desktop_file}")
