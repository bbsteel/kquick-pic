# 工具栏图标对齐问题：排查与进展记录

## 背景

kquick-pic 截图工具的区域选择器（`area_selector.py`）在用户选区完成后，会在画面底部显示一排工具栏按钮（画框、添加文字、画线、画箭头、数字印章、选择颜色、撤销、确认、取消）。

用户反馈工具栏"参差不齐"——各按钮在视觉上高低不一、整体凌乱。

---

## 根本原因分析

工具栏按钮由 `_make_tool_button()` 统一构建，每个按钮内部结构是：

```
Gtk.Button
└── Gtk.Box (vertical)
    ├── Gtk.Label (icon_text, class=qp-tool-icon)
    └── Gtk.Label (text, class=qp-tool-text)
```

CSS 设置了 `min-height: 52px`，看起来高度应该一致，但实际存在两个独立问题：

### 问题 1：按钮内容高度不一致（已解决）

`box.pack_start(icon_label, False, False, 0)` 不扩展、不填充，图标 Label 只占自然高度。不同 Unicode 字符（□、T、●、①……）的字形在同一字号下自然像素高度不同，导致图标行高各异，进而使图标行和文字行组成的整体在按钮内的位置不同，视觉上看起来高低错落。

### 问题 2：图标视觉尺寸差异（未完全解决）

即使行高对齐，不同字符的视觉大小差距仍然显著：

- `●`（实心圆）视觉上远大于 `□`（空心方框）
- `→`（横向箭头）ink 高度极小（箭头很扁），若用高度规一化会被放大到异常大

这两个问题性质不同，第一个可通过布局约束解决，第二个与 Unicode 字符形状的根本差异有关。

---

## 解决过程

### 尝试 1：wrapper-box 固定高度（有效，当前状态）

给每个图标 Label 外套一个固定高度的容器，强制所有图标区域高度一致：

```python
icon_wrapper = self._Gtk.Box()
icon_wrapper.set_size_request(-1, 26)  # 固定 26px 高
icon_wrapper.pack_start(icon_label, True, True, 0)  # 图标在容器内居中展开
```

同时对图标 Label 和整体 Box 设置垂直居中：

```python
icon_label.set_valign(self._Gtk.Align.CENTER)
icon_label.set_halign(self._Gtk.Align.CENTER)
box.set_valign(self._Gtk.Align.CENTER)
```

**结果**：按钮行高对齐问题解决（问题 1 修复），但各图标视觉大小仍有差距。

---

### 尝试 2：逐图标手动调字号（效果有限，已回退）

对每个字符单独设定 Pango 字号，以目测的方式让视觉尺寸接近：

```python
_make_tool_button("□", ..., icon_size=20)
_make_tool_button("●", ..., icon_size=12)  # 实心圆字号缩小
# ...
```

**问题**：

1. 硬编码，加新图标就要手动再调一次
2. 调试结果依赖字体渲染环境，不同系统可能表现不同

用户指出这不是好的抽象，要求改进。

---

### 尝试 3：Cairo + Pango 自动测量墨水高度（失败，已回退）

自动测量每个字符在 100pt 下的 ink height，反推让它等于目标像素高的字号：

```python
def _icon_font_size_pt(icon_text, target_px=18):
    probe = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 600)
    ctx = cairo.Context(probe)
    layout = self._PangoCairo.create_layout(ctx)
    layout.set_text(icon_text, -1)
    layout.set_font_description(self._Pango.FontDescription("Sans 100"))
    ink, _ = layout.get_pixel_extents()
    h = max(ink.height, 1)
    pt = round(100 * target_px / h)
    return max(6, min(48, pt))
```

**失败原因**：

对宽扁字符（`→`）墨水高度极小（箭头轴线很细），公式把字号放大到上限（48pt），导致 `→` 在工具栏里异常巨大；而 `□` 墨水高度大，字号算出来反而小。效果比手动调还差。

**根本问题**：用 ink height 单一维度规一化，对宽高比差异悬殊的字符完全不适用。没有任何一个通用几何指标能覆盖所有 Unicode 字符类型（正方形、横向箭头、字母、数字圆圈……）。

---

## 当前状态

代码停留在**尝试 1（wrapper-box）** 状态：

- 按钮行高对齐 ✓
- 图标字号统一 17px（CSS）
- 各图标视觉大小有差距，但按钮整体不再凌乱

相关代码位置：`kquick_pic/area_selector.py`，函数 `_make_tool_button()`（在 `_setup_overlay()` 内部）。

---

## 未解决问题

图标视觉尺寸均等化**没有基于文本字符的可靠方案**。

根因：Unicode 字符的视觉大小由字形设计决定，同一字号下 `●` 就是比 `□` 视觉上大，`→` 就是扁而宽，这是字体本身的设计，无法在渲染层自动补偿。

---

## 正确的长期解法

放弃 Unicode 文本字符作为图标的方案，改为以下两种之一：

### 方案 A：Gtk.DrawingArea + Cairo 自绘

为每种工具类型编写 Cairo 绘制函数（矩形轮廓、实心圆、箭头线、T 字形等），所有图标在同一个固定像素框（如 20×20）内绘制，天然尺寸一致。

优点：像素级精确，支持主题色，无需字体依赖。  
缺点：每个图标类型都要写绘制代码，工作量较大，约 200-300 行。

### 方案 B：嵌入 SVG/PNG 图标

使用 `Gtk.Image.new_from_pixbuf()` 加载固定尺寸（如 20×20）的图标图片，图标文件统一放在 `kquick_pic/icons/` 目录。

优点：最简单、最可靠。  
缺点：需要图标素材；主题色跟随（active 状态变蓝）需要对 SVG 做额外处理或切两套图。
