from quick_pic.area_selector import AreaSelector
from quick_pic.annotations import NumberStampAnnotation


class FakeDrawing:
    def __init__(self):
        self.queued = False

    def queue_draw(self):
        self.queued = True


def _make_selector():
    selector = object.__new__(AreaSelector)
    selector._selection_rect = (100, 200, 300, 180)
    selector._annotations = []
    selector._drawing = FakeDrawing()
    selector._selected_color_value = (255, 0, 0)
    selector._next_number_stamp_value = 1
    return selector


def test_add_number_stamp_increments_each_click():
    selector = _make_selector()

    assert selector._add_number_stamp_at(120, 230) is True
    assert selector._add_number_stamp_at(140, 260) is True

    assert selector._annotations == [
        NumberStampAnnotation(center=(20, 30), number=1, color=(255, 0, 0)),
        NumberStampAnnotation(center=(40, 60), number=2, color=(255, 0, 0)),
    ]
    assert selector._drawing.queued is True


def test_add_number_stamp_ignores_points_outside_selection():
    selector = _make_selector()

    assert selector._add_number_stamp_at(90, 230) is False

    assert selector._annotations == []
    assert selector._drawing.queued is False


def test_number_stamp_counter_does_not_reuse_number_after_undo():
    selector = _make_selector()

    selector._add_number_stamp_at(120, 230)
    selector._on_undo(None)
    selector._add_number_stamp_at(140, 260)

    assert selector._annotations == [
        NumberStampAnnotation(center=(40, 60), number=2, color=(255, 0, 0)),
    ]
