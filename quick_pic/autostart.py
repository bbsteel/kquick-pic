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
        if getattr(sys, "frozen", False):
            exec_path = Path(sys.executable).resolve()
            exec_cmd = str(exec_path)
            working_dir = str(exec_path.parent)
        else:
            # Keep the venv symlink (do not resolve to /usr/bin/python3.x):
            # - launching must use the venv so site-packages resolve
            # - KWin still canonicalizes Exec[0] for ScreenShot2 auth match
            python_path = Path(sys.executable)
            if not python_path.is_absolute():
                python_path = python_path.resolve()
            exec_cmd = f"{python_path} -m quick_pic"
            working_dir = str(Path(__file__).resolve().parent.parent)

        icon_path = get_icon_path(config.icon_theme).resolve()

        desktop_entry = "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                "Version=1.0",
                f"Name={t('autostart.name')}",
                f"Comment={t('autostart.comment')}",
                f"Exec={exec_cmd}",
                f"Path={working_dir}",
                f"Icon={icon_path}",
                "Terminal=false",
                "Categories=Utility;Graphics;",
                "StartupNotify=false",
                "X-GNOME-Autostart-enabled=true",
                # Same restricted interface as applications/*.desktop so a
                # process launched via autostart is also authorized for KWin.
                "X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2",
                "",
            ]
        )

        self._desktop_file.parent.mkdir(parents=True, exist_ok=True)
        self._desktop_file.write_text(desktop_entry, encoding="utf-8")
        logger.info(f"Autostart enabled at {self._desktop_file}")
