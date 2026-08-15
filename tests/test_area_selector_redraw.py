import inspect

from PIL import Image

from kuick_pic.area_selector import AreaSelector, _sample_image_luma


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


def test_overlay_draw_never_clears_argb_surface():
    source = inspect.getsource(AreaSelector._on_draw_overlay)

    assert "OPERATOR_CLEAR" not in source
    assert "OPERATOR_OVER" in source


def test_sample_image_luma_reports_bright_frame():
    image = Image.new("RGB", (200, 100), (240, 240, 240))
    luma_min, luma_mean, luma_max = _sample_image_luma(image)
    assert luma_min == 240
    assert luma_mean == 240
    assert luma_max == 240


def test_sample_image_luma_reports_black_frame():
    image = Image.new("RGB", (200, 100), (0, 0, 0))
    luma_min, luma_mean, luma_max = _sample_image_luma(image)
    assert luma_min == 0
    assert luma_mean == 0
    assert luma_max == 0


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
    selector._mosaic_palette_frame = None
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


def test_position_toolbar_places_below_selection_when_space_allows():
    selector = object.__new__(AreaSelector)
    selector._selection_rect = (80, 90, 100, 70)
    selector._background_pixbuf = FakePixbuf()  # 500x400
    selector._toolbar_frame = FakeToolbarFrame()  # 120x52
    selector._color_palette_frame = None
    selector._mosaic_palette_frame = None
    selector._container = FakeContainer()

    selector._position_toolbar()

    # below: 90 + 70 + 12 = 172
    assert selector._container.moves == [(selector._toolbar_frame, 80, 172)]


def test_position_toolbar_flips_above_when_selection_near_bottom():
    selector = object.__new__(AreaSelector)
    # Selection bottom at y=380 on a 400px-tall screen — no room below.
    selector._selection_rect = (50, 300, 200, 80)
    selector._background_pixbuf = FakePixbuf()  # 500x400
    selector._toolbar_frame = FakeToolbarFrame()  # 120x52
    selector._color_palette_frame = None
    selector._mosaic_palette_frame = None
    selector._container = FakeContainer()

    selector._position_toolbar()

    # above: 300 - 52 - 12 = 236
    assert selector._container.moves == [(selector._toolbar_frame, 50, 236)]


def test_position_toolbar_clamps_when_selection_fills_screen():
    selector = object.__new__(AreaSelector)
    selector._selection_rect = (0, 0, 500, 400)
    selector._background_pixbuf = FakePixbuf()  # 500x400
    selector._toolbar_frame = FakeToolbarFrame()  # 120x52
    selector._color_palette_frame = None
    selector._mosaic_palette_frame = None
    selector._container = FakeContainer()

    selector._position_toolbar()

    # Neither above nor below has room; clamp to bottom margin band.
    # y = max(16, min(0+400+12, 400-52-16)) = max(16, min(412, 332)) = 332
    assert selector._container.moves == [(selector._toolbar_frame, 16, 332)]
