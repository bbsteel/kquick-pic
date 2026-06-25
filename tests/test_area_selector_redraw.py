from quick_pic.area_selector import AreaSelector


class FakeDrawing:
    def __init__(self):
        self.areas = []

    def queue_draw_area(self, x, y, width, height):
        self.areas.append((x, y, width, height))


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
