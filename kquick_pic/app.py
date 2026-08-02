import glob
import logging
import os
from pathlib import Path

from gi.repository import GLib

from kquick_pic.timing import log_duration, log_event, now
from kquick_pic.autostart import AutoStartManager
from kquick_pic.clipboard import ClipboardManager
from kquick_pic.config import AppConfig, ConfigManager
from kquick_pic.hotkey import HotkeyBinding, HotkeyManager
from kquick_pic.i18n import set_language, t
from kquick_pic.pin import PinManager
from kquick_pic.screenshot import ScreenshotCapture
from kquick_pic.tray import TrayManager

logger = logging.getLogger(__name__)

PID_FILE = Path.home() / ".config" / "kquick-pic" / "kquick-pic.pid"


class KQuickPicApp:

    def __init__(self):
        self._config_manager = ConfigManager()
        self._autostart_manager = AutoStartManager()
        self._config: AppConfig | None = None
        self._hotkey_manager: HotkeyManager | None = None
        self._tray_manager: TrayManager | None = None
        self._area_selector = None
        self._pin_manager = PinManager()
        self._screenshot_in_progress = False
        self._history_in_progress = False

    def run(self) -> None:
        started_at = now()
        self._config = self._config_manager.load()
        set_language(self._config.language)
        self._autostart_manager.apply(self._config)

        self._cleanup_stale_temp_screenshots()

        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

        self._tray_manager = TrayManager(
            on_screenshot=self._on_screenshot_triggered,
            on_settings=self._on_settings,
            on_quit=self._on_quit,
            on_about=self._on_about,
            config=self._config,
        )

        self._start_hotkeys()

        log_duration(
            logger,
            "app_started",
            started_at,
            pid=os.getpid(),
            hotkey=self._config.hotkey,
            history_hotkey=self._config.history_hotkey,
            history_count=self._config.history_count,
            save_path=self._config.resolved_save_path(),
            format=self._config.format,
        )
        # Pre-build the overlay widgets so the first trigger pays no
        # construction cost. The window itself stays unmapped until a capture.
        GLib.idle_add(self._prepare_area_selector)
        self._tray_manager.start()

    def _start_hotkeys(self) -> None:
        if self._hotkey_manager:
            self._hotkey_manager.stop()
            self._hotkey_manager = None
        assert self._config is not None
        bindings = [
            HotkeyBinding(
                action_id="take-screenshot",
                hotkey=self._config.hotkey,
                callback=self._on_screenshot_triggered,
                title="KQuick Pic",
                description="Take Screenshot",
            ),
            HotkeyBinding(
                action_id="show-history",
                hotkey=self._config.history_hotkey,
                callback=self._on_history_triggered,
                title="KQuick Pic",
                description="Show Recent Screenshots",
            ),
        ]
        self._hotkey_manager = HotkeyManager(bindings)
        self._hotkey_manager.start()

    def _prepare_area_selector(self) -> bool:
        try:
            from kquick_pic.area_selector import AreaSelector
            if self._area_selector is None:
                self._area_selector = AreaSelector()
            self._area_selector.prepare()
            log_event(logger, "selector_prewarmed")
        except Exception:
            logger.warning("Failed to pre-warm area selector", exc_info=True)
        return False

    def shutdown(self) -> None:
        logger.info("Shutting down...")
        if self._hotkey_manager:
            self._hotkey_manager.stop()
        if self._tray_manager:
            self._tray_manager.stop()
        if self._area_selector is not None:
            self._area_selector.destroy()
            self._area_selector = None
        self._pin_manager.close_all()
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        logger.info("Shutdown complete")

    def _on_screenshot_triggered(self, *_args) -> None:
        """Entry point for both hotkey and tray menu clicks.

        Schedules the actual work on the GTK main thread and returns
        immediately so the caller (pynput's daemon thread or the tray
        menu's activate handler) is never blocked.
        """
        source = "tray" if _args else "hotkey"
        triggered_at = now()
        log_event(logger, "screenshot_triggered", source=source)
        GLib.idle_add(self._do_screenshot, triggered_at, source)

    def _do_screenshot(self, triggered_at: float | None = None, source: str = "unknown") -> bool:
        """Runs on the GTK main thread. Owns the full select → crop → save → clipboard flow."""
        flow_started_at = now()
        if triggered_at is not None:
            log_duration(logger, "screenshot_idle_started", triggered_at, source=source)
        # run() blocks in a nested Gtk.main, which still dispatches idle
        # callbacks — a second trigger would re-enter run() and corrupt the
        # in-progress selection, so drop it here.
        if self._screenshot_in_progress or self._history_in_progress:
            log_event(logger, "screenshot_ignored_busy", source=source)
            return False
        self._screenshot_in_progress = True
        try:
            from kquick_pic.area_selector import AreaSelector
            if self._area_selector is None:
                self._area_selector = AreaSelector()
            try:
                selection = self._area_selector.run(
                    include_cursor=self._config.include_cursor,
                )
            except Exception:
                self._area_selector.destroy()
                self._area_selector = None
                raise
            if selection is None:
                log_duration(logger, "screenshot_cancelled", flow_started_at, source=source)
                return False
            log_event(
                logger,
                "screenshot_selection_ready",
                rect=selection.rect,
                annotations=len(selection.annotations),
                pin=selection.pin,
            )
            save_started_at = now()
            try:
                path = ScreenshotCapture.capture_selection(
                    self._config,
                    selection.screenshot_path,
                    selection.rect,
                    selection.annotations,
                )
            finally:
                selection.screenshot_path.unlink(missing_ok=True)
            log_duration(logger, "screenshot_saved_to_disk", save_started_at, path=path)
            clipboard_started_at = now()
            ClipboardManager.set_path(str(path))
            log_duration(logger, "screenshot_copied_to_clipboard", clipboard_started_at, path=path)
            # Pin only when the user chose the pin toolbar button.
            if selection.pin:
                pin_started_at = now()
                pin_x, pin_y, _, _ = selection.rect
                pinned = self._pin_manager.pin(path, position=(pin_x, pin_y))
                log_duration(
                    logger,
                    "screenshot_pinned",
                    pin_started_at,
                    path=path,
                    pinned=pinned is not None,
                    open_pins=self._pin_manager.count,
                )
            log_duration(
                logger,
                "screenshot_flow_finished",
                flow_started_at,
                source=source,
                path=path,
                pin=selection.pin,
            )
        except Exception:
            logger.exception("Screenshot capture failed")
            if self._tray_manager:
                self._tray_manager.notify(t("notify.app_name"), t("notify.screenshot_failed"))
        finally:
            self._screenshot_in_progress = False
        return False

    def _on_history_triggered(self, *_args) -> None:
        log_event(logger, "history_triggered")
        GLib.idle_add(self._do_history)

    def _do_history(self) -> bool:
        """Show recent screenshots; left-click copies path to clipboard."""
        if self._screenshot_in_progress or self._history_in_progress:
            log_event(logger, "history_ignored_busy")
            return False
        assert self._config is not None
        self._history_in_progress = True
        try:
            from kquick_pic.history import list_recent_screenshots
            from kquick_pic.history_picker import HistoryPicker

            paths = list_recent_screenshots(
                self._config.resolved_save_path(),
                self._config.history_count,
            )
            log_event(
                logger,
                "history_listed",
                count=len(paths),
                limit=self._config.history_count,
                save_path=self._config.resolved_save_path(),
            )
            if not paths:
                if self._tray_manager:
                    self._tray_manager.notify(
                        t("notify.app_name"),
                        t("notify.history_empty"),
                    )
                return False

            picker = HistoryPicker()
            selected = picker.run(paths)
            if selected is None:
                log_event(logger, "history_cancelled")
                return False
            ClipboardManager.set_path(str(selected))
            log_event(logger, "history_path_copied", path=selected)
        except Exception:
            logger.exception("History picker failed")
            if self._tray_manager:
                self._tray_manager.notify(
                    t("notify.app_name"),
                    t("notify.history_failed"),
                )
        finally:
            self._history_in_progress = False
        return False

    def _cleanup_stale_temp_screenshots(self) -> None:
        try:
            stale = [Path(p) for p in glob.glob("/tmp/tmp*.png")]
            for path in stale:
                path.unlink(missing_ok=True)
            if stale:
                logger.info(f"Cleaned up {len(stale)} stale screenshot temp files")
        except Exception:
            logger.warning("Failed to clean stale temp screenshots", exc_info=True)

    def _on_about(self, widget) -> None:
        from kquick_pic.about import AboutDialog
        dialog = AboutDialog()
        dialog.run()
        dialog.destroy()

    def _on_settings(self, widget) -> None:
        from kquick_pic.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._config)
        result = dialog.run()
        dialog.destroy()

        if result is None:
            return

        old_hotkey = self._config.hotkey
        old_history_hotkey = self._config.history_hotkey
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

        if (
            result.hotkey != old_hotkey
            or result.history_hotkey != old_history_hotkey
        ):
            logger.info(
                "Hotkeys changed, restarting listener: "
                f"screenshot={result.hotkey} history={result.history_hotkey}"
            )
            self._start_hotkeys()

    def _on_quit(self, widget) -> None:
        self.shutdown()
