from types import SimpleNamespace

from kuick_pic.area_selector import AreaSelector
from kuick_pic.annotations import RectangleAnnotation


class FakeDrawing:
    def __init__(self):
        self.queued = 0
        self.focused = False

    def queue_draw(self):
        self.queued += 1

    def grab_focus(self):
        self.focused = True


class FakeWidget:
    def __init__(self):
        self.hidden = False
        self.shown = False

    def hide(self):
        self.hidden = True

    def show_all(self):
        self.shown = True


class FakeButton:
    def __init__(self):
        self.active = True

    def get_active(self):
        return self.active

    def set_active(self, active):
        self.active = active


def _event(x, y, button=1):
    return SimpleNamespace(button=button, x=x, y=y, type="button-press")


def _make_selector():
    selector = object.__new__(AreaSelector)
    selector._Gdk = SimpleNamespace(EventType=SimpleNamespace(_2BUTTON_PRESS="double"))
    selector._drawing = FakeDrawing()
    selector._window = None
    selector._container = None
    selector._background_pixbuf = None
    selector._selection_rect = (100, 100, 80, 60)
    selector._result = selector._selection_rect
    selector._active_tool = None
    selector._pending_text_rect = None
    selector._gesture_kind = None
    selector._dragging = False
    selector._selection_drag_origin = None
    selector._start_x = 0
    selector._start_y = 0
    selector._end_x = 0
    selector._end_y = 0
    selector._annotations = [
        RectangleAnnotation(rect=(5, 5, 20, 20), color=(255, 0, 0)),
    ]
    selector._toolbar_frame = FakeWidget()
    selector._color_palette_frame = FakeWidget()
    selector._mosaic_palette_frame = FakeWidget()
    selector._text_editor = FakeWidget()
    selector._box_button = FakeButton()
    selector._line_button = FakeButton()
    selector._arrow_button = FakeButton()
    selector._number_button = FakeButton()
    selector._mosaic_button = FakeButton()
    selector._text_button = FakeButton()
    selector._next_number_stamp_value = 3
    return selector


def test_left_press_outside_existing_selection_starts_reselect_drag():
    selector = _make_selector()

    handled = selector._on_button_press(None, _event(20, 30))

    assert handled is True
    assert selector._dragging is True
    assert selector._gesture_kind == "select"
    assert selector._start_x == 20
    assert selector._start_y == 30
    assert selector._end_x == 20
    assert selector._end_y == 30
    assert selector._toolbar_frame.hidden is True
    assert selector._color_palette_frame.hidden is True
    assert selector._text_editor.hidden is True
    assert selector._box_button.active is False
    assert selector._text_button.active is False
    assert selector._line_button.active is False
    assert selector._arrow_button.active is False
    assert selector._number_button.active is False


def test_successful_reselect_replaces_selection_and_clears_old_annotations():
    selector = _make_selector()
    selector._on_button_press(None, _event(20, 30))

    selector._on_button_release(None, SimpleNamespace(button=1, x=220, y=180))

    assert selector._selection_rect == (20, 30, 200, 150)
    assert selector._result == (20, 30, 200, 150)
    assert selector._annotations == []
    assert selector._next_number_stamp_value == 1
    assert selector._toolbar_frame.shown is True


def test_reselect_drag_draws_new_drag_rect_instead_of_old_selection():
    selector = _make_selector()
    selector._on_button_press(None, _event(20, 30))
    selector._end_x = 220
    selector._end_y = 180

    assert selector._active_selection_rect_for_draw() == (20, 30, 200, 150)
