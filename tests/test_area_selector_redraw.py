from quick_pic.area_selector import AreaSelector


class FakeDrawing:
    def __init__(self):
        self.areas = []

    def queue_draw_area(self, x, y, width, height):
        self.areas.append((x, y, width, height))


class FakePixbuf:
    def get_width(self):
        return 500

    def get_height(self):
        return 400


class FakeToolbarFrame:
    def get_preferred_size(self):
        natural = type("Size", (), {"width": 120, "height": 52})()
        return None, natural


class FakeContainer:
    def __init__(self):
        self.moves = []

    def move(self, widget, x, y):
        self.moves.append((widget, x, y))


def _covers(queued, rect):
    qx, qy, qw, qh = queued
    rx, ry, rw, rh = rect
    return qx <= rx and qy <= ry and qx + qw >= rx + rw and qy + qh >= ry + rh


def test_selection_drag_redraw_covers_old_and_new_selection_bodies():
    selector = object.__new__(AreaSelector)
    selector._drawing = FakeDrawing()
    selector._gesture_kind = "selection-move"
    selector._selection_rect = (80, 90, 100, 70)

    previous_rect = (40, 50, 100, 70)

    selector._queue_drag_redraw(previous_rect)

    assert any(_covers(area, previous_rect) for area in selector._drawing.areas)
    assert any(_covers(area, selector._selection_rect) for area in selector._drawing.areas)


def test_selection_drag_repositions_toolbar_during_motion_flush():
    selector = object.__new__(AreaSelector)
    selector._drawing = FakeDrawing()
    selector._gesture_kind = "selection-move"
    selector._selection_rect = (80, 90, 100, 70)
    selector._selection_drag_origin = selector._selection_rect
    selector._background_pixbuf = FakePixbuf()
    selector._toolbar_frame = FakeToolbarFrame()
    selector._color_palette_frame = None
    selector._container = FakeContainer()
    selector._dragging = True
    selector._motion_pending_event = (120, 130)
    selector._start_x = 90
    selector._start_y = 100
    selector._end_x = 90
    selector._end_y = 100
    selector._last_motion_time = 0
    selector._motion_flush_count = 0

    selector._flush_motion()

    assert selector._selection_rect == (110, 120, 100, 70)
    assert selector._container.moves == [(selector._toolbar_frame, 110, 202)]
