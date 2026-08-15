# 直线与箭头标注工具 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标:** 从 `area_selector.py` 中提取标注类型和渲染逻辑到共享模块 `annotations.py`，新增 `LineAnnotation` / `ArrowAnnotation` 及对应工具栏按钮、拖拽手势、预览和最终渲染。

**架构:** 新建 `kuick_pic/annotations.py` 作为唯一的数据模型和 Cairo 渲染源。`area_selector.py`（屏幕标注）和 `screenshot.py`（最终图片）都调用 `render_annotations()` 统一绘制。直线/箭头的拖拽预览使用独立函数 `draw_line_preview` / `draw_arrow_preview`。

**技术栈:** Python, GTK3, Cairo, PangoCairo, dataclasses

---

## 改动前 / 改动后对比

**改动前:**
```
area_selector.py (983 行)           screenshot.py (131 行)
├── SelectionResult                 ├── import from area_selector
├── RectangleAnnotation             ├── _apply_annotations (手写)
├── TextAnnotation                  │   ├── RectangleAnnotation 渲染
├── AreaSelector (全部 UI+手势)     │   └── TextAnnotation 渲染
│   ├── 手势处理 (box, text)        └── _draw_text_annotation (重复)
│   ├── _draw_annotations
│   │   ├── _draw_rectangle_annotation
│   │   └── _draw_text_annotation
│   └── _on_draw_overlay (拖拽预览)
```

**改动后:**
```
annotations.py (新)                 area_selector.py (~850 行)     screenshot.py (~90 行)
├── SelectionResult                 ├── import from annotations    ├── import from annotations
├── RectangleAnnotation             ├── 手势 (box/text/line/arrow) ├── _apply_annotations
├── TextAnnotation                  ├── _on_draw_overlay           │   └── render_annotations()
├── LineAnnotation (新)             │   ├── 拖拽预览 + 预览函数
├── ArrowAnnotation (新)            │   └── render_annotations()
├── render_annotations()            ├── _draw_annotations
├── draw_line_preview() (新)        │   └── render_annotations()
├── draw_arrow_preview() (新)       └── 4 个工具按钮
├── _draw_rectangle_annotation()
├── _draw_text_annotation()
├── _draw_line_annotation() (新)
├── _draw_arrow_annotation() (新)
└── _draw_arrowhead() (新)
```

---

### Task 1: 创建 `kuick_pic/annotations.py` — 标注 dataclass

**文件:** 创建 `kuick_pic/annotations.py`

- [ ] **Step 1: 创建文件**

```python
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
    rect: tuple[int, int, int, int]   # (x, y, width, height) — 相对于选区
    color: tuple[int, int, int]       # (r, g, b) 0-255


@dataclass(frozen=True)
class TextAnnotation:
    rect: tuple[int, int, int, int]   # (x, y, width, height) — 相对于选区
    text: str
    color: tuple[int, int, int]       # (r, g, b) 0-255


@dataclass(frozen=True)
class LineAnnotation:
    start: tuple[int, int]            # (x, y) — 相对于选区
    end: tuple[int, int]              # (x, y) — 相对于选区
    color: tuple[int, int, int]       # (r, g, b) 0-255


@dataclass(frozen=True)
class ArrowAnnotation:
    start: tuple[int, int]            # (x, y) — 相对于选区
    end: tuple[int, int]              # (x, y) — 相对于选区
    color: tuple[int, int, int]       # (r, g, b) 0-255
```

- [ ] **Step 2: 验证导入**

```bash
uv run python -c "from kuick_pic.annotations import LineAnnotation, ArrowAnnotation, SelectionResult; print('OK')"
```

预期: `OK`

- [ ] **Step 3: 提交**

```bash
git add kuick_pic/annotations.py
git commit -m "feat: add annotations module with LineAnnotation and ArrowAnnotation dataclasses"
```

---

### Task 2: 添加共享 Cairo 渲染函数到 `annotations.py`

**文件:** 修改 `kuick_pic/annotations.py`

- [ ] **Step 1: 追加渲染函数**

在文件末尾追加：

```python
import math


_TEXT_FONT = "Sans 20"
_TEXT_PADDING_X = 8
_TEXT_PADDING_Y = 6
_ARROW_ANGLE = math.radians(22.5)
_ARROW_LENGTH = 12

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


def _draw_arrowhead(cr, tip, tail, color, origin_x, origin_y) -> None:
    """在 tip 处绘制八字形开口箭头（两条短线，不填充）。"""
    import math
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
```

- [ ] **Step 2: 验证导入**

```bash
uv run python -c "from kuick_pic.annotations import render_annotations, draw_line_preview, draw_arrow_preview; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add kuick_pic/annotations.py
git commit -m "feat: add shared Cairo rendering functions for all annotation types"
```

---

### Task 3: 更新 `area_selector.py` — 用 import 替换本地 dataclass

**文件:** 修改 `kuick_pic/area_selector.py`

- [ ] **Step 1: 删除本地 dataclass 定义（第 10-28 行），替换为 import**

删除第 10-28 行的 `SelectionResult`、`RectangleAnnotation`、`TextAnnotation` 三个 dataclass 定义。

在第 11 行位置插入：

```python
from kuick_pic.annotations import SelectionResult, RectangleAnnotation, TextAnnotation, LineAnnotation, ArrowAnnotation
```

- [ ] **Step 2: 更新类型注解**

第 69 行，将：
```python
self._annotations: list[RectangleAnnotation | TextAnnotation] = []
```
改为：
```python
self._annotations: list[RectangleAnnotation | TextAnnotation | LineAnnotation | ArrowAnnotation] = []
```

- [ ] **Step 3: 验证**

```bash
uv run python -c "from kuick_pic.area_selector import AreaSelector; print('OK')"
```

- [ ] **Step 4: 提交**

```bash
git add kuick_pic/area_selector.py
git commit -m "refactor: replace local annotation dataclasses with imports from annotations module"
```

---

### Task 4: 更新 `screenshot.py` — 用共享渲染函数替换重复代码

**文件:** 修改 `kuick_pic/screenshot.py`

- [ ] **Step 1: 替换 import**

第 67 行，将：
```python
from kuick_pic.area_selector import RectangleAnnotation, TextAnnotation
```
改为：
```python
from kuick_pic.annotations import render_annotations
```

- [ ] **Step 2: 替换 `_apply_annotations` 方法体（第 63-92 行）**

```python
@staticmethod
def _apply_annotations(image, annotations) -> None:
    import cairo
    from PIL import Image

    image_rgba = image.convert("RGBA")
    raw = bytearray(image_rgba.tobytes("raw", "BGRA"))
    width, height = image_rgba.size
    surface = cairo.ImageSurface.create_for_data(raw, cairo.FORMAT_ARGB32, width, height)
    cr = cairo.Context(surface)

    render_annotations(cr, annotations, origin_x=0, origin_y=0)

    surface.flush()
    rendered = Image.frombuffer("RGBA", (width, height), bytes(raw), "raw", "BGRA", 0, 1)
    image.paste(rendered)
```

- [ ] **Step 3: 删除 `_draw_text_annotation` 静态方法（第 94-115 行）**

删除整段。

- [ ] **Step 4: 验证**

```bash
uv run python -c "from kuick_pic.screenshot import ScreenshotCapture; print('OK')"
```

- [ ] **Step 5: 提交**

```bash
git add kuick_pic/screenshot.py
git commit -m "refactor: use shared render_annotations in screenshot.py"
```

---

### Task 5: 添加 i18n key

**文件:** 修改 `kuick_pic/locales/en.json`、`kuick_pic/locales/zh-CN.json`

- [ ] **Step 1: 添加英文 key**

`en.json`，第 28 行 `"selector.add_text": "Add text",` 后添加：

```json
"selector.draw_line": "Draw line",
"selector.draw_arrow": "Draw arrow",
```

- [ ] **Step 2: 添加中文 key**

`zh-CN.json`，第 28 行 `"selector.add_text": "添加文字",` 后添加：

```json
"selector.draw_line": "画线",
"selector.draw_arrow": "画箭头",
```

- [ ] **Step 3: 验证**

```bash
uv run python -c "
import json
json.load(open('kuick_pic/locales/en.json'))
json.load(open('kuick_pic/locales/zh-CN.json'))
print('OK')
"
```

- [ ] **Step 4: 提交**

```bash
git add kuick_pic/locales/en.json kuick_pic/locales/zh-CN.json
git commit -m "feat: add i18n keys for line and arrow tools"
```

---

### Task 6: 添加直线/箭头切换按钮到工具栏

**文件:** 修改 `kuick_pic/area_selector.py`

- [ ] **Step 1: 在 `__init__` 属性声明块中添加成员变量**

在第 81 行 `self._text_button = None` 后添加：

```python
self._line_button = None
self._line_button_label = None
self._arrow_button = None
self._arrow_button_label = None
```

- [ ] **Step 2: 创建按钮**

在第 213 行 `text_button, text_button_label_ = _make_tool_button(...)` 后添加：

```python
line_button, line_button_label = _make_tool_button("╱", "selector.draw_line", toggle=True)
arrow_button, arrow_button_label = _make_tool_button("→", "selector.draw_arrow", toggle=True)
```

- [ ] **Step 3: 连接信号**

在第 220 行 `text_button.connect("toggled", self._on_tool_toggled, "text")` 后添加：

```python
line_button.connect("toggled", self._on_tool_toggled, "line")
arrow_button.connect("toggled", self._on_tool_toggled, "arrow")
```

- [ ] **Step 4: 连接 active-class 切换**

在第 235 行 `text_button.connect("toggled", lambda b: _toggle_active_class(b))` 后添加：

```python
line_button.connect("toggled", lambda b: _toggle_active_class(b))
arrow_button.connect("toggled", lambda b: _toggle_active_class(b))
```

- [ ] **Step 5: 装入工具栏**

在第 239 行 `toolbar.pack_start(text_button, False, False, 0)` 后添加：

```python
toolbar.pack_start(line_button, False, False, 0)
toolbar.pack_start(arrow_button, False, False, 0)
```

- [ ] **Step 6: 存储引用**

在第 317 行 `self._text_button = text_button` 后添加：

```python
self._line_button = line_button
self._line_button_label = line_button_label
self._arrow_button = arrow_button
self._arrow_button_label = arrow_button_label
```

- [ ] **Step 7: 验证**

```bash
uv run python -c "from kuick_pic.area_selector import AreaSelector; a = AreaSelector(); print(hasattr(a, '_line_button'))"
```

预期: `True`

- [ ] **Step 8: 提交**

```bash
git add kuick_pic/area_selector.py
git commit -m "feat: add line and arrow toggle buttons to toolbar"
```

---

### Task 7: 更新 `_on_tool_toggled` 为 4 选 1 互斥

**文件:** 修改 `kuick_pic/area_selector.py` — `_on_tool_toggled` 方法（第 557-566 行）

- [ ] **Step 1: 替换方法体**

```python
def _on_tool_toggled(self, button, tool_name: str) -> None:
    if button.get_active():
        all_tool_buttons = {
            "box": self._box_button,
            "text": self._text_button,
            "line": self._line_button,
            "arrow": self._arrow_button,
        }
        for name, btn in all_tool_buttons.items():
            if name != tool_name and btn is not None and btn.get_active():
                btn.set_active(False)
        self._set_active_tool(tool_name)
    elif self._active_tool == tool_name:
        if tool_name == "text":
            self._hide_text_editor()
        self._set_active_tool(None)
```

- [ ] **Step 2: 验证**

```bash
uv run python -c "from kuick_pic.area_selector import AreaSelector; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add kuick_pic/area_selector.py
git commit -m "feat: support 4-way mutual exclusion for tool toggle buttons"
```

---

### Task 8: 添加直线/箭头手势处理

**文件:** 修改 `kuick_pic/area_selector.py`

- [ ] **Step 1: 在 `_on_button_press` 中添加 line/arrow elif**

在第 460 行（text tool 的 elif 结束后，`return False` 之前）插入：

```python
elif event.button == 1 and self._active_tool in ("line", "arrow") and self._point_in_selection(event.x, event.y):
    self._dragging = True
    self._gesture_kind = self._active_tool
    self._start_x = event.x
    self._start_y = event.y
    self._end_x = event.x
    self._end_y = event.y
    widget.queue_draw()
```

- [ ] **Step 2: 在 `_on_button_release` 中添加 line/arrow 提交逻辑**

在第 519 行（text 提交块的 `elif` 结束后，`selection-` 处理之前）插入：

```python
elif self._gesture_kind == "line":
    annotation = self._relative_line_within_selection(
        (self._start_x, self._start_y),
        (self._end_x, self._end_y),
    )
    if annotation is not None:
        self._annotations.append(annotation)
elif self._gesture_kind == "arrow":
    annotation = self._relative_arrow_within_selection(
        (self._start_x, self._start_y),
        (self._end_x, self._end_y),
    )
    if annotation is not None:
        self._annotations.append(annotation)
```

- [ ] **Step 3: 添加 line/arrow 的短拖拽过滤**

在第 496 行 `widget.queue_draw()` 之后、`if self._gesture_kind == "select":` 之前插入：

```python
if self._gesture_kind in ("line", "arrow"):
    dx = abs(self._end_x - self._start_x)
    dy = abs(self._end_y - self._start_y)
    if dx < 4 and dy < 4:
        self._dragging = False
        self._gesture_kind = None
        self._update_idle_cursor(event.x, event.y)
        widget.queue_draw()
        return
```

- [ ] **Step 4: 添加坐标夹紧辅助方法**

在 `_relative_rect_within_selection` 方法附近（第 666 行后）添加：

```python
def _relative_line_within_selection(
    self,
    start_abs: tuple[float, float],
    end_abs: tuple[float, float],
) -> LineAnnotation | None:
    if self._selection_rect is None:
        return None
    sx, sy, sw, sh = self._selection_rect
    x1 = max(sx, min(start_abs[0], sx + sw))
    y1 = max(sy, min(start_abs[1], sy + sh))
    x2 = max(sx, min(end_abs[0], sx + sw))
    y2 = max(sy, min(end_abs[1], sy + sh))
    if int(x1) == int(x2) and int(y1) == int(y2):
        return None
    return LineAnnotation(
        start=(int(x1 - sx), int(y1 - sy)),
        end=(int(x2 - sx), int(y2 - sy)),
        color=self._selected_color(),
    )

def _relative_arrow_within_selection(
    self,
    start_abs: tuple[float, float],
    end_abs: tuple[float, float],
) -> ArrowAnnotation | None:
    if self._selection_rect is None:
        return None
    sx, sy, sw, sh = self._selection_rect
    x1 = max(sx, min(start_abs[0], sx + sw))
    y1 = max(sy, min(start_abs[1], sy + sh))
    x2 = max(sx, min(end_abs[0], sx + sw))
    y2 = max(sy, min(end_abs[1], sy + sh))
    if int(x1) == int(x2) and int(y1) == int(y2):
        return None
    return ArrowAnnotation(
        start=(int(x1 - sx), int(y1 - sy)),
        end=(int(x2 - sx), int(y2 - sy)),
        color=self._selected_color(),
    )
```

- [ ] **Step 5: 验证**

```bash
uv run python -c "from kuick_pic.area_selector import AreaSelector; a = AreaSelector(); print(hasattr(a, '_relative_line_within_selection'))"
```

预期: `True`

- [ ] **Step 6: 提交**

```bash
git add kuick_pic/area_selector.py
git commit -m "feat: add line and arrow gesture handling"
```

---

### Task 9: 添加拖拽预览到 `_on_draw_overlay`

**文件:** 修改 `kuick_pic/area_selector.py` — `_on_draw_overlay` 方法

- [ ] **Step 1: 在 `_pending_text_rect` 预览块（第 425 行后）添加 line/arrow 预览**

```python
if self._dragging and self._gesture_kind == "line" and self._selection_rect is not None:
    sx, sy, _, _ = self._selection_rect
    start_rel = (int(self._start_x - sx), int(self._start_y - sy))
    end_rel = (int(self._end_x - sx), int(self._end_y - sy))
    from kuick_pic.annotations import draw_line_preview
    draw_line_preview(cr, start_rel, end_rel, self._selected_color(), sx, sy, dashed=True)

if self._dragging and self._gesture_kind == "arrow" and self._selection_rect is not None:
    sx, sy, _, _ = self._selection_rect
    start_rel = (int(self._start_x - sx), int(self._start_y - sy))
    end_rel = (int(self._end_x - sx), int(self._end_y - sy))
    from kuick_pic.annotations import draw_arrow_preview
    draw_arrow_preview(cr, start_rel, end_rel, self._selected_color(), sx, sy, dashed=True)
```

- [ ] **Step 2: 验证**

```bash
uv run python -c "from kuick_pic.area_selector import AreaSelector; print('OK')"
```

- [ ] **Step 3: 提交**

```bash
git add kuick_pic/area_selector.py
git commit -m "feat: add line and arrow drag preview rendering"
```

---

### Task 10: 十字光标与拖拽区域更新

**文件:** 修改 `kuick_pic/area_selector.py`

- [ ] **Step 1: `_update_idle_cursor`（第 791 行）**

将：
```python
if self._active_tool == "box":
```
改为：
```python
if self._active_tool in ("box", "line", "arrow"):
```

- [ ] **Step 2: `_set_active_tool`（第 874 行）**

将：
```python
cursor_name = "crosshair" if tool_name == "box" else None
```
改为：
```python
cursor_name = "crosshair" if tool_name in ("box", "line", "arrow") else None
```

- [ ] **Step 3: `_drag_preview_screen_rect`（第 691 行）添加 line/arrow 分支**

在第 705 行 text 处理后添加：

```python
if gesture_kind in ("line", "arrow"):
    if self._selection_rect is None:
        return None
    x1 = min(self._start_x, self._end_x)
    y1 = min(self._start_y, self._end_y)
    x2 = max(self._start_x, self._end_x)
    y2 = max(self._start_y, self._end_y)
    return (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
```

- [ ] **Step 4: 验证**

```bash
uv run python -c "from kuick_pic.area_selector import AreaSelector; print('OK')"
```

- [ ] **Step 5: 提交**

```bash
git add kuick_pic/area_selector.py
git commit -m "feat: crosshair cursor and redraw regions for line/arrow tools"
```

---

### Task 11: 将 `_draw_annotations` 替换为共享渲染器

**文件:** 修改 `kuick_pic/area_selector.py`

- [ ] **Step 1: 替换 `_draw_annotations` 方法体（第 684-689 行）**

```python
def _draw_annotations(self, cr) -> None:
    if self._selection_rect is None:
        return
    sx, sy, _, _ = self._selection_rect
    from kuick_pic.annotations import render_annotations
    render_annotations(cr, self._annotations, origin_x=sx, origin_y=sy)
```

- [ ] **Step 2: 更新 `_on_draw_overlay` 中的矩形预览调用**

第 409 行，将：
```python
self._draw_rectangle_annotation(
    cr,
    RectangleAnnotation(
        rect=preview_rect,
        color=self._selected_color(),
    ),
    dashed=True,
)
```
改为带 sx, sy 的调用（`_on_draw_overlay` 中第 380 行已有 `sx, sy`）：

```python
from kuick_pic.annotations import _draw_rectangle_annotation as _dra
_dra(cr, RectangleAnnotation(rect=preview_rect, color=self._selected_color()), sx, sy, dashed=True)
```

第 418 行，将：
```python
self._draw_rectangle_annotation(
    cr,
    RectangleAnnotation(
        rect=self._pending_text_rect,
        color=self._selected_color(),
    ),
    dashed=True,
)
```
改为：
```python
from kuick_pic.annotations import _draw_rectangle_annotation as _dra
_dra(cr, RectangleAnnotation(rect=self._pending_text_rect, color=self._selected_color()), sx, sy, dashed=True)
```

- [ ] **Step 3: 删除私有绘制方法**

删除 `_draw_rectangle_annotation`（第 818-831 行）和 `_draw_text_annotation`（第 833-855 行）。

- [ ] **Step 4: 验证**

```bash
uv run python -c "from kuick_pic.area_selector import AreaSelector; print('OK')"
```

- [ ] **Step 5: 提交**

```bash
git add kuick_pic/area_selector.py
git commit -m "refactor: use shared render_annotations in area_selector's _draw_annotations"
```

---

### Task 12: 编写测试

**文件:** 创建 `tests/test_annotations.py`

- [ ] **Step 1: 创建测试文件**

```python
import cairo
import pytest
from kuick_pic.annotations import (
    LineAnnotation,
    ArrowAnnotation,
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
```

- [ ] **Step 2: 运行测试**

```bash
uv run pytest tests/test_annotations.py -v
```

预期: 全部 PASS

- [ ] **Step 3: 提交**

```bash
git add tests/test_annotations.py
git commit -m "test: add tests for annotation dataclasses and rendering"
```

---

### Task 13: 全量验证

- [ ] **Step 1: 运行全部测试**

```bash
uv run pytest tests/ -v
```

- [ ] **Step 2: 验证完整导入链**

```bash
uv run python -c "from kuick_pic.app import KuickPicApp; print('OK')"
```

- [ ] **Step 3: 验证 i18n**

```bash
uv run python -c "from kuick_pic.i18n import t; print(t('selector.draw_line')); print(t('selector.draw_arrow'))"
```

预期: `画线` / `画箭头`

- [ ] **Step 4: 提交（如有未提交内容）**

```bash
git status
```

---

## 验证总结

```bash
# 每步代码改动后:
uv run python -c "..."           # 导入检查

# Task 12 后:
uv run pytest tests/test_annotations.py -v

# 最终:
uv run pytest tests/ -v
uv run python -c "from kuick_pic.app import KuickPicApp; print('OK')"
uv run python -c "from kuick_pic.i18n import t; print(t('selector.draw_line'), t('selector.draw_arrow'))"
```

手动验证: 启动应用，截图后确认 4 个工具（画框、文字、直线、箭头）互斥切换正常，拖拽绘制含虚线预览，松开后渲染正确，撤销功能正常，最终保存的图片包含所有标注。
