# 直线与箭头标注工具

## 概述

在截图标注系统中新增两个绘图工具：无箭头直线和带箭头直线。

## 设计

### 数据模型（`area_selector.py`）

新增两个 frozen dataclass，与 `RectangleAnnotation` / `TextAnnotation` 同级：

```python
@dataclass(frozen=True)
class LineAnnotation:
    start: tuple[int, int]     # (x, y) 起点，相对于选区
    end: tuple[int, int]       # (x, y) 终点，相对于选区
    color: tuple[int, int, int]

@dataclass(frozen=True)
class ArrowAnnotation:
    start: tuple[int, int]
    end: tuple[int, int]
    color: tuple[int, int, int]
```

两者结构相同，但类型不同，以便渲染时分派到各自的绘制逻辑。

### 工具栏按钮

新增两个切换按钮，与 `box`、`text` 及彼此之间互斥：

- `—` 直线（i18n key: `selector.draw_line`）
- `→` 箭头（i18n key: `selector.draw_arrow`）

### 交互（按下拖拽 → 释放）

与现有矩形/文字工具一致：
- 在选区内按下鼠标 → 开始手势
- 拖拽 → 虚线预览从起点到当前光标位置
- 释放 → 将 `LineAnnotation` 或 `ArrowAnnotation` 提交到 `self._annotations`

两个工具分别将 `self._gesture_kind` 设为 `"line"` 或 `"arrow"`，用 `self._gesture_start` 记录起点。

### 光标

进入直线或箭头模式后，鼠标在选区内时显示十字光标。

### Cairo 渲染（`area_selector.py`）

**预览（拖拽中）：**
- 从起点到当前鼠标位置的虚线
- 宽度 2px，颜色为用户所选色

**最终直线：**
- 实线，宽度 3px

**最终箭头：**
- 同上实线
- 终点处添加八字形开口箭头（V 形）：
  - 从终点向后方延伸两条 12px 短线
  - 展开角度：偏离线方向 ±22.5°（总开口 45°）
  - 颜色和线宽与直线一致

### 最终图片渲染（`screenshot.py`）

`_apply_annotations()` 新增两个 `isinstance` 分支处理 `LineAnnotation` 和 `ArrowAnnotation`，逻辑与 `area_selector.py` 中的绘制一致。箭头方向通过 `atan2` 计算，然后沿直线方向向后偏移。

### 撤销

通过现有的 `_on_undo`（弹出最后一条标注）自动支持。`LineAnnotation` 和 `ArrowAnnotation` 与其他标注同在一个列表中。

### i18n

| Key | en | zh-CN |
|---|---|---|
| `selector.draw_line` | Draw Line | 直线 |
| `selector.draw_arrow` | Draw Arrow | 箭头 |

### 涉及文件

| 文件 | 改动 |
|---|---|
| `quick_pic/area_selector.py` | 新增 dataclass、按钮、手势处理、Cairo 绘制方法 |
| `quick_pic/screenshot.py` | `_apply_annotations` 新增直线/箭头渲染分支 |
| `quick_pic/locales/en.json` | 两个新 key |
| `quick_pic/locales/zh-CN.json` | 两个新 key |

### 不纳入范围

- 箭头样式可配置（固定在八字开口 V 形）
- 线宽可配置（固定 3px）
- 自由绘制/铅笔工具
- 其他图形（圆、椭圆等）
