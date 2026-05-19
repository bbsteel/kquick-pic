import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AreaSelector:
    """GTK3 fullscreen overlay for selecting a screen region.

    Architecture:
      Gtk.Overlay
        ├── Gtk.Image (screenshot background, static, never redrawn)
        └── Gtk.DrawingArea (transparent overlay for dim mask + selection rect)

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

    def run(self) -> tuple[int, int, int, int] | None:
        import tempfile
        import mss

        # Take full screenshot for background
        screenshot_path = Path(tempfile.mktemp(suffix=".png"))
        with mss.mss() as sct:
            sct.shot(output=str(screenshot_path), mon=0)

        pixbuf = self._GdkPixbuf.Pixbuf.new_from_file(str(screenshot_path))
        screenshot_path.unlink()

        # Build window
        win = self._Gtk.Window(type=self._Gtk.WindowType.POPUP)
        win.set_default_size(pixbuf.get_width(), pixbuf.get_height())

        overlay = self._Gtk.Overlay()
        win.add(overlay)

        # Layer 1: static screenshot background
        bg_image = self._Gtk.Image.new_from_pixbuf(pixbuf)
        overlay.add(bg_image)

        # Layer 2: transparent overlay for dim mask + selection rect
        drawing = self._Gtk.DrawingArea()
        drawing.set_halign(self._Gtk.Align.FILL)
        drawing.set_valign(self._Gtk.Align.FILL)
        drawing.connect("draw", self._on_draw_overlay)
        overlay.add_overlay(drawing)

        win.add_events(
            self._Gdk.EventMask.BUTTON_PRESS_MASK
            | self._Gdk.EventMask.BUTTON_RELEASE_MASK
            | self._Gdk.EventMask.POINTER_MOTION_MASK
            | self._Gdk.EventMask.KEY_PRESS_MASK
        )

        win.connect("button-press-event", self._on_button_press)
        win.connect("button-release-event", self._on_button_release)
        win.connect("motion-notify-event", self._on_motion)
        win.connect("key-press-event", self._on_key_press)

        win.fullscreen()
        win.show_all()

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
        return self._result

    def destroy(self) -> None:
        pass

    def _on_draw_overlay(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()

        # Semi-transparent dark mask over entire screen
        cr.set_source_rgba(0, 0, 0, 0.45)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        if not self._dragging:
            return

        x = min(self._start_x, self._end_x)
        y = min(self._start_y, self._end_y)
        rw = abs(self._end_x - self._start_x)
        rh = abs(self._end_y - self._start_y)

        if rw < 2 or rh < 2:
            return

        # Cut out selection region (clear operator to show background through)
        cr.set_operator(1)  # CAIRO_OPERATOR_CLEAR
        cr.rectangle(x, y, rw, rh)
        cr.fill()
        cr.set_operator(2)  # CAIRO_OPERATOR_OVER

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
            self._Gtk.main_quit()

    def _on_motion(self, widget, event):
        if self._dragging:
            old_x, old_y = self._end_x, self._end_y
            self._end_x = event.x
            self._end_y = event.y
            # Only redraw if position changed enough to avoid jitter
            if abs(old_x - self._end_x) > 0.5 or abs(old_y - self._end_y) > 0.5:
                widget.get_toplevel().get_child().get_children()[-1].queue_draw()

    def _on_key_press(self, widget, event):
        from gi.repository import Gdk
        if event.keyval == Gdk.KEY_Escape:
            self._Gtk.main_quit()
