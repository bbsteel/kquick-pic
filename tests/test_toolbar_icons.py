import cairo
import pytest

from quick_pic.toolbar_icons import TOOLBAR_ICON_SIZE, draw_toolbar_icon


ICON_NAMES = (
    "box",
    "text",
    "line",
    "arrow",
    "number",
    "color",
    "undo",
    "confirm",
    "cancel",
)


def _alpha_bounds(surface: cairo.ImageSurface) -> tuple[int, int, int, int] | None:
    width = surface.get_width()
    height = surface.get_height()
    data = bytes(surface.get_data())
    stride = surface.get_stride()
    xs: list[int] = []
    ys: list[int] = []

    for y in range(height):
        row = y * stride
        for x in range(width):
            offset = row + x * 4
            alpha = data[offset + 3]
            if alpha:
                xs.append(x)
                ys.append(y)

    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize("icon_name", ICON_NAMES)
def test_toolbar_icon_draws_visible_pixels_inside_fixed_canvas(icon_name):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE)
    cr = cairo.Context(surface)

    draw_toolbar_icon(cr, icon_name, (32, 43, 54), TOOLBAR_ICON_SIZE)

    bounds = _alpha_bounds(surface)
    assert bounds is not None
    left, top, right, bottom = bounds
    assert 0 <= left <= right < TOOLBAR_ICON_SIZE
    assert 0 <= top <= bottom < TOOLBAR_ICON_SIZE


def test_toolbar_icon_rejects_unknown_icon_name():
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE)
    cr = cairo.Context(surface)

    with pytest.raises(ValueError, match="Unknown toolbar icon"):
        draw_toolbar_icon(cr, "missing", (32, 43, 54), TOOLBAR_ICON_SIZE)
