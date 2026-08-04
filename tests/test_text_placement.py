from kquick_pic.annotations import (
    TextAnnotation,
    RectangleAnnotation,
    click_text_placement_rect,
    clamp_rect_in_bounds,
    hit_text_annotation_index,
    measure_text_pixel_size,
    text_font_description,
    render_annotations,
)
import cairo


class TestClickTextPlacementRect:
    def test_click_near_origin_uses_default_size(self):
        rect = click_text_placement_rect((400, 300), (20, 30), default_w=160, default_h=36)
        assert rect == (20, 30, 160, 36)

    def test_click_near_right_edge_shifts_left_for_min_width(self):
        # Selection 100 wide; click at x=90 leaves only 10px — shift left.
        rect = click_text_placement_rect((100, 80), (90, 10), default_w=160, default_h=36, min_w=48)
        assert rect is not None
        x, y, w, h = rect
        assert x + w <= 100
        assert w >= 48
        assert y == 10

    def test_tiny_selection_still_places(self):
        rect = click_text_placement_rect((40, 30), (5, 5), default_w=160, default_h=36, min_w=48)
        assert rect is not None
        x, y, w, h = rect
        assert x >= 0 and y >= 0
        assert x + w <= 40
        assert y + h <= 30

    def test_outside_selection_returns_none(self):
        assert click_text_placement_rect((100, 100), (-1, 10)) is None
        assert click_text_placement_rect((100, 100), (10, 100)) is None
        assert click_text_placement_rect((0, 0), (0, 0)) is None


class TestMeasureTextPixelSize:
    def test_non_empty_text_has_positive_size(self):
        w, h = measure_text_pixel_size("hello", 200, font_size=16)
        assert w > 8
        assert h > 6

    def test_wrap_width_limits_layout(self):
        wide_w, wide_h = measure_text_pixel_size("word " * 20, 400, font_size=16)
        narrow_w, narrow_h = measure_text_pixel_size("word " * 20, 80, font_size=16)
        assert narrow_w <= 80
        assert narrow_h >= wide_h

    def test_larger_font_is_taller(self):
        _, small_h = measure_text_pixel_size("Aa", 200, font_size=12)
        _, large_h = measure_text_pixel_size("Aa", 200, font_size=32)
        assert large_h > small_h


class TestTextFontDescription:
    def test_default_and_clamped(self):
        assert text_font_description(16) == "Sans 16"
        assert text_font_description(4) == "Sans 8"
        assert text_font_description(100) == "Sans 72"


class TestTextAnnotationFontSize:
    def test_render_respects_font_size(self):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 100)
        cr = cairo.Context(surface)
        ann = TextAnnotation(
            rect=(5, 5, 180, 40),
            text="Hi",
            color=(255, 0, 0),
            font_size=14,
        )
        render_annotations(cr, [ann])
        surface.flush()


class TestClampAndHitText:
    def test_clamp_keeps_rect_inside(self):
        assert clamp_rect_in_bounds((90, 80, 40, 30), (100, 100)) == (60, 70, 40, 30)

    def test_hit_topmost_text(self):
        anns = [
            RectangleAnnotation(rect=(0, 0, 50, 50), color=(0, 0, 0)),
            TextAnnotation(rect=(10, 10, 40, 20), text="a", color=(255, 0, 0), font_size=12),
            TextAnnotation(rect=(15, 12, 40, 20), text="b", color=(0, 255, 0), font_size=12),
        ]
        assert hit_text_annotation_index(anns, (20, 15)) == 2
        assert hit_text_annotation_index(anns, (5, 5)) is None
