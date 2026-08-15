"""Selection frame edge/corner resize and move."""

from types import SimpleNamespace

from kuick_pic.area_selector import AreaSelector
from kuick_pic.annotations import RectangleAnnotation


class FakeDrawing:
    def __init__(self):
        self.queued = 0
        self.areas: list[tuple[int, int, int, int]] = []

    def queue_draw(self):
        self.queued += 1

    def queue_draw_area(self, x, y, w, h):
        self.areas.append((x, y, w, h))

    def grab_focus(self):
        pass


class FakeWidget:
    def __init__(self):
        self.hidden = False
        self.shown = False
        self.moves: list[tuple[int, int]] = []

    def hide(self):
        self.hidden = True

    def show_all(self):
        self.shown = True

    def get_preferred_size(self):
        return SimpleNamespace(width=0, height=0), SimpleNamespace(width=200, height=48)


class FakeContainer:
    def __init__(self):
        self.moves: list[tuple[object, int, int]] = []

    def move(self, widget, x, y):
        self.moves.append((widget, x, y))


class FakePixbuf:
    def get_width(self):
        return 1920

    def get_height(self):
        return 1080


class FakeButton:
    def __init__(self):
        self.active = False

    def get_active(self):
        return self.active

    def set_active(self, active):
        self.active = active


def _event(x, y, button=1, etype="button-press"):
    return SimpleNamespace(button=button, x=x, y=y, type=etype)


def _make_selector(rect=(100, 100, 200, 150)):
    selector = object.__new__(AreaSelector)
    selector._Gdk = SimpleNamespace(EventType=SimpleNamespace(_2BUTTON_PRESS="double"))
    selector._GLib = SimpleNamespace(timeout_add=lambda *_a, **_k: 0)
    selector._drawing = FakeDrawing()
    selector._window = None
    selector._container = FakeContainer()
    selector._background_pixbuf = FakePixbuf()
    selector._selection_rect = rect
    selector._result = rect
    selector._active_tool = None
    selector._pending_text_rect = None
    selector._gesture_kind = None
    selector._dragging = False
    selector._selection_drag_origin = None
    selector._start_x = 0.0
    selector._start_y = 0.0
    selector._end_x = 0.0
    selector._end_y = 0.0
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
    selector._motion_pending = False
    selector._motion_pending_event = None
    selector._last_motion_time = 0.0
    selector._in_run = True
    # Avoid real Gdk cursor path in unit tests.
    selector._set_window_cursor = lambda *_a, **_k: None
    selector._apply_selection_cursor = lambda handle: setattr(
        selector, "_last_cursor_handle", handle
    )
    selector._last_cursor_handle = None
    return selector


def test_hit_test_outside_left_edge_is_west_handle_not_none():
    selector = _make_selector()
    margin = AreaSelector._SELECTION_HANDLE_MARGIN
    # Outside left border but still within the enlarged handle margin.
    assert selector._selection_hit_test(100 - margin + 1, 170) == "w"
    assert selector._selection_hit_test(100, 170) == "w"
    assert selector._selection_hit_test(200, 100 - margin + 1) == "n"
    assert selector._selection_hit_test(300 + margin - 1, 170) == "e"
    assert selector._selection_hit_test(200, 250 + margin - 1) == "s"
    assert selector._selection_hit_test(100, 100) == "nw"
    assert selector._selection_hit_test(300, 250) == "se"
    assert selector._selection_hit_test(200, 175) == "move"
    assert selector._selection_hit_test(100 - margin - 1, 170) is None
    assert selector._selection_hit_test(20, 20) is None


def test_hit_test_prefers_closer_edge_on_small_selection():
    # Width < 2*margin: both left/right strips overlap; closer side wins.
    selector = _make_selector(rect=(100, 100, 20, 80))
    assert selector._selection_hit_test(101, 140) == "w"
    assert selector._selection_hit_test(119, 140) == "e"


def test_press_just_outside_edge_starts_resize_not_reselect():
    selector = _make_selector()
    # Deep into the outside half of the west hit strip.
    handled = selector._on_button_press(None, _event(100 - 12, 170))

    assert handled is True
    assert selector._dragging is True
    assert selector._gesture_kind == "selection-w"
    assert selector._reselecting is False
    assert selector._selection_drag_origin == (100, 100, 200, 150)
    assert selector._annotations  # reselect would clear; resize must not


def test_press_far_outside_still_reselects():
    selector = _make_selector()
    handled = selector._on_button_press(None, _event(20, 30))

    assert handled is True
    assert selector._gesture_kind == "select"
    assert selector._reselecting is True
    assert selector._toolbar_frame.hidden is True


def test_east_edge_drag_expands_width():
    selector = _make_selector()
    selector._on_button_press(None, _event(300, 170))
    assert selector._gesture_kind == "selection-e"

    selector._end_x = 340
    selector._end_y = 170
    selector._update_selection_drag()

    assert selector._selection_rect == (100, 100, 240, 150)
    assert selector._result == (100, 100, 240, 150)


def test_west_edge_drag_moves_left_and_grows():
    selector = _make_selector()
    selector._on_button_press(None, _event(100, 170))
    assert selector._gesture_kind == "selection-w"

    selector._end_x = 60
    selector._end_y = 170
    selector._update_selection_drag()

    assert selector._selection_rect == (60, 100, 240, 150)


def test_south_east_corner_drag_grows_both_axes():
    selector = _make_selector()
    selector._on_button_press(None, _event(300, 250))
    assert selector._gesture_kind == "selection-se"

    selector._end_x = 360
    selector._end_y = 300
    selector._update_selection_drag()

    assert selector._selection_rect == (100, 100, 260, 200)


def test_resize_respects_min_size():
    selector = _make_selector(rect=(100, 100, 80, 80))
    selector._on_button_press(None, _event(180, 140))
    assert selector._gesture_kind == "selection-e"

    # Drag west past the minimum width.
    selector._end_x = 100
    selector._end_y = 140
    selector._update_selection_drag()

    min_size = AreaSelector._MIN_SELECTION_SIZE
    x, y, w, h = selector._selection_rect
    assert w == min_size
    assert h == 80
    assert x == 100


def test_move_drag_translates_selection():
    selector = _make_selector()
    selector._on_button_press(None, _event(200, 175))
    assert selector._gesture_kind == "selection-move"

    selector._end_x = 250
    selector._end_y = 195
    selector._update_selection_drag()

    assert selector._selection_rect == (150, 120, 200, 150)


def test_release_after_resize_keeps_annotations_and_repositions_toolbar():
    selector = _make_selector()
    selector._on_button_press(None, _event(300, 170))
    selector._on_button_release(None, SimpleNamespace(button=1, x=340, y=170))

    assert selector._selection_rect == (100, 100, 240, 150)
    assert selector._result == (100, 100, 240, 150)
    assert selector._annotations  # not cleared
    assert selector._dragging is False
    assert selector._gesture_kind is None
    assert selector._selection_drag_origin is None
    assert selector._container.moves  # toolbar repositioned
