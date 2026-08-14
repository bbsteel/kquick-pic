import inspect

from kquick_pic.area_selector import AreaSelector


class FakeWindow:
    def __init__(self):
        self.calls = []

    def unfullscreen(self):
        self.calls.append("unfullscreen")

    def hide(self):
        self.calls.append("hide")

    def resize(self, width, height):
        self.calls.append(("resize", width, height))

    def move(self, x, y):
        self.calls.append(("move", x, y))

    def show_all(self):
        self.calls.append("show_all")

    def fullscreen(self):
        self.calls.append("fullscreen")

    def get_window(self):
        return None


class FakeImage:
    def __init__(self):
        self.cleared = False

    def clear(self):
        self.cleared = True


class FakeGtk:
    def __init__(self):
        self.iterations = 0

    def events_pending(self):
        return self.iterations == 0

    def main_iteration(self):
        self.iterations += 1


class FakeGdk:
    def __init__(self):
        self.flushed = False

    def flush(self):
        self.flushed = True


def test_overlay_cleanup_hides_window_without_fullscreen_transition():
    selector = object.__new__(AreaSelector)
    selector._window = FakeWindow()
    selector._background_image_widget = FakeImage()
    selector._background_pixbuf = object()
    selector._Gtk = FakeGtk()
    selector._Gdk = FakeGdk()

    selector._hide_overlay_after_run()

    assert selector._window.calls == ["hide"]
    assert "unfullscreen" not in selector._window.calls
    assert selector._Gtk.iterations == 1
    assert selector._Gdk.flushed is True


def test_overlay_cleanup_keeps_background_image_until_next_capture_replaces_it():
    selector = object.__new__(AreaSelector)
    selector._window = FakeWindow()
    selector._background_image_widget = FakeImage()
    selector._background_pixbuf = object()
    selector._Gtk = FakeGtk()
    selector._Gdk = FakeGdk()

    selector._hide_overlay_after_run()

    assert selector._background_image_widget.cleared is False
    assert selector._background_pixbuf is None


class FakeDrawing:
    def grab_focus(self):
        pass


class FakeGLib:
    def idle_add(self, callback):
        return 1


def test_show_overlay_covers_screen_without_entering_fullscreen():
    selector = object.__new__(AreaSelector)
    selector._window = FakeWindow()
    selector._drawing = FakeDrawing()
    selector._GLib = FakeGLib()
    selector._hide_selection_controls = lambda: None

    selector._show_overlay_covering_screen(3840, 2160)

    assert "fullscreen" not in selector._window.calls
    assert ("resize", 3840, 2160) in selector._window.calls
    assert ("move", 0, 0) in selector._window.calls
    assert "show_all" in selector._window.calls


def test_selector_run_does_not_request_wm_fullscreen():
    source = inspect.getsource(AreaSelector.run)
    assert "fullscreen(" not in source
