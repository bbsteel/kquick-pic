# Kuick Pic (`kuick-pic`)

KDE/Plasma 向的个人快速截图工具：托盘常驻 + 全局热键 + 区域选择 + 保存/钉住 + 路径入剪贴板。  
非官方 KDE 项目。Python 包：`kuick_pic`。

## 运行

```bash
uv run python -m kuick_pic
```

venv 必须用系统 Python 3.13 创建（`--system-site-packages`），因为 GTK3 / PyGObject / dbus-python 是系统包，无法通过 pip 安装：

```bash
uv venv --system-site-packages --python python3.13
uv sync
```

## 安装 / 分发

### 本地安装桌面启动器

```bash
./scripts/install.sh
```

安装脚本会：

1. 用系统 Python 3.13 创建 `.venv`
2. 执行 `uv sync --frozen`
3. 安装 `~/.local/share/applications/kuick-pic.desktop`
4. 安装桌面图标 `~/.local/share/icons/hicolor/256x256/apps/kuick-pic.png`

卸载桌面集成：

```bash
./scripts/uninstall.sh
```

### 打源码分发包

```bash
./scripts/package-release.sh
```

输出：

```bash
dist/kuick-pic-0.1.0.tar.gz
```

把这个 tar.gz 发给另一个 Linux 用户后，对方解压并执行：

```bash
./scripts/install.sh
```

### 额外说明

- 分发目标仍然需要系统层依赖：`python3.13`、GTK3 / PyGObject、`dbus-python`
- 自启动由应用内设置控制，写入 `~/.config/autostart/kuick-pic.desktop`
- 多语言插件可放在 `kuick_pic/locales/*.json` 或 `~/.config/kuick-pic/locales/*.json`

## 技术栈

| 层 | 选型 |
|---|---|
| 截屏 | `mss` (X11 全屏/区域) |
| 区域选择 UI | GTK3 Overlay (截图背景 + 半透明遮罩 + 选区镂空) |
| 剪贴板 | `Gtk.Clipboard` (写入路径文本，非图像) |
| 托盘 | 原生 D-Bus `org.kde.StatusNotifierItem` (非 pystray/AyatanaAppIndicator3) |
| 热键 | `pynput` (XRecord) |
| 配置 | JSON (`~/.config/kuick-pic/config.json`) |

## 线程模型

```
主线程 = Gtk.main() (阻塞)
  ├── 托盘 D-Bus 回调 (GLib 集成)
  ├── 托盘菜单回调
  └── GLib.idle_add() 剪贴板写入

热键线程 = pynput daemon
  └── _on_screenshot_triggered() → GLib.idle_add 回主线程

区域选择 Worker 线程 (托盘菜单触发时从主线程 fork)
  └── 截图 I/O → GLib.idle_add 剪贴板
```

关键约束：所有 GTK 操作（剪贴板、菜单）必须通过 `GLib.idle_add()` 调度到主线程。

## 项目结构

```
kuick_pic/
├── app.py              # KuickPicApp 生命周期编排
├── config.py           # AppConfig dataclass + ConfigManager (JSON)
├── screenshot.py       # ScreenshotCapture: capture_fullscreen / capture_area
├── area_selector.py    # GTK3 全屏叠加层：拖拽选区 (Overlay: Image + DrawingArea)
├── pin.py              # 钉住窗口 PinManager
├── clipboard.py        # ClipboardManager: set_path (主线程) / set_path_async (任意线程)
├── hotkey.py           # HotkeyManager: pynput / KGlobalAccel
├── tray.py             # TrayManager: 原生 D-Bus StatusNotifierItem
├── settings_dialog.py  # GTK3 设置对话框 (路径/格式/热键)
├── icon.py             # generate_icon() 程序化图标 (Pillow RGBA)
├── __main__.py         # 入口: SIGINT/SIGTERM → shutdown()
└── __init__.py
```

## 关键设计决策

### 为什么要自己实现 D-Bus StatusNotifierItem

pystray 默认用 `Gtk.StatusIcon` (XEmbed 协议)，KDE Plasma 5+ 已弃用。尝试 AyatanaAppIndicator3 但无法拦截左键点击（Activate 行为硬编码为显示菜单）。

最终方案：直接用 `dbus.service.Object` 实现 `org.kde.StatusNotifierItem` 接口，完全控制 Activate（左键直接截屏）和 ContextMenu（右键弹出 GTK 菜单）。

### 托盘图标如何暴露

现在托盘图标以 `IconPixmap` 为主，并且按 SNI 常见实现方式提供完整 introspection：

- `IconPixmap`：直接通过 D-Bus 提供 ARGB32 像素数据
- `IconName` / `IconThemePath`：留空，避免 KDE 把找不到的主题图标名渲染成占位图
- `Introspect`：显式声明 `org.kde.StatusNotifierItem` 的属性 / 方法 / 信号
- `Menu`：通过 `com.canonical.dbusmenu` 暴露托盘菜单
- 图标切换时会重建 SNI 对象，并发 `NewIcon` / `NewToolTip` / `PropertiesChanged`，再重新向 watcher 注册
- 对象路径使用 `/StatusNotifierItem`

区域截图不再依赖外部截图工具。当前流程是：

1. 先用 `mss` 抓一张全屏底图
2. 用单个 GTK `DrawingArea` 直接绘制底图、外部遮罩、选区边框和标注预览
3. 鼠标释放后显示工具栏，可添加线框、文字、线框颜色，并手动确认
4. 确认后直接裁剪这张底图并落盘，同时把标注绘制到最终图片上

这样不会再因为“选区窗口刚消失就重新抓屏”而截出黑图。

### mss 区域截屏

`mss.shot(mon=dict)` 不接受字典参数。必须用 `mss.grab(region_dict)` + `mss.tools.to_png()` 组合来保存区域截图。

### 区域选择器架构

用 `Gtk.Overlay` 分两层避免拖动闪烁：
- 底层: `Gtk.Image` (静态截图背景，从不重绘)
- 上层: `Gtk.DrawingArea` (半透明遮罩 + 镂空选区，仅在拖拽时重绘)

## 配置

`~/.config/kuick-pic/config.json`：
```json
{
  "save_path": "~/Pictures/kuick-pic",
  "format": "png",
  "hotkey": "<ctrl>+<shift>+p",
  "icon_theme": "v1",
  "autostart": false,
  "language": "zh-CN"
}
```

- format 仅支持 png/jpg
- hotkey 格式为 pynput 的 `<mod>+<mod>+<key>` 格式
- 配置文件损坏/缺失时自动写回默认值
