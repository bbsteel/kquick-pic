import os
import threading
import logging
from pathlib import Path

from quick_pic.autostart import AutoStartManager
from quick_pic.config import ConfigManager, AppConfig
from quick_pic.i18n import set_language, t
from quick_pic.screenshot import ScreenshotCapture
from quick_pic.clipboard import ClipboardManager
from quick_pic.hotkey import HotkeyManager
from quick_pic.tray import TrayManager

logger = logging.getLogger(__name__)

PID_FILE = Path.home() / ".config" / "quick-pic" / "quick-pic.pid"


class QuickPicApp:

    def __init__(self):
        self._config_manager = ConfigManager()
        self._autostart_manager = AutoStartManager()
        self._config: AppConfig | None = None
        self._hotkey_manager: HotkeyManager | None = None
        self._tray_manager: TrayManager | None = None

    def run(self) -> None:
        self._config = self._config_manager.load()
        set_language(self._config.language)
        self._autostart_manager.apply(self._config)

        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

        self._tray_manager = TrayManager(
            on_screenshot=self._on_tray_screenshot,
            on_settings=self._on_settings,
            on_quit=self._on_quit,
            config=self._config,
        )

        self._hotkey_manager = HotkeyManager(
            hotkey_str=self._config.hotkey,
            callback=self._on_screenshot_triggered,
        )
        self._hotkey_manager.start()

        self._tray_manager.start()

    def shutdown(self) -> None:
        logger.info("Shutting down...")
        if self._hotkey_manager:
            self._hotkey_manager.stop()
        if self._tray_manager:
            self._tray_manager.stop()
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        logger.info("Shutdown complete")

    def _on_screenshot_triggered(self) -> None:
        """Area selection → capture → clipboard. Runs on hotkey daemon thread."""
        try:
            selection = self._request_area_selection()
            if selection is None:
                return
            path = ScreenshotCapture.capture_selection(
                self._config,
                selection.screenshot_path,
                selection.rect,
                selection.annotations,
            )
            ClipboardManager.set_path_async(str(path))
        except Exception:
            logger.exception("Screenshot capture failed")
            if self._tray_manager:
                self._tray_manager.notify(t("notify.app_name"), t("notify.screenshot_failed"))

    def _on_tray_screenshot(self, widget) -> None:
        """GTK menu callback — spawn worker thread."""
        t = threading.Thread(target=self._on_screenshot_triggered, daemon=True)
        t.start()

    def _request_area_selection(self):
        """Show the area selector. Must run on GTK main thread."""
        from quick_pic.area_selector import AreaSelector
        from gi.repository import GLib
        import queue

        q: queue.Queue = queue.Queue()

        def _run():
            selector = AreaSelector()
            result = selector.run()
            selector.destroy()
            q.put(result)

        GLib.idle_add(_run)
        # Since we might be called from GTK main thread (tray menu),
        # handle both cases
        try:
            return q.get(timeout=60)
        except queue.Empty:
            return None

    def _on_settings(self, widget) -> None:
        from quick_pic.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._config)
        result = dialog.run()
        dialog.destroy()

        if result is None:
            return

        old_hotkey = self._config.hotkey
        old_icon_theme = self._config.icon_theme
        old_language = self._config.language
        self._config = result
        set_language(result.language)
        self._config_manager.save(self._config)
        self._autostart_manager.apply(self._config)

        if result.icon_theme != old_icon_theme:
            self._tray_manager.update_icon_theme(result.icon_theme)

        if result.language != old_language:
            self._tray_manager.update_language()

        if result.hotkey != old_hotkey:
            logger.info(f"Hotkey changed, restarting listener with: {result.hotkey}")
            if self._hotkey_manager:
                self._hotkey_manager.stop()
            self._hotkey_manager = HotkeyManager(
                hotkey_str=result.hotkey,
                callback=self._on_screenshot_triggered,
            )
            self._hotkey_manager.start()

    def _on_quit(self, widget) -> None:
        self.shutdown()
