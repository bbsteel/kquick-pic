"""Floating text editor must stay inside the overlay window near edges.

Regression: the editor was measured with get_preferred_size() while still
hidden. GTK reports 0x0 for hidden widgets, so the right/bottom clamp was a
no-op and the confirm/cancel buttons landed off-screen.
"""

from types import SimpleNamespace

from kuick_pic import area_selector
from kuick_pic.area_selector import AreaSelector


class FakeEditor:
    """Mimics GTK: hidden widgets measure as 0x0."""

    WIDTH = 255
    HEIGHT = 127

    def __init__(self):
        self.visible = False
        self.measured_while_hidden = False

    def show_all(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def get_preferred_size(self):
        if not self.visible:
            self.measured_while_hidden = True
            zero = SimpleNamespace(width=0, height=0)
            return zero, zero
        return (
            SimpleNamespace(width=self.WIDTH, height=self.HEIGHT),
            SimpleNamespace(width=self.WIDTH, height=self.HEIGHT),
        )


class FakeEditorBox:
    def __init__(self):
        self.size_request = None

    def set_size_request(self, w, h):
        self.size_request = (w, h)


class FakeContainer:
    def __init__(self):
        self.moves: list[tuple[object, int, int]] = []

    def move(self, widget, x, y):
        self.moves.append((widget, x, y))


class FakeWindow:
    width = 1280
    height = 800

    def get_allocated_width(self):
        return self.width

    def get_allocated_height(self):
        return self.height


class FakeBuffer:
    def set_text(self, text):
        self.text = text


class FakeTextView:
    def grab_focus(self):
        pass


class FakeDrawing:
    def queue_draw(self):
        pass


def _make_selector():
    selector = object.__new__(AreaSelector)
    selector._selection_rect = (0, 0, 1280, 800)
    selector._text_buffer = FakeBuffer()
    selector._text_view = FakeTextView()
    selector._text_editor = FakeEditor()
    selector._text_editor_box = FakeEditorBox()
    selector._container = FakeContainer()
    selector._window = FakeWindow()
    selector._drawing = FakeDrawing()
    selector._text_font_size = area_selector._DEFAULT_TEXT_FONT_SIZE
    selector._pending_text_rect = None
    selector._apply_text_font_size = lambda *a, **k: None
    return selector


def test_editor_is_shown_before_measuring():
    selector = _make_selector()
    selector._show_text_entry((100, 100, 220, 40))
    assert not selector._text_editor.measured_while_hidden


def test_editor_clamped_inside_right_edge():
    selector = _make_selector()
    # Click near the right edge of the selection/screen.
    selector._show_text_entry((1200, 100, 80, 40))
    _, x, _ = selector._container.moves[-1]
    assert x + FakeEditor.WIDTH <= FakeWindow.width


def test_editor_clamped_inside_bottom_edge():
    selector = _make_selector()
    selector._show_text_entry((100, 780, 220, 20))
    _, _, y = selector._container.moves[-1]
    assert y + FakeEditor.HEIGHT <= FakeWindow.height


def test_editor_anchors_at_click_when_room():
    selector = _make_selector()
    selector._show_text_entry((100, 100, 220, 40))
    _, x, y = selector._container.moves[-1]
    assert (x, y) == (100, 100)
