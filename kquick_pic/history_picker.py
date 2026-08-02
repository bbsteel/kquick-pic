"""Compact popup picker for recent screenshots.

Designed to feel like a lightweight in-place popup, not an app window:
- small undecorated panel centered on the monitor under the mouse
- no fullscreen takeover, no translucent veil — solid opaque window
- thumb grid sized to content; hover only swaps highlight, never reflows
- cancels on focus-out / Esc so clicking anywhere else dismisses it
"""

from __future__ import annotations

import logging
from pathlib import Path

from kquick_pic.timing import log_event, now

logger = logging.getLogger(__name__)

THUMB_W = 220
THUMB_H = 140
GRID_COLS = 5
# Hover preview pops up next to the panel in its own borderless window.
PREVIEW_MAX_W = 1280
PREVIEW_MAX_H = 800
PREVIEW_GAP = 12

PANEL_CSS = b"""
    .qp-history-window {
        background-color: #1b222b;
        border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .qp-history-title {
        font-size: 13px;
        color: #e8edf2;
    }
    .qp-history-thumb {
        border: 2px solid transparent;
        border-radius: 6px;
        background-color: #2a323c;
        padding: 3px;
    }
    .qp-history-thumb.hover {
        border-color: #3b82f6;
        background-color: #1e3a5f;
    }
    .qp-history-thumb-label {
        font-size: 11px;
        color: #9aa8b5;
    }
    .qp-history-hint {
        font-size: 11px;
        color: #7c8894;
    }
    .qp-history-empty {
        font-size: 13px;
        color: #9aa8b5;
    }
    .qp-history-preview {
        background-color: #0a0d11;
        border: 1px solid rgba(255, 255, 255, 0.12);
    }
"""


class HistoryPicker:
    """Show recent screenshot thumbnails; click copies path, Esc/outside cancels.

    Must run on the GTK main thread. Uses a nested Gtk.main() like AreaSelector.
    """

    def __init__(self):
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

        self._Gtk = Gtk
        self._Gdk = Gdk
        self._GdkPixbuf = GdkPixbuf
        self._GLib = GLib
        self._result: Path | None = None
        self._window = None
        self._preview_window = None
        self._preview_image = None
        self._paths: list[Path] = []
        self._thumb_boxes: dict[str, object] = {}
        self._thumb_pixbufs: dict[str, object] = {}
        self._preview_pixbufs: dict[str, object] = {}
        self._hovered: Path | None = None
        self._in_run = False
        self._css_provider = None

    def run(self, paths: list[Path]) -> Path | None:
        """Show picker for *paths* (newest first). Returns selected path or None."""
        self._result = None
        self._paths = list(paths)
        self._hovered = None
        self._thumb_boxes.clear()
        self._thumb_pixbufs.clear()
        log_event(logger, "history_picker_started", count=len(self._paths))
        started = now()

        self._preload_images()
        self._setup_window()
        assert self._window is not None
        self._position_window()
        self._window.show()

        self._in_run = True
        try:
            self._Gtk.main()
        finally:
            self._in_run = False
            self._teardown_window()

        log_event(
            logger,
            "history_picker_finished",
            result="selected" if self._result else "cancelled",
            path=str(self._result) if self._result else None,
            elapsed_ms=int((now() - started) * 1000),
        )
        return self._result

    def destroy(self) -> None:
        self._teardown_window()

    def _teardown_window(self) -> None:
        self._hide_preview()
        if self._preview_window is not None:
            self._preview_window.destroy()
            self._preview_window = None
            self._preview_image = None
        if self._window is not None:
            self._window.hide()
            while self._Gtk.events_pending():
                self._Gtk.main_iteration()
            self._window.destroy()
            self._window = None
        if self._css_provider is not None:
            try:
                screen = self._Gdk.Screen.get_default()
                self._Gtk.StyleContext.remove_provider_for_screen(
                    screen, self._css_provider
                )
            except Exception:
                pass
            self._css_provider = None
        self._thumb_boxes.clear()
        self._thumb_pixbufs.clear()
        self._preview_pixbufs.clear()
        self._hovered = None

    def _preload_images(self) -> None:
        for path in self._paths:
            key = str(path)
            try:
                self._thumb_pixbufs[key] = self._GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    key, THUMB_W, THUMB_H, True
                )
            except Exception:
                logger.warning("Failed to load thumbnail %s", path, exc_info=True)

    def _position_window(self) -> None:
        """Center on the monitor that currently holds the mouse pointer.

        KWin ignores move requests on unmapped windows, so the window must be
        realized (GdkWindow created) before move() — then the position is
        applied as the initial geometry when show() maps it.
        """
        win = self._window
        child = win.get_child()
        if child is not None:
            child.show_all()
        win.realize()
        try:
            display = self._Gdk.Display.get_default()
            seat = display.get_default_seat()
            pointer = seat.get_pointer()
            _screen, x, y = pointer.get_position()
            monitor = display.get_monitor_at_point(x, y)
            geo = monitor.get_geometry()
            _minimum, natural = win.get_preferred_size()
            wx = geo.x + max(0, (geo.width - natural.width) // 2)
            wy = geo.y + max(0, (geo.height - natural.height) * 2 // 3)
            win.move(wx, wy)
        except Exception:
            logger.debug("Pointer-based placement failed, centering", exc_info=True)
            win.set_position(self._Gtk.WindowPosition.CENTER)

    def _setup_window(self) -> None:
        from kquick_pic.i18n import t

        win = self._Gtk.Window(type=self._Gtk.WindowType.TOPLEVEL)
        win.set_decorated(False)
        win.set_keep_above(True)
        win.set_accept_focus(True)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_type_hint(self._Gdk.WindowTypeHint.DIALOG)
        win.set_resizable(False)
        # Opaque solid window — no ARGB / app_paintable.
        win.get_style_context().add_class("qp-history-window")

        screen = win.get_screen()
        css = self._Gtk.CssProvider()
        css.load_from_data(PANEL_CSS)
        self._css_provider = css
        self._Gtk.StyleContext.add_provider_for_screen(
            screen,
            css,
            self._Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        panel = self._Gtk.Box(orientation=self._Gtk.Orientation.VERTICAL, spacing=8)
        panel.set_margin_top(12)
        panel.set_margin_bottom(12)
        panel.set_margin_start(14)
        panel.set_margin_end(14)

        title = self._Gtk.Label(label=t("history.title"))
        title.get_style_context().add_class("qp-history-title")
        title.set_halign(self._Gtk.Align.START)
        panel.pack_start(title, False, False, 0)

        if not self._paths:
            empty = self._Gtk.Label(label=t("history.empty"))
            empty.get_style_context().add_class("qp-history-empty")
            empty.set_halign(self._Gtk.Align.CENTER)
            panel.pack_start(empty, False, False, 8)
        else:
            grid = self._Gtk.Grid()
            grid.set_column_spacing(10)
            grid.set_row_spacing(10)
            grid.set_halign(self._Gtk.Align.CENTER)
            for idx, path in enumerate(self._paths):
                col = idx % GRID_COLS
                row = idx // GRID_COLS
                grid.attach(self._make_thumb(path), col, row, 1, 1)
            panel.pack_start(grid, False, False, 0)

        hint = self._Gtk.Label(label=t("history.hint"))
        hint.get_style_context().add_class("qp-history-hint")
        hint.set_halign(self._Gtk.Align.CENTER)
        panel.pack_start(hint, False, False, 0)

        win.add(panel)

        win.connect("key-press-event", self._on_key_press)
        win.connect("delete-event", self._on_delete)
        win.connect("focus-out-event", self._on_focus_out)
        win.connect("map-event", self._on_map)
        self._window = win

    def _on_map(self, widget, event) -> bool:
        widget.present()
        return False

    def _make_thumb(self, path: Path):
        frame = self._Gtk.EventBox()
        frame.set_visible_window(True)
        frame.get_style_context().add_class("qp-history-thumb")
        frame.add_events(
            self._Gdk.EventMask.ENTER_NOTIFY_MASK
            | self._Gdk.EventMask.LEAVE_NOTIFY_MASK
            | self._Gdk.EventMask.BUTTON_PRESS_MASK
        )
        key = str(path)
        cell = self._Gtk.Box(orientation=self._Gtk.Orientation.VERTICAL, spacing=4)
        pixbuf = self._thumb_pixbufs.get(key)
        if pixbuf is not None:
            image = self._Gtk.Image.new_from_pixbuf(pixbuf)
        else:
            image = self._Gtk.Label(label=path.name[-18:])
        image.set_size_request(THUMB_W, THUMB_H)
        image.set_halign(self._Gtk.Align.CENTER)
        image.set_valign(self._Gtk.Align.CENTER)
        cell.pack_start(image, False, False, 0)
        label = self._Gtk.Label(label=path.name)
        label.get_style_context().add_class("qp-history-thumb-label")
        label.set_ellipsize(3)  # Pango.EllipsizeMode.END
        label.set_max_width_chars(26)
        cell.pack_start(label, False, False, 0)
        frame.add(cell)
        frame.connect("enter-notify-event", self._on_thumb_enter, path)
        frame.connect("leave-notify-event", self._on_thumb_leave, path)
        frame.connect("button-press-event", self._on_thumb_click, path)
        frame.set_tooltip_text(str(path))
        self._thumb_boxes[key] = frame
        return frame

    def _ensure_preview_window(self) -> None:
        if self._preview_window is not None:
            return
        win = self._Gtk.Window(type=self._Gtk.WindowType.TOPLEVEL)
        win.set_decorated(False)
        win.set_keep_above(True)
        win.set_accept_focus(False)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_type_hint(self._Gdk.WindowTypeHint.NOTIFICATION)
        win.set_resizable(False)
        win.get_style_context().add_class("qp-history-preview")
        image = self._Gtk.Image()
        image.set_margin_top(4)
        image.set_margin_bottom(4)
        image.set_margin_start(4)
        image.set_margin_end(4)
        win.add(image)
        self._preview_window = win
        self._preview_image = image

    def _preview_pixbuf_for(self, path: Path):
        key = str(path)
        pixbuf = self._preview_pixbufs.get(key)
        if pixbuf is None and key not in self._preview_pixbufs:
            try:
                pixbuf = self._GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    key, PREVIEW_MAX_W, PREVIEW_MAX_H, True
                )
            except Exception:
                logger.warning("Failed to load preview %s", path, exc_info=True)
                pixbuf = None
            self._preview_pixbufs[key] = pixbuf
        return pixbuf

    def _show_preview(self, path: Path) -> None:
        pixbuf = self._preview_pixbuf_for(path)
        if pixbuf is None or self._window is None:
            return
        self._ensure_preview_window()
        win = self._preview_window
        image = self._preview_image
        image.set_from_pixbuf(pixbuf)
        image.show()
        win.realize()
        pw = pixbuf.get_width() + 10
        ph = pixbuf.get_height() + 10
        win.resize(pw, ph)
        try:
            panel_gdk = self._window.get_window()
            px, py = panel_gdk.get_origin()[-2:]
            panel_w, panel_h = self._window.get_size()
            display = self._Gdk.Display.get_default()
            monitor = display.get_monitor_at_point(px, py)
            geo = monitor.get_geometry()
            x = px + (panel_w - pw) // 2
            x = max(geo.x + 8, min(x, geo.x + geo.width - pw - 8))
            # Prefer the side of the panel with more room, clamped on-screen.
            above = py - geo.y
            below = geo.y + geo.height - (py + panel_h)
            if above >= below:
                y = py - ph - PREVIEW_GAP
            else:
                y = py + panel_h + PREVIEW_GAP
            y = max(geo.y + 8, min(y, geo.y + geo.height - ph - 8))
            win.move(x, y)
        except Exception:
            logger.debug("Preview placement failed", exc_info=True)
        win.show()

    def _hide_preview(self) -> None:
        if self._preview_window is not None:
            self._preview_window.hide()

    def _on_thumb_enter(self, widget, event, path: Path) -> bool:
        if event.detail == self._Gdk.NotifyType.INFERIOR:
            return False
        if self._hovered is not None and self._hovered != path:
            prev = self._thumb_boxes.get(str(self._hovered))
            if prev is not None:
                prev.get_style_context().remove_class("hover")
        widget.get_style_context().add_class("hover")
        self._hovered = path
        self._show_preview(path)
        return False

    def _on_thumb_leave(self, widget, event, path: Path) -> bool:
        if event.detail == self._Gdk.NotifyType.INFERIOR:
            return False
        if self._hovered == path:
            widget.get_style_context().remove_class("hover")
            self._hide_preview()
        return False

    def _on_thumb_click(self, widget, event, path: Path) -> bool:
        if event.button != 1:
            return False
        self._result = path
        self._quit_loop()
        return True

    def _on_focus_out(self, widget, event) -> bool:
        # Clicking anywhere outside dismisses the picker. Delay the check so
        # transient focus shifts (e.g. tooltips mapping) don't cancel.
        self._GLib.timeout_add(150, self._cancel_if_unfocused)
        return False

    def _cancel_if_unfocused(self) -> bool:
        if self._in_run and self._window is not None and not self._window.is_active():
            self._result = None
            self._quit_loop()
        return False

    def _on_key_press(self, widget, event) -> bool:
        if event.keyval in (self._Gdk.KEY_Escape, self._Gdk.KEY_q):
            self._result = None
            self._quit_loop()
            return True
        if self._Gdk.KEY_1 <= event.keyval <= self._Gdk.KEY_9:
            idx = event.keyval - self._Gdk.KEY_1
            if 0 <= idx < len(self._paths):
                self._result = self._paths[idx]
                self._quit_loop()
                return True
        return False

    def _on_delete(self, widget, event) -> bool:
        self._result = None
        self._quit_loop()
        return True

    def _quit_loop(self) -> None:
        if self._in_run:
            self._Gtk.main_quit()
