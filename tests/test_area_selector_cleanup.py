from kquick_pic.area_selector import AreaSelector


class FakeWindow:
    def __init__(self):
        self.calls = []

    def unfullscreen(self):
        self.calls.append("unfullscreen")

    def hide(self):
        self.calls.append("hide")


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


def test_overlay_cleanup_exits_fullscreen_before_hiding_window():
    selector = object.__new__(AreaSelector)
    selector._window = FakeWindow()
    selector._background_image_widget = FakeImage()
    selector._background_pixbuf = object()
    selector._Gtk = FakeGtk()
    selector._Gdk = FakeGdk()

    selector._hide_overlay_after_run()

    assert selector._window.calls == ["unfullscreen", "hide"]
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
