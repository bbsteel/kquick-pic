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
]


@dataclass(frozen=True)
class SelectionResult:
    rect: tuple[int, int, int, int]
    screenshot_path: Path
    annotations: list[
        "RectangleAnnotation | TextAnnotation | LineAnnotation | ArrowAnnotation | NumberStampAnnotation"
    ]


@dataclass(frozen=True)
class RectangleAnnotation:
    rect: tuple[int, int, int, int]   # (x, y, width, height) — selection-relative
    color: tuple[int, int, int]       # (r, g, b) 0-255


@dataclass(frozen=True)
class TextAnnotation:
    rect: tuple[int, int, int, int]   # (x, y, width, height) — selection-relative
    text: str
    color: tuple[int, int, int]       # (r, g, b) 0-255


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


# ---- shared Cairo rendering ----

_TEXT_FONT = "Sans 20"
_TEXT_PADDING_X = 8
_TEXT_PADDING_Y = 6
_ARROW_ANGLE = math.radians(22.5)
_ARROW_LENGTH = 12
_STAMP_FONT = "Sans Bold 17"
_STAMP_RADIUS = 14

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

def _draw_rectangle_annotation(cr, annotation, origin_x, origin_y, dashed=False) -> None:
    x, y, w, h = annotation.rect
    _set_source_color(cr, annotation.color)
    cr.set_line_width(3)
    if dashed:
        cr.set_dash([8, 4], 0)
    cr.rectangle(origin_x + x + 1.5, origin_y + y + 1.5, max(1, w - 3), max(1, h - 3))
    cr.stroke()
    cr.set_dash([], 0)


def _draw_text_annotation(cr, annotation, origin_x, origin_y) -> None:
    import gi
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo

    x, y, w, h = annotation.rect
    layout = PangoCairo.create_layout(cr)
    layout.set_text(annotation.text, -1)
    layout.set_font_description(Pango.FontDescription(_TEXT_FONT))
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
