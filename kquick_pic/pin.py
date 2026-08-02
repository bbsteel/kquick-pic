"""Pinned screenshot floating windows.

After capture, a screenshot can be "pinned" as an always-on-top undecorated
window that sits above other apps. Each pin:
- shows a vivid border so it is easy to spot
- can be dragged with the left mouse button
- right-click opens a menu with Close
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from kquick_pic.i18n import t
from kquick_pic.timing import log_event

logger = logging.getLogger(__name__)

# Outer border thickness in pixels — intentionally bold so pins stand out.
# Built with nested EventBoxes + widget margins (reliable on GTK3;
# CSS padding alone is flaky for undecorated floating windows).
OUTER_RING_PX = 1   # white outer ring
MAIN_BORDER_PX = 3  # blue main border
BORDER_PX = OUTER_RING_PX + MAIN_BORDER_PX

PIN_CSS = b"""
    .qp-pin-window {
        background-color: #ffffff;
    }
    .qp-pin-border-outer {
        background-color: #ffffff;
    }
    .qp-pin-border-main {
        background-color: #2563eb;
    }
    .qp-pin-image {
        background-color: #000000;
    }
"""

_css_installed = False


def _ensure_pin_css(Gtk, Gdk) -> None:
    """Install pin CSS once for the process (class names are qp-pin-*)."""
    global _css_installed
    if _css_installed:
        return
    screen = Gdk.Screen.get_default()
    if screen is None:
        return
    css = Gtk.CssProvider()
    css.load_from_data(PIN_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        screen,
        css,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _css_installed = True


class PinnedScreenshot:
    """One floating always-on-top screenshot window."""

    def __init__(
        self,
        image_path: Path,
        *,
        position: tuple[int, int] | None = None,
        on_closed: Callable[["PinnedScreenshot"], None] | None = None,
    ):
        import gi

        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gtk, Gdk, GdkPixbuf

        self._Gtk = Gtk
        self._Gdk = Gdk
        self._GdkPixbuf = GdkPixbuf
        self._image_path = Path(image_path)
        self._position = position
        self._on_closed = on_closed
        self._window = None
        self._menu = None
        self._closed = False

    @property
    def image_path(self) -> Path:
        return self._image_path

    @property
    def is_open(self) -> bool:
        return not self._closed and self._window is not None

    def show(self) -> None:
        """Build and map the pin window. Must run on the GTK main thread."""
        if self._closed:
            return
        try:
            pixbuf = self._GdkPixbuf.Pixbuf.new_from_file(str(self._image_path))
        except Exception:
            logger.exception("Failed to load image for pin: %s", self._image_path)
            self._closed = True
            return

        _ensure_pin_css(self._Gtk, self._Gdk)

        win = self._Gtk.Window(type=self._Gtk.WindowType.TOPLEVEL)
        win.set_decorated(False)
        win.set_keep_above(True)
        win.set_accept_focus(True)
        win.set_skip_taskbar_hint(True)
        win.set_skip_pager_hint(True)
        win.set_resizable(False)
        # UTILITY keeps it floating without acting like a full app window.
        win.set_type_hint(self._Gdk.WindowTypeHint.UTILITY)
        win.set_title(f"KQuick Pic — {self._image_path.name}")
        win.get_style_context().add_class("qp-pin-window")

        # Double ring: white outer + blue main via margins on nested EventBoxes.
        border_outer = self._Gtk.EventBox()
        border_outer.set_visible_window(True)
        border_outer.get_style_context().add_class("qp-pin-border-outer")

        border_main = self._Gtk.EventBox()
        border_main.set_visible_window(True)
        border_main.get_style_context().add_class("qp-pin-border-main")
        for edge in ("top", "bottom", "start", "end"):
            getattr(border_main, f"set_margin_{edge}")(OUTER_RING_PX)

        image = self._Gtk.Image.new_from_pixbuf(pixbuf)
        image.get_style_context().add_class("qp-pin-image")
        for edge in ("top", "bottom", "start", "end"):
            getattr(image, f"set_margin_{edge}")(MAIN_BORDER_PX)

        border_main.add(image)
        border_outer.add(border_main)
        win.add(border_outer)

        # Event masks on the outer event box for drag + context menu.
        border_outer.add_events(
            self._Gdk.EventMask.BUTTON_PRESS_MASK
            | self._Gdk.EventMask.BUTTON_RELEASE_MASK
            | self._Gdk.EventMask.POINTER_MOTION_MASK
        )
        border_outer.connect("button-press-event", self._on_button_press)
        win.connect("delete-event", self._on_delete)
        win.connect("destroy", self._on_destroy)

        self._menu = self._build_menu()
        self._window = win

        # Realize before move so KWin accepts the initial geometry.
        border_outer.show_all()
        win.realize()

        img_w = pixbuf.get_width()
        img_h = pixbuf.get_height()
        total_w = img_w + BORDER_PX * 2
        total_h = img_h + BORDER_PX * 2
        win.resize(total_w, total_h)

        if self._position is not None:
            x, y = self._position
            # Offset by border so the image content sits on the capture rect.
            win.move(x - BORDER_PX, y - BORDER_PX)
        else:
            win.set_position(self._Gtk.WindowPosition.CENTER)

        win.show_all()
        log_event(
            logger,
            "pin_shown",
            path=str(self._image_path),
            width=img_w,
            height=img_h,
            position=self._position,
        )

    def close(self) -> None:
        """Close and destroy this pin (idempotent)."""
        if self._closed:
            return
        self._closed = True
        win = self._window
        self._window = None
        if win is not None:
            try:
                win.destroy()
            except Exception:
                logger.debug("Pin window destroy failed", exc_info=True)
        self._menu = None
        log_event(logger, "pin_closed", path=str(self._image_path))
        if self._on_closed is not None:
            try:
                self._on_closed(self)
            except Exception:
                logger.debug("pin on_closed callback failed", exc_info=True)

    def _build_menu(self):
        menu = self._Gtk.Menu()
        close_item = self._Gtk.MenuItem(label=t("pin.close"))
        close_item.connect("activate", lambda *_: self.close())
        menu.append(close_item)
        menu.show_all()
        return menu

    def _on_button_press(self, widget, event) -> bool:
        if self._window is None:
            return False
        if event.button == 1:
            # Let the window manager handle move for undecorated windows.
            self._window.begin_move_drag(
                int(event.button),
                int(event.x_root),
                int(event.y_root),
                int(event.time),
            )
            return True
        if event.button == 3:
            menu = self._menu
            if menu is None:
                menu = self._build_menu()
                self._menu = menu
            # Rebuild label in case language changed while pin is open.
            children = menu.get_children()
            if children:
                children[0].set_label(t("pin.close"))
            menu.popup_at_pointer(event)
            return True
        return False

    def _on_delete(self, widget, event) -> bool:
        self.close()
        return True

    def _on_destroy(self, widget) -> None:
        if not self._closed:
            self._closed = True
            self._window = None
            self._menu = None
            log_event(logger, "pin_closed", path=str(self._image_path), reason="destroy")
            if self._on_closed is not None:
                try:
                    self._on_closed(self)
                except Exception:
                    logger.debug("pin on_closed callback failed", exc_info=True)


class PinManager:
    """Tracks open pins; safe to call from the GTK main thread only."""

    def __init__(self) -> None:
        self._pins: list[PinnedScreenshot] = []

    @property
    def count(self) -> int:
        return len(self._pins)

    def pin(
        self,
        image_path: Path,
        *,
        position: tuple[int, int] | None = None,
    ) -> PinnedScreenshot | None:
        """Show a new pin for *image_path*. Returns the pin, or None on failure."""
        pin = PinnedScreenshot(
            image_path,
            position=position,
            on_closed=self._on_pin_closed,
        )
        pin.show()
        if not pin.is_open:
            # show() failed (e.g. bad image)
            return None
        self._pins.append(pin)
        log_event(logger, "pin_manager_added", count=len(self._pins), path=str(image_path))
        return pin

    def close_all(self) -> None:
        for pin in list(self._pins):
            pin.close()
        self._pins.clear()

    def _on_pin_closed(self, pin: PinnedScreenshot) -> None:
        try:
            self._pins.remove(pin)
        except ValueError:
            pass
        log_event(logger, "pin_manager_removed", count=len(self._pins))
