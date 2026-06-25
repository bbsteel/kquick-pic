import cairo
import pytest
from quick_pic.annotations import (
    LineAnnotation,
    ArrowAnnotation,
    NumberStampAnnotation,
    RectangleAnnotation,
    TextAnnotation,
    SelectionResult,
    render_annotations,
    draw_line_preview,
    draw_arrow_preview,
)


class TestLineAnnotation:
    def test_create(self):
        a = LineAnnotation(start=(10, 20), end=(30, 40), color=(255, 0, 0))
        assert a.start == (10, 20)
        assert a.end == (30, 40)
        assert a.color == (255, 0, 0)

    def test_is_frozen(self):
        a = LineAnnotation(start=(0, 0), end=(10, 10), color=(0, 0, 0))
        with pytest.raises(Exception):
            a.start = (1, 2)


class TestArrowAnnotation:
    def test_create(self):
        a = ArrowAnnotation(start=(5, 5), end=(50, 50), color=(0, 255, 0))
        assert a.start == (5, 5)
        assert a.end == (50, 50)
        assert a.color == (0, 255, 0)

    def test_is_frozen(self):
        a = ArrowAnnotation(start=(0, 0), end=(1, 1), color=(0, 0, 0))
        with pytest.raises(Exception):
            a.color = (1, 2, 3)


class TestNumberStampAnnotation:
    def test_create(self):
        a = NumberStampAnnotation(center=(10, 20), number=3, color=(255, 0, 0))
        assert a.center == (10, 20)
        assert a.number == 3
        assert a.color == (255, 0, 0)

    def test_is_frozen(self):
        a = NumberStampAnnotation(center=(0, 0), number=1, color=(0, 0, 0))
        with pytest.raises(Exception):
            a.number = 2


class TestRenderAnnotations:
    def _make_surface(self, w=200, h=150):
        return cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)

    def test_render_rectangle(self):
        surface = self._make_surface()
        cr = cairo.Context(surface)
        ann = RectangleAnnotation(rect=(10, 10, 80, 50), color=(255, 0, 0))
        render_annotations(cr, [ann])
        surface.flush()

    def test_render_line(self):
        surface = self._make_surface()
        cr = cairo.Context(surface)
        ann = LineAnnotation(start=(10, 10), end=(100, 60), color=(0, 0, 255))
        render_annotations(cr, [ann])
        surface.flush()

    def test_render_arrow(self):
        surface = self._make_surface()
        cr = cairo.Context(surface)
        ann = ArrowAnnotation(start=(10, 10), end=(100, 60), color=(0, 255, 0))
        render_annotations(cr, [ann])
        surface.flush()

    def test_render_number_stamp(self):
        surface = self._make_surface()
        cr = cairo.Context(surface)
        ann = NumberStampAnnotation(center=(40, 40), number=1, color=(255, 0, 0))
        render_annotations(cr, [ann])
        surface.flush()

    def test_render_number_stamp_does_not_connect_from_existing_path(self):
        surface = self._make_surface()
        cr = cairo.Context(surface)
        cr.move_to(0, 0)
        ann = NumberStampAnnotation(center=(100, 100), number=1, color=(255, 0, 0))

        render_annotations(cr, [ann])
        surface.flush()

        data = surface.get_data()
        stride = surface.get_stride()
        # This point lies on the unwanted line Cairo draws from (0, 0) to
        # the circle start if arc() is not isolated with new_sub_path().
        pixel_offset = 53 * stride + 60 * 4
        blue, green, red, alpha = data[pixel_offset : pixel_offset + 4]
        assert (red, green, blue, alpha) == (0, 0, 0, 0)

    def test_render_with_origin_offset(self):
        surface = self._make_surface()
        cr = cairo.Context(surface)
        ann = LineAnnotation(start=(10, 10), end=(50, 50), color=(255, 255, 255))
        render_annotations(cr, [ann], origin_x=50, origin_y=30)
        surface.flush()


class TestDrawPreviews:
    def _make_surface(self, w=200, h=150):
        return cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)

    def test_line_preview(self):
        surface = self._make_surface()
        cr = cairo.Context(surface)
        draw_line_preview(cr, (10, 10), (80, 80), (255, 0, 0))

    def test_arrow_preview(self):
        surface = self._make_surface()
        cr = cairo.Context(surface)
        draw_arrow_preview(cr, (10, 10), (80, 80), (255, 0, 0))

    def test_arrow_preview_with_offset(self):
        surface = self._make_surface()
        cr = cairo.Context(surface)
        draw_arrow_preview(cr, (10, 10), (80, 80), (255, 0, 0), origin_x=50, origin_y=30)


class TestSelectionResult:
    def test_line_in_annotations(self):
        line = LineAnnotation(start=(0, 0), end=(10, 10), color=(0, 0, 0))
        result = SelectionResult(
            rect=(0, 0, 100, 100),
            screenshot_path="/tmp/test.png",
            annotations=[line],
        )
        assert isinstance(result.annotations[0], LineAnnotation)

    def test_arrow_in_annotations(self):
        arrow = ArrowAnnotation(start=(0, 0), end=(10, 10), color=(0, 0, 0))
        result = SelectionResult(
            rect=(0, 0, 100, 100),
            screenshot_path="/tmp/test.png",
            annotations=[arrow],
        )
        assert isinstance(result.annotations[0], ArrowAnnotation)

    def test_number_stamp_in_annotations(self):
        stamp = NumberStampAnnotation(center=(20, 20), number=1, color=(255, 0, 0))
        result = SelectionResult(
            rect=(0, 0, 100, 100),
            screenshot_path="/tmp/test.png",
            annotations=[stamp],
        )
        assert isinstance(result.annotations[0], NumberStampAnnotation)
