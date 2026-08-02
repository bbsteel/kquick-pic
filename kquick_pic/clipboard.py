import logging

from kquick_pic.timing import log_duration, now

logger = logging.getLogger(__name__)


class ClipboardManager:

    @staticmethod
    def set_path(filepath: str) -> None:
        """Set file path text to CLIPBOARD. Must be called from GTK main thread."""
        started_at = now()
        from gi.repository import Gtk, Gdk
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(filepath, -1)
        clip.store()
        log_duration(logger, "clipboard_path_set", started_at, path=filepath)

    @staticmethod
    def set_path_async(filepath: str) -> None:
        """Thread-safe: schedules set_path on GTK main thread via GLib.idle_add."""
        from gi.repository import GLib
        GLib.idle_add(ClipboardManager.set_path, filepath)
