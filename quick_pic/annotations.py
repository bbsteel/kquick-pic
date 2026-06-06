from dataclasses import dataclass
from pathlib import Path


__all__ = [
    "SelectionResult",
    "RectangleAnnotation",
    "TextAnnotation",
    "LineAnnotation",
    "ArrowAnnotation",
]


@dataclass(frozen=True)
class SelectionResult:
    rect: tuple[int, int, int, int]
    screenshot_path: Path
    annotations: list["RectangleAnnotation | TextAnnotation | LineAnnotation | ArrowAnnotation"]


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
