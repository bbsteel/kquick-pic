import math

import cairo


TOOLBAR_ICON_SIZE = 24
TOOLBAR_ICON_INSET = 4


def draw_toolbar_icon(
    cr: cairo.Context,
    icon_name: str,
    color: tuple[int, int, int],
    size: int = TOOLBAR_ICON_SIZE,
) -> None:
    """Draw a toolbar icon into a fixed square Cairo canvas."""
    draw_fn = _DRAWERS.get(icon_name)
    if draw_fn is None:
        raise ValueError(f"Unknown toolbar icon: {icon_name}")

    cr.save()
    _set_source_color(cr, color)
    cr.set_line_width(max(2.0, size / 12.0))
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    draw_fn(cr, float(size))
    cr.restore()


def _set_source_color(cr: cairo.Context, color: tuple[int, int, int], alpha: float = 0.95) -> None:
    red, green, blue = color
    cr.set_source_rgba(red / 255.0, green / 255.0, blue / 255.0, alpha)


def _draw_box(cr: cairo.Context, size: float) -> None:
    inset = TOOLBAR_ICON_INSET + 0.5
    cr.rectangle(inset, inset, size - inset * 2, size - inset * 2)
    cr.stroke()


def _draw_text(cr: cairo.Context, size: float) -> None:
    cr.move_to(size * 0.28, size * 0.30)
    cr.line_to(size * 0.72, size * 0.30)
    cr.move_to(size * 0.50, size * 0.30)
    cr.line_to(size * 0.50, size * 0.76)
    cr.stroke()


def _draw_line(cr: cairo.Context, size: float) -> None:
    cr.move_to(size * 0.30, size * 0.72)
    cr.line_to(size * 0.70, size * 0.28)
    cr.stroke()


def _draw_arrow(cr: cairo.Context, size: float) -> None:
    start = (size * 0.24, size * 0.62)
    end = (size * 0.76, size * 0.38)
    cr.move_to(*start)
    cr.line_to(*end)
    cr.stroke()
    _draw_arrowhead(cr, tip=end, tail=start, length=size * 0.22)


def _draw_number(cr: cairo.Context, size: float) -> None:
    cr.arc(size / 2, size / 2, size * 0.34, 0, math.tau)
    cr.stroke()
    cr.move_to(size * 0.50, size * 0.34)
    cr.line_to(size * 0.50, size * 0.68)
    cr.move_to(size * 0.43, size * 0.42)
    cr.line_to(size * 0.50, size * 0.34)
    cr.stroke()


def _draw_color(cr: cairo.Context, size: float) -> None:
    cr.arc(size / 2, size / 2, size * 0.31, 0, math.tau)
    cr.fill_preserve()
    cr.set_source_rgba(0, 0, 0, 0.18)
    cr.set_line_width(max(1.0, size / 18.0))
    cr.stroke()


def _draw_undo(cr: cairo.Context, size: float) -> None:
    cr.arc(size * 0.54, size * 0.54, size * 0.28, math.radians(35), math.radians(260))
    cr.stroke()
    cr.move_to(size * 0.27, size * 0.37)
    cr.line_to(size * 0.26, size * 0.62)
    cr.line_to(size * 0.43, size * 0.50)
    cr.stroke()


def _draw_confirm(cr: cairo.Context, size: float) -> None:
    # Checkmark — used for Save.
    cr.move_to(size * 0.27, size * 0.53)
    cr.line_to(size * 0.44, size * 0.70)
    cr.line_to(size * 0.75, size * 0.33)
    cr.stroke()


def _draw_pin(cr: cairo.Context, size: float) -> None:
    # Pushpin: round head + short needle.
    cr.arc(size * 0.50, size * 0.34, size * 0.18, 0, math.tau)
    cr.stroke()
    cr.move_to(size * 0.50, size * 0.52)
    cr.line_to(size * 0.50, size * 0.80)
    cr.stroke()
    # Small crossbar under the head.
    cr.move_to(size * 0.36, size * 0.50)
    cr.line_to(size * 0.64, size * 0.50)
    cr.stroke()


def _draw_cancel(cr: cairo.Context, size: float) -> None:
    cr.move_to(size * 0.32, size * 0.32)
    cr.line_to(size * 0.68, size * 0.68)
    cr.move_to(size * 0.68, size * 0.32)
    cr.line_to(size * 0.32, size * 0.68)
    cr.stroke()


def _draw_arrowhead(
    cr: cairo.Context,
    tip: tuple[float, float],
    tail: tuple[float, float],
    length: float,
) -> None:
    angle = math.atan2(tip[1] - tail[1], tip[0] - tail[0])
    spread = math.radians(28)
    for delta in (-spread, spread):
        x = tip[0] - length * math.cos(angle + delta)
        y = tip[1] - length * math.sin(angle + delta)
        cr.move_to(*tip)
        cr.line_to(x, y)
    cr.stroke()


_DRAWERS = {
    "box": _draw_box,
    "text": _draw_text,
    "line": _draw_line,
    "arrow": _draw_arrow,
    "number": _draw_number,
    "color": _draw_color,
    "undo": _draw_undo,
    "save": _draw_confirm,
    "confirm": _draw_confirm,  # alias for save checkmark
    "pin": _draw_pin,
    "cancel": _draw_cancel,
}
