from types import SimpleNamespace

from kuick_pic.area_selector import AreaSelector
from kuick_pic.annotations import TextAnnotation


class FakeDrawing:
    def __init__(self):
        self.queued = 0

    def queue_draw(self):
        self.queued += 1


class FakeGtk:
    def __init__(self):
        self.main_quit_calls = 0

    def main_quit(self):
        self.main_quit_calls += 1


def _make_selector_with_text():
    selector = object.__new__(AreaSelector)
    selector._in_run = True
    selector._Gtk = FakeGtk()
    selector._drawing = FakeDrawing()
    selector._selection_rect = (100, 100, 200, 150)
    selector._pending_text_rect = None
    selector._selected_annotation_index = None
    selector._annotation_drag_index = None
    selector._annotation_drag_offset = None
    selector._result = selector._selection_rect
    selector._annotations = [
        TextAnnotation(
            rect=(20, 30, 60, 24),
            text="hello",
            color=(255, 0, 0),
            font_size=12,
        ),
    ]
    return selector


def test_right_click_on_text_deletes_without_exiting():
    selector = _make_selector_with_text()
    # Screen point over the text: selection origin + rect
    handled = selector._handle_right_click(100 + 30, 100 + 40)

    assert handled is True
    assert selector._annotations == []
    assert selector._Gtk.main_quit_calls == 0
    assert selector._result == (100, 100, 200, 150)
    assert selector._drawing.queued >= 1


def test_right_click_empty_cancels_session():
    selector = _make_selector_with_text()
    handled = selector._handle_right_click(100 + 180, 100 + 120)

    assert handled is True
    assert len(selector._annotations) == 1
    assert selector._Gtk.main_quit_calls == 1
    assert selector._result is None


def test_right_click_during_text_entry_cancels_entry_only():
    selector = _make_selector_with_text()
    selector._pending_text_rect = (10, 10, 80, 30)
    cancelled = {"n": 0}

    def _cancel():
        cancelled["n"] += 1
        selector._pending_text_rect = None

    selector._cancel_text_entry = _cancel
    handled = selector._handle_right_click(150, 150)

    assert handled is True
    assert cancelled["n"] == 1
    assert selector._Gtk.main_quit_calls == 0
    assert len(selector._annotations) == 1
