import math
from dataclasses import dataclass
from pathlib import Path


__all__ = [
    "SelectionResult",
    "RectangleAnnotation",
    "TextAnnotation",
    "LineAnnotation",
    "ArrowAnnotation",
    "NumberStampAnnotation",
    "MosaicAnnotation",
]


@dataclass(frozen=True)
class SelectionResult:
    rect: tuple[int, int, int, int]
    screenshot_path: Path
    annotations: list[
        "RectangleAnnotation | TextAnnotation | LineAnnotation | ArrowAnnotation | NumberStampAnnotation"
    ]
    # True when the user chose Pin (钉住); False for Save (保存).
    pin: bool = False


@dataclass(frozen=True)
class RectangleAnnotation:
    rect: tuple[int, int, int, int]   # (x, y, width, height) — selection-relative
    color: tuple[int, int, int]       # (r, g, b) 0-255


@dataclass(frozen=True)
class TextAnnotation:
    rect: tuple[int, int, int, int]   # (x, y, width, height) — selection-relative
    text: str
    color: tuple[int, int, int]       # (r, g, b) 0-255
    font_size: int = 12               # point size; matches editor + final render


@dataclass(frozen=True)
class LineAnnotation:
    start: tuple[int, int]            # (x, y) — selection-relative
    end: tuple[int, int]              # (x, y) — selection-relative
    color: tuple[int, int, int]       # (r, g, b) 0-255


@dataclass(frozen=True)
class ArrowAnnotation:
    start: tuple[int, int]            # (x, y) — selection-relative
    end: tuple[int, int]              # (x, y) — selection-relative
    color: tuple[int, int, int]       # (r, g, b) 0-255


@dataclass(frozen=True)
class NumberStampAnnotation:
    center: tuple[int, int]           # (x, y) — selection-relative
    number: int
    color: tuple[int, int, int]       # (r, g, b) 0-255


@dataclass(frozen=True)
class MosaicAnnotation:
    # Rect is expressed in the caller's render space: the area selector stores
    # ABSOLUTE screen coordinates and renders mosaics with origin (0, 0) so
    # they stay glued to the screen content when the selection moves; the
    # selector converts them to selection-relative before producing the final
    # SelectionResult.
    rect: tuple[int, int, int, int]   # (x, y, width, height)
    mode: str = "mosaic"              # "mosaic" (pixelate) | "blur" (gaussian)


# ---- shared Cairo rendering ----

_TEXT_FONT_FAMILY = "Sans"
_DEFAULT_TEXT_FONT_SIZE = 12
_TEXT_FONT = f"{_TEXT_FONT_FAMILY} {_DEFAULT_TEXT_FONT_SIZE}"
_TEXT_PADDING_X = 6
_TEXT_PADDING_Y = 4
_ARROW_ANGLE = math.radians(22.5)
_ARROW_LENGTH = 12
_STAMP_FONT = "Sans Bold 17"
_STAMP_RADIUS = 14


def text_font_description(font_size: int | None = None) -> str:
    """Pango font description shared by the text editor and final render."""
    size = int(font_size) if font_size is not None else _DEFAULT_TEXT_FONT_SIZE
    size = max(8, min(72, size))
    return f"{_TEXT_FONT_FAMILY} {size}"

# ---- 颜色辅助 ----

def _set_source_color(cr, color, alpha=0.95):
    r, g, b = color
    cr.set_source_rgba(r / 255.0, g / 255.0, b / 255.0, alpha)


# ---- 统一渲染入口 ----

def render_annotations(cr, annotations, origin_x=0, origin_y=0) -> None:
    """绘制全部标注到 Cairo context，origin 为选区左上角偏移。"""
    for annotation in annotations:
        if isinstance(annotation, RectangleAnnotation):
            _draw_rectangle_annotation(cr, annotation, origin_x, origin_y)
        elif isinstance(annotation, TextAnnotation):
            _draw_text_annotation(cr, annotation, origin_x, origin_y)
        elif isinstance(annotation, LineAnnotation):
            _draw_line_annotation(cr, annotation, origin_x, origin_y)
        elif isinstance(annotation, ArrowAnnotation):
            _draw_arrow_annotation(cr, annotation, origin_x, origin_y)
        elif isinstance(annotation, NumberStampAnnotation):
            _draw_number_stamp_annotation(cr, annotation, origin_x, origin_y)
        elif isinstance(annotation, MosaicAnnotation):
            _draw_mosaic_annotation(cr, annotation, origin_x, origin_y)


# ---- 拖拽预览 ----

def draw_line_preview(cr, start, end, color, origin_x=0, origin_y=0, dashed=True) -> None:
    """虚线预览（拖拽中）。"""
    _set_source_color(cr, color)
    cr.set_line_width(3)
    if dashed:
        cr.set_dash([8, 4], 0)
    cr.move_to(origin_x + start[0], origin_y + start[1])
    cr.line_to(origin_x + end[0], origin_y + end[1])
    cr.stroke()
    cr.set_dash([], 0)


def draw_arrow_preview(cr, start, end, color, origin_x=0, origin_y=0, dashed=True) -> None:
    """虚线 + 箭头预览（拖拽中）。"""
    draw_line_preview(cr, start, end, color, origin_x, origin_y, dashed=dashed)
    _draw_arrowhead(cr, end, start, color, origin_x, origin_y)


# ---- 私有渲染函数 ----

def _draw_mosaic_annotation(cr, annotation, origin_x, origin_y) -> None:
    """Pixelate the rect in place by resampling the cairo target itself.

    The target already holds the pixels under the annotation (frozen frame in
    the overlay, cropped image in the final render), so the mosaic always
    obscures whatever is underneath it at draw time.
    """
    import cairo

    x, y, w, h = annotation.rect
    if w < 2 or h < 2:
        return
    target = cr.get_target()
    # Copy the region out before overwriting it below.
    region = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    rcr = cairo.Context(region)
    rcr.set_source_surface(target, -origin_x - x, -origin_y - y)
    rcr.paint()

    if annotation.mode == "blur":
        # PIL gaussian on the sampled region; cairo has no blur filter.
        from PIL import Image, ImageFilter
        radius = max(4, min(16, min(w, h) // 6))
        img = Image.frombuffer(
            "RGBA", (w, h), region.get_data(), "raw", "BGRA", w * 4, 1
        )
        blurred = img.filter(ImageFilter.GaussianBlur(radius))
        buf = bytearray(blurred.tobytes("raw", "BGRA"))
        source = cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, w, h, w * 4)
        cr.save()
        cr.rectangle(origin_x + x, origin_y + y, w, h)
        cr.clip()
        cr.set_source_surface(source, origin_x + x, origin_y + y)
        cr.paint()
        cr.restore()
        return

    block = max(4, min(16, min(w, h) // 8))
    small_w = max(1, w // block)
    small_h = max(1, h // block)

    small = cairo.ImageSurface(cairo.FORMAT_ARGB32, small_w, small_h)
    scr = cairo.Context(small)
    scr.scale(small_w / w, small_h / h)
    scr.set_source_surface(region, 0, 0)
    scr.get_source().set_filter(cairo.FILTER_BILINEAR)
    scr.paint()

    cr.save()
    cr.rectangle(origin_x + x, origin_y + y, w, h)
    cr.clip()
    cr.translate(origin_x + x, origin_y + y)
    cr.scale(w / small_w, h / small_h)
    cr.set_source_surface(small, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_NEAREST)
    cr.paint()
    cr.restore()


def _draw_rectangle_annotation(cr, annotation, origin_x, origin_y, dashed=False) -> None:
    x, y, w, h = annotation.rect
    _set_source_color(cr, annotation.color)
    cr.set_line_width(3)
    if dashed:
        cr.set_dash([8, 4], 0)
    cr.rectangle(origin_x + x + 1.5, origin_y + y + 1.5, max(1, w - 3), max(1, h - 3))
    cr.stroke()
    cr.set_dash([], 0)


def measure_text_pixel_size(
    text: str,
    max_width: int,
    *,
    font: str | None = None,
    font_size: int | None = None,
    padding_x: int = _TEXT_PADDING_X,
    padding_y: int = _TEXT_PADDING_Y,
) -> tuple[int, int]:
    """Return (width, height) including padding for laid-out annotation text."""
    import cairo
    import gi

    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo

    font_desc = font if font is not None else text_font_description(font_size)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    cr = cairo.Context(surface)
    layout = PangoCairo.create_layout(cr)
    layout.set_text(text, -1)
    layout.set_font_description(Pango.FontDescription(font_desc))
    content_width = max(1, int(max_width) - 2 * padding_x)
    layout.set_width(content_width * Pango.SCALE)
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    text_w, text_h = layout.get_pixel_size()
    return (
        max(1, text_w + 2 * padding_x),
        max(1, text_h + 2 * padding_y),
    )


def clamp_rect_in_bounds(
    rect: tuple[int, int, int, int],
    bounds: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Clamp a rect so it stays fully inside (0,0)-(sw,sh)."""
    x, y, w, h = rect
    sw, sh = bounds
    w = max(1, min(w, sw))
    h = max(1, min(h, sh))
    x = max(0, min(x, sw - w))
    y = max(0, min(y, sh - h))
    return (int(x), int(y), int(w), int(h))


def hit_text_annotation_index(
    annotations: list,
    point_rel: tuple[int, int],
) -> int | None:
    """Topmost TextAnnotation index containing the selection-relative point."""
    px, py = point_rel
    for index in range(len(annotations) - 1, -1, -1):
        ann = annotations[index]
        if not isinstance(ann, TextAnnotation):
            continue
        x, y, w, h = ann.rect
        if x <= px <= x + w and y <= py <= y + h:
            return index
    return None


def click_text_placement_rect(
    selection_size: tuple[int, int],
    click_rel: tuple[int, int],
    *,
    default_w: int = 160,
    default_h: int = 36,
    min_w: int = 48,
) -> tuple[int, int, int, int] | None:
    """Selection-relative rect for click-to-type text placement.

    Anchor stays at the click when possible. For clicks near the right/bottom
    edge of a small selection, the origin shifts so the rect stays inside.
    """
    sw, sh = selection_size
    x, y = int(click_rel[0]), int(click_rel[1])
    if sw <= 0 or sh <= 0 or x < 0 or y < 0 or x >= sw or y >= sh:
        return None

    # Prefer a comfortable wrap width, but never exceed the selection.
    target_w = min(default_w, sw)
    if target_w >= min_w and sw - x < min_w:
        x = max(0, sw - target_w)
    w = min(target_w, sw - x)
    if w < 1:
        x = 0
        w = sw

    target_h = min(default_h, sh)
    min_h = min(24, sh)
    if target_h >= min_h and sh - y < min_h:
        y = max(0, sh - target_h)
    h = min(target_h, sh - y)
    if h < 1:
        y = 0
        h = sh

    return (x, y, int(w), int(h))


def _draw_text_annotation(cr, annotation, origin_x, origin_y) -> None:
    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo

    x, y, w, h = annotation.rect
    font_size = getattr(annotation, "font_size", _DEFAULT_TEXT_FONT_SIZE)
    layout = PangoCairo.create_layout(cr)
    layout.set_text(annotation.text, -1)
    layout.set_font_description(Pango.FontDescription(text_font_description(font_size)))
    layout.set_width(max(1, w - _TEXT_PADDING_X * 2) * Pango.SCALE)
    layout.set_wrap(Pango.WrapMode.WORD_CHAR)
    cr.save()
    cr.rectangle(origin_x + x, origin_y + y, w, h)
    cr.clip()
    draw_x = origin_x + x + _TEXT_PADDING_X
    draw_y = origin_y + y + _TEXT_PADDING_Y
    cr.set_source_rgba(0, 0, 0, 0.65)
    cr.move_to(draw_x + 1, draw_y + 1)
    PangoCairo.show_layout(cr, layout)
    _set_source_color(cr, annotation.color)
    cr.move_to(draw_x, draw_y)
    PangoCairo.show_layout(cr, layout)
    cr.restore()


def _draw_line_annotation(cr, annotation, origin_x, origin_y) -> None:
    _set_source_color(cr, annotation.color)
    cr.set_line_width(3)
    cr.move_to(origin_x + annotation.start[0], origin_y + annotation.start[1])
    cr.line_to(origin_x + annotation.end[0], origin_y + annotation.end[1])
    cr.stroke()


def _draw_arrow_annotation(cr, annotation, origin_x, origin_y) -> None:
    _draw_line_annotation(cr, annotation, origin_x, origin_y)
    _draw_arrowhead(cr, annotation.end, annotation.start, annotation.color, origin_x, origin_y)


def _draw_number_stamp_annotation(cr, annotation, origin_x, origin_y) -> None:
    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo

    cx = origin_x + annotation.center[0]
    cy = origin_y + annotation.center[1]
    radius = _STAMP_RADIUS

    _set_source_color(cr, annotation.color)
    cr.set_line_width(3)
    cr.new_sub_path()
    cr.arc(cx, cy, radius, 0, math.tau)
    cr.stroke()

    layout = PangoCairo.create_layout(cr)
    layout.set_text(str(annotation.number), -1)
    layout.set_font_description(Pango.FontDescription(_STAMP_FONT))
    text_width, text_height = layout.get_pixel_size()
    text_x = cx - text_width / 2
    text_y = cy - text_height / 2

    cr.set_source_rgba(0, 0, 0, 0.65)
    cr.move_to(text_x + 1, text_y + 1)
    PangoCairo.show_layout(cr, layout)
    _set_source_color(cr, annotation.color)
    cr.move_to(text_x, text_y)
    PangoCairo.show_layout(cr, layout)


def _draw_arrowhead(cr, tip, tail, color, origin_x, origin_y) -> None:
    """在 tip 处绘制八字形开口箭头（两条短线，不填充）。"""
    tip_x = origin_x + tip[0]
    tip_y = origin_y + tip[1]
    tail_x = origin_x + tail[0]
    tail_y = origin_y + tail[1]

    angle = math.atan2(tip_y - tail_y, tip_x - tail_x)

    left_x = tip_x - _ARROW_LENGTH * math.cos(angle - _ARROW_ANGLE)
    left_y = tip_y - _ARROW_LENGTH * math.sin(angle - _ARROW_ANGLE)
    right_x = tip_x - _ARROW_LENGTH * math.cos(angle + _ARROW_ANGLE)
    right_y = tip_y - _ARROW_LENGTH * math.sin(angle + _ARROW_ANGLE)

    _set_source_color(cr, color)
    cr.set_line_width(3)
    cr.move_to(tip_x, tip_y)
    cr.line_to(left_x, left_y)
    cr.stroke()
    cr.move_to(tip_x, tip_y)
    cr.line_to(right_x, right_y)
    cr.stroke()
