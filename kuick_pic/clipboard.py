import logging

from kuick_pic.timing import log_duration, now

logger = logging.getLogger(__name__)


class ClipboardManager:

    @staticmethod
    def _write_clipboard_text(text: str) -> None:
        from gi.repository import Gtk, Gdk
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(text, -1)
        clip.store()

    @staticmethod
    def set_text(text: str) -> None:
        """Set plain text to CLIPBOARD. Must be called from GTK main thread."""
        started_at = now()
        ClipboardManager._write_clipboard_text(text)
        log_duration(logger, "clipboard_text_set", started_at, chars=len(text))

    @staticmethod
    def set_path(filepath: str) -> None:
        """Set file path text to CLIPBOARD. Must be called from GTK main thread."""
        started_at = now()
        ClipboardManager._write_clipboard_text(filepath)
        log_duration(logger, "clipboard_path_set", started_at, path=filepath)

    @staticmethod
    def set_path_async(filepath: str) -> None:
        """Thread-safe: schedules set_path on GTK main thread via GLib.idle_add."""
        from gi.repository import GLib
        GLib.idle_add(ClipboardManager.set_path, filepath)
