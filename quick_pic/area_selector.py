from dataclasses import dataclass
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SelectionResult:
    rect: tuple[int, int, int, int]
    screenshot_path: Path


class AreaSelector:
    """GTK3 fullscreen overlay for selecting a screen region.

    Press Escape or right-click to cancel. Left-drag to select.
    """

    def __init__(self):
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk, Gdk, GdkPixbuf

        self._Gtk = Gtk
        self._Gdk = Gdk
        self._GdkPixbuf = GdkPixbuf
        self._result: tuple[int, int, int, int] | None = None
        self._start_x = 0.0
        self._start_y = 0.0
        self._end_x = 0.0
        self._end_y = 0.0
        self._dragging = False
        self._screenshot_path: Path | None = None
        self._background_pixbuf = None
        self._drawing = None

    def run(self) -> SelectionResult | None:
        import tempfile
        import mss

        # Take full screenshot for background
        screenshot_path = Path(tempfile.mktemp(suffix=".png"))
        self._screenshot_path = screenshot_path
        with mss.mss() as sct:
            sct.shot(output=str(screenshot_path), mon=0)

        pixbuf = self._GdkPixbuf.Pixbuf.new_from_file(str(screenshot_path))
        self._background_pixbuf = pixbuf

        # Build window
        win = self._Gtk.Window(type=self._Gtk.WindowType.POPUP)
        win.set_default_size(pixbuf.get_width(), pixbuf.get_height())

        drawing = self._Gtk.DrawingArea()
        self._drawing = drawing
        drawing.set_can_focus(True)
        drawing.connect("draw", self._on_draw_overlay)
        drawing.add_events(
            self._Gdk.EventMask.BUTTON_PRESS_MASK
            | self._Gdk.EventMask.BUTTON_RELEASE_MASK
            | self._Gdk.EventMask.POINTER_MOTION_MASK
            | self._Gdk.EventMask.KEY_PRESS_MASK
        )
        win.add(drawing)

        drawing.connect("button-press-event", self._on_button_press)
        drawing.connect("button-release-event", self._on_button_release)
        drawing.connect("motion-notify-event", self._on_motion)
        drawing.connect("key-press-event", self._on_key_press)

        win.fullscreen()
        win.show_all()
        drawing.grab_focus()

        # Grab input devices
        display = self._Gdk.Display.get_default()
        seat = display.get_default_seat()
        self._ptr_device = seat.get_pointer()
        self._kbd_device = seat.get_keyboard()

        self._ptr_device.grab(
            win.get_window(),
            self._Gdk.GrabOwnership.NONE,
            True,
            self._Gdk.EventMask.BUTTON_PRESS_MASK
            | self._Gdk.EventMask.BUTTON_RELEASE_MASK
            | self._Gdk.EventMask.POINTER_MOTION_MASK,
            None,
            self._Gdk.CURRENT_TIME,
        )
        if self._kbd_device:
            self._kbd_device.grab(
                win.get_window(),
                self._Gdk.GrabOwnership.NONE,
                True,
                self._Gdk.EventMask.KEY_PRESS_MASK | self._Gdk.EventMask.KEY_RELEASE_MASK,
                None,
                self._Gdk.CURRENT_TIME,
            )

        self._Gtk.main()

        if self._kbd_device:
            self._kbd_device.ungrab(self._Gdk.CURRENT_TIME)
        self._ptr_device.ungrab(self._Gdk.CURRENT_TIME)

        # Ensure the overlay is fully removed from screen before caller
        # (e.g. mss) captures the framebuffer again.
        win.hide()
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk as _Gtk, Gdk as _Gdk
        while _Gtk.events_pending():
            _Gtk.main_iteration()
        _Gdk.flush()
        win.destroy()
        if self._result is None:
            screenshot_path.unlink(missing_ok=True)
            self._screenshot_path = None
            return None
        return SelectionResult(rect=self._result, screenshot_path=screenshot_path)

    def destroy(self) -> None:
        pass

    def _on_draw_overlay(self, widget, cr):
        if self._background_pixbuf is not None:
            self._Gdk.cairo_set_source_pixbuf(cr, self._background_pixbuf, 0, 0)
            cr.paint()

        w = widget.get_allocated_width()
        h = widget.get_allocated_height()

        if not self._dragging:
            # Semi-transparent dark mask over entire screen
            cr.set_source_rgba(0, 0, 0, 0.45)
            cr.rectangle(0, 0, w, h)
            cr.fill()
            return

        x = min(self._start_x, self._end_x)
        y = min(self._start_y, self._end_y)
        rw = abs(self._end_x - self._start_x)
        rh = abs(self._end_y - self._start_y)

        if rw < 2 or rh < 2:
            return

        # Draw dim mask only outside the selected region so the screenshot
        # background remains fully visible inside the selection.
        cr.set_source_rgba(0, 0, 0, 0.45)
        cr.rectangle(0, 0, w, y)
        cr.fill()
        cr.rectangle(0, y, x, rh)
        cr.fill()
        cr.rectangle(x + rw, y, w - (x + rw), rh)
        cr.fill()
        cr.rectangle(0, y + rh, w, h - (y + rh))
        cr.fill()

        # White border around selection
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.set_line_width(2)
        cr.rectangle(x + 1, y + 1, rw - 2, rh - 2)
        cr.stroke()

        cr.set_line_width(1)
        cr.set_dash([4, 4], 0)

    def _on_button_press(self, widget, event):
        if event.button == 1:
            self._dragging = True
            self._start_x = event.x
            self._start_y = event.y
            self._end_x = event.x
            self._end_y = event.y
            widget.queue_draw()
        elif event.button == 3:
            self._Gtk.main_quit()

    def _on_button_release(self, widget, event):
        if event.button == 1 and self._dragging:
            self._dragging = False
            self._end_x = event.x
            self._end_y = event.y

            x = int(min(self._start_x, self._end_x))
            y = int(min(self._start_y, self._end_y))
            w = int(abs(self._end_x - self._start_x))
            h = int(abs(self._end_y - self._start_y))

            if w < 4 or h < 4:
                widget.queue_draw()
                return

            self._result = (x, y, w, h)
            widget.queue_draw()
            self._Gtk.main_quit()

    def _on_motion(self, widget, event):
        if self._dragging:
            old_x, old_y = self._end_x, self._end_y
            self._end_x = event.x
            self._end_y = event.y
            # Only redraw if position changed enough to avoid jitter
            if abs(old_x - self._end_x) > 0.5 or abs(old_y - self._end_y) > 0.5:
                widget.queue_draw()

    def _on_key_press(self, widget, event):
        from gi.repository import Gdk
        if event.keyval == Gdk.KEY_Escape:
            self._Gtk.main_quit()
