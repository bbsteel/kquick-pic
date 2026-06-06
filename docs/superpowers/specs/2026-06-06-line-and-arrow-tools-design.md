# Line and Arrow Annotation Tools

## Overview

Add two new drawing tools to the screenshot annotation system: a straight line tool and an arrow tool.

## Design

### Data Model (`area_selector.py`)

Two new frozen dataclasses:

```python
@dataclass(frozen=True)
class LineAnnotation:
    start: tuple[int, int]     # (x, y) start point, relative to selection
    end: tuple[int, int]       # (x, y) end point, relative to selection
    color: tuple[int, int, int]

@dataclass(frozen=True)
class ArrowAnnotation:
    start: tuple[int, int]
    end: tuple[int, int]
    color: tuple[int, int, int]
```

Both share the same structure but are distinct types so rendering code can branch on type.

### Toolbar Buttons

Two new toggle buttons, mutually exclusive with `box`, `text`, and each other:

- `—` Straight line (i18n key: `selector.draw_line`)
- `→` Arrow (i18n key: `selector.draw_arrow`)

### Interaction (Drag Start → Drag → Release)

Same as existing box/text tools:
- Click in selection area → begin gesture
- Drag → dashed preview line from start to current cursor
- Release → commit annotation to `self._annotations`

Both tools set `self._gesture_kind` to `"line"` or `"arrow"`, with `self._gesture_start` holding the start point.

### Keyboard Cursor

In line or arrow mode, cursor changes to crosshair while inside the selection area.

### Cairo Rendering (`area_selector.py`)

**Preview (drag in progress):**
- Dashed line from start to current mouse position
- Width 2px, color = selected color

**Final line:**
- Solid line, width 3px

**Final arrow:**
- Same solid line as above
- Plus an open V-shaped arrowhead at the end point:
  - Two short lines (12px each) extending backward from the end point
  - Spread angle: ±22.5° from the line direction (total 45° opening)
  - Same color and width as the line

### Final Image Rendering (`screenshot.py`)

`_apply_annotations()` gets two new `isinstance` branches for `LineAnnotation` and `ArrowAnnotation`, duplicating the same drawing logic. Arrowhead is computed via trigonometry (atan2 for angle, then offset backward along the line).

### Undo

Works automatically via the existing `_on_undo` which pops the last annotation. Both `LineAnnotation` and `ArrowAnnotation` are items in the same list.

### i18n

| Key | en | zh-CN |
|---|---|---|
| `selector.draw_line` | Draw Line | 直线 |
| `selector.draw_arrow` | Draw Arrow | 箭头 |

### Files Changed

| File | Change |
|---|---|
| `quick_pic/area_selector.py` | New dataclasses, buttons, gesture handling, Cairo drawing methods |
| `quick_pic/screenshot.py` | New annotation rendering branches in `_apply_annotations` |
| `quick_pic/locales/en.json` | Two new keys |
| `quick_pic/locales/zh-CN.json` | Two new keys |

### Out of Scope

- Arrowhead style configuration (always open V-shape)
- Line width configuration (always 3px)
- Freehand/pencil drawing
- Other shapes (circle, ellipse)
