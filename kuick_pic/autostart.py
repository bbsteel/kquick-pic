from pathlib import Path
import logging
import sys

from kuick_pic.icon import get_icon_path
from kuick_pic.i18n import t

logger = logging.getLogger(__name__)

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "kuick-pic.desktop"
_LEGACY_AUTOSTART_NAMES = ("kquick-pic.desktop", "quick-pic.desktop")


class AutoStartManager:
    def __init__(self, desktop_file: Path | None = None):
        self._desktop_file = desktop_file or AUTOSTART_FILE

    def apply(self, config) -> None:
        if config.autostart:
            self._write_desktop_entry(config)
            self._remove_legacy_desktop_files()
        else:
            self._desktop_file.unlink(missing_ok=True)
            self._remove_legacy_desktop_files()
            logger.info("Autostart disabled")

    def _remove_legacy_desktop_files(self) -> None:
        parent = self._desktop_file.parent
        for name in _LEGACY_AUTOSTART_NAMES:
            legacy = parent / name
            if legacy == self._desktop_file:
                continue
            try:
                legacy.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to remove leftover autostart file %s", legacy)

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
            exec_cmd = f"{python_path} -m kuick_pic"
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
