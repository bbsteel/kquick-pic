# Quick Pic

Quick Pic 是一个面向特定 Linux 桌面环境的快速截图工具，目标是提供**比系统自带截图工具更轻、更快、更适合常驻使用**的体验。

它的核心场景是：

- 托盘常驻
- 全局快捷键触发
- 区域截图
- 截图后即时标注
- 自动保存并把文件路径写入剪贴板

## 功能概览

- 托盘图标 + 右键菜单
- 全局快捷键截图
- 区域框选、拖动、缩放
- 线框标注
- 文本标注
- 自动保存到本地目录
- 自启动开关
- 中英文界面
- 插件式语言包扩展

## 平台支持范围

Quick Pic 不是跨平台截图方案，也不是通用 Linux 包。当前实现主要面向：

- Linux 桌面环境
- X11 图形会话
- GTK3 / PyGObject 可用的发行版环境
- 支持 D-Bus `org.kde.StatusNotifierItem` 托盘协议的桌面环境
- 有 compositor / RGBA visual 支持的窗口管理环境

这些场景目前不保证可用：

- Windows / macOS
- Wayland 会话
- headless 服务器、容器、CI
- 没有系统托盘或不支持 StatusNotifierItem 的桌面环境
- 禁止全局热键、屏幕截图或透明全屏窗口的受限桌面/沙箱环境

Wayland 下尤其容易受到桌面安全策略限制：全局热键、全屏截图、窗口覆盖层和托盘行为都可能不可用、需要额外授权，或只能通过 xdg-desktop-portal 等平台 API 重新适配。

## 运行环境

当前项目面向 Linux 桌面环境，主要假设：

- X11 会话
- GTK3 可用
- D-Bus 可用
- 系统已安装 PyGObject / `dbus-python`
- 可用的系统托盘实现支持 `org.kde.StatusNotifierItem`
- 桌面允许 `pynput` / XRecord 监听全局热键
- `mss` 能读取屏幕内容
- compositor 支持透明全屏选区窗口；不支持时遮罩效果可能退化

## 安装

### 方式一：从源码目录直接安装

这是最推荐的安装方式。

```bash
./scripts/install.sh
```

安装脚本会自动完成这些事情：

1. 用系统 Python 3.13 创建 `.venv`
2. 执行 `uv sync --frozen`
3. 安装桌面启动器到 `~/.local/share/applications/quick-pic.desktop`
4. 安装桌面图标到 `~/.local/share/icons/hicolor/256x256/apps/quick-pic.png`

### 方式二：手动运行开发版本

如果你只是本地开发或调试：

```bash
uv venv --system-site-packages --python python3.13
uv sync
uv run python -m quick_pic
```

## 依赖要求

运行前需要这些基础依赖：

- `uv`
- `python3.13`
- GTK3 / PyGObject
- `dbus-python`

之所以必须使用 `--system-site-packages`，是因为 GTK3 / PyGObject / `dbus-python` 通常来自系统包，而不是 pip。

## 分发给别人

### 方式一：构建单体可执行程序（推荐）

使用 PyInstaller 构建为独立二进制，无需 uv/Python 运行环境：

```bash
./scripts/build-binary.sh
```

构建产物位于 `dist/quick-pic/`，可直接运行：

```bash
./dist/quick-pic/quick-pic
```

打包为 tar.gz 分发给别人：

```bash
./scripts/package-binary.sh
# 输出: dist/quick-pic-0.1.0-linux-x86_64.tar.gz
```

对方解压即用，只需系统装有 GTK3/PyGObject/dbus-python（无需 uv/Python），并满足上面的 Linux 桌面环境前提：

```bash
tar -xzf quick-pic-0.1.0-linux-x86_64.tar.gz
cd quick-pic
./quick-pic
```

### 方式二：打源码分发包

```bash
./scripts/package-release.sh
```

输出文件：

```bash
dist/quick-pic-0.1.0.tar.gz
```

### 对方安装步骤

把 `dist/quick-pic-0.1.0.tar.gz` 发给对方后，对方执行：

```bash
tar -xzf quick-pic-0.1.0.tar.gz
cd quick-pic
./scripts/install.sh
```

## 卸载

移除桌面启动器、图标和自启动文件：

```bash
./scripts/uninstall.sh
```

## 配置

配置文件位置：

```bash
~/.config/quick-pic/config.json
```

示例：

```json
{
  "save_path": "~/Pictures/quick-pic",
  "format": "png",
  "hotkey": "<ctrl>+<shift>+p",
  "icon_theme": "v1",
  "autostart": false,
  "language": "zh-CN"
}
```

## 多语言

首批内置语言：

- `zh-CN`
- `en`

新增语言有两种方式：

1. 项目内置语言包：`quick_pic/locales/*.json`
2. 用户侧语言插件：`~/.config/quick-pic/locales/*.json`

每个语言文件都是一个 JSON 插件，至少包含：

- `code`
- `name`
- `messages`

## 入口命令

安装完成后可直接运行：

```bash
quick-pic
```

或：

```bash
python -m quick_pic
```
