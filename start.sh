#!/usr/bin/env bash
# KQuick Pic 统一入口：构建成品、安装到 ~/Applications、启动。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.13}"
VENV_DIR="$ROOT_DIR/.venv"
DIST_DIR="$ROOT_DIR/dist/kquick-pic"
BINARY_NAME="kquick-pic"
APP_INSTALL_DIR="${KQUICK_PIC_INSTALL_DIR:-$HOME/Applications/kquick-pic}"
PID_FILE="$HOME/.config/kquick-pic/kquick-pic.pid"
LOG_FILE="$HOME/.config/kquick-pic/kquick-pic.log"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
DESKTOP_FILE="$DESKTOP_DIR/kquick-pic.desktop"
ICON_FILE="$ICON_DIR/kquick-pic.png"
DEFAULT_ICON="$ROOT_DIR/kquick_pic/icons/kquick-pic-tray-v1.png"

usage() {
  cat <<EOF
用法: $(basename "$0") <命令>

命令:
  build         用 PyInstaller 构建成品到 dist/kquick-pic/
  install       将成品安装到 ~/Applications/kquick-pic（无成品时先 build）
  start         开发模式启动（默认）：venv + 安装 KWin 授权用 .desktop
  stop          停止正在运行的实例
  restart       停止后重新开发模式启动
  start-binary  启动已安装/dist 成品（会写入成品路径的 .desktop）
  help          显示本帮助

本机默认按开发态处理：start 不优先成品，避免 desktop Exec 与
/proc/self/exe 错位导致 KWin ScreenShot2 未授权、回退 Portal 弹跳。

环境变量:
  PYTHON_BIN              构建/开发用的 Python（默认 python3.13）
  KQUICK_PIC_INSTALL_DIR   安装目录（默认 \$HOME/Applications/kquick-pic）

示例:
  ./start.sh start
  ./start.sh restart
  ./start.sh build && ./start.sh install && ./start.sh start-binary
EOF
}

die() {
  echo "错误: $*" >&2
  exit 1
}

assert_safe_install_dir() {
  local dir="$1"
  # 只允许写到用户 Applications 下的 kquick-pic 目录，避免误删。
  case "$dir" in
    "$HOME/Applications/kquick-pic"|"$HOME/Applications/kquick-pic/")
      ;;
    *)
      # 允许覆盖 KQUICK_PIC_INSTALL_DIR，但必须仍落在 $HOME 且目录名以 kquick-pic 结尾
      if [[ "$dir" != "$HOME"/* ]] || [[ "$(basename "$dir")" != "kquick-pic" ]]; then
        die "拒绝使用不安全的安装目录: $dir（须在 \$HOME 下且目录名为 kquick-pic）"
      fi
      ;;
  esac
}

is_kquick_pic_pid() {
  local pid="$1"
  [[ -n "${pid:-}" && -d "/proc/$pid" ]] || return 1
  # cmdline 用 NUL 分隔；匹配 python -m kquick_pic / 成品 kquick-pic
  # （兼容旧进程名 quick_pic / quick-pic，便于改名后 stop）
  tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -qE 'k?quick[_-]pic'
}

is_running() {
  if [[ ! -f "$PID_FILE" ]]; then
    return 1
  fi
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if is_kquick_pic_pid "$pid"; then
    echo "$pid"
    return 0
  fi
  rm -f -- "$PID_FILE"
  return 1
}

stop_instance() {
  # 按 pid 文件优雅停止；陈旧 pid 文件则清理。不存在运行实例时返回 0。
  if [[ ! -f "$PID_FILE" ]]; then
    echo "KQuick Pic 未在运行（无 pid 文件）"
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if ! is_kquick_pic_pid "$pid"; then
    echo "陈旧 pid 文件，已移除"
    rm -f -- "$PID_FILE"
    return 0
  fi

  echo "停止 KQuick Pic（PID $pid）..."
  kill "$pid" 2>/dev/null || true
  local _
  for _ in $(seq 1 30); do
    if ! is_kquick_pic_pid "$pid"; then
      break
    fi
    sleep 0.1
  done
  if is_kquick_pic_pid "$pid"; then
    echo "强制结束 PID $pid..."
    kill -9 "$pid" 2>/dev/null || true
    sleep 0.1
  fi
  rm -f -- "$PID_FILE"
  echo "已停止"
}

cmd_build() {
  if [[ ! -x "$ROOT_DIR/scripts/build-binary.sh" ]]; then
    die "找不到构建脚本: $ROOT_DIR/scripts/build-binary.sh"
  fi
  echo "=== 构建 KQuick Pic 成品 ==="
  "$ROOT_DIR/scripts/build-binary.sh"
  if [[ ! -x "$DIST_DIR/$BINARY_NAME" ]]; then
    die "构建结束但未找到可执行文件: $DIST_DIR/$BINARY_NAME"
  fi
  echo "成品: $DIST_DIR/$BINARY_NAME"
}

install_desktop_entry() {
  local exec_path="$1"
  local work_dir="$2"
  local icon_src="$3"

  mkdir -p "$DESKTOP_DIR" "$ICON_DIR"
  if [[ -f "$icon_src" ]]; then
    cp -f "$icon_src" "$ICON_FILE"
  elif [[ -f "$DEFAULT_ICON" ]]; then
    cp -f "$DEFAULT_ICON" "$ICON_FILE"
  fi

  # KWin 通过 /proc/<pid>/exe 与 desktop Exec 第一参数的规范路径匹配，
  # 再读 X-KDE-DBUS-Restricted-Interfaces 授权 ScreenShot2。
  # 开发态 Exec 必须是 .venv/bin/python3（可保留 symlink），不能写成成品路径。
  cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=KQuick Pic
Comment=KDE/Plasma-oriented quick screenshot tool
Exec=$exec_path
Path=$work_dir
Icon=kquick-pic
Terminal=false
Categories=Utility;Graphics;
StartupNotify=false
X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2
EOF

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
  fi
  if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 >/dev/null 2>&1 || true
  fi
}

install_dev_desktop_entry() {
  # 与 scripts/install.sh 一致：venv python3 + -m kquick_pic。
  # 勿 resolve 掉 symlink，否则从菜单启动会绕过 venv。
  local py="$VENV_DIR/bin/python3"
  if [[ ! -x "$py" ]]; then
    die "开发态 desktop 需要 $py，请先创建 venv"
  fi
  install_desktop_entry "$py -m kquick_pic" "$ROOT_DIR" "$DEFAULT_ICON"
  echo "开发态 desktop: $DESKTOP_FILE"
  echo "  Exec 第一参数规范路径: $(readlink -f "$py")"
}

cmd_install() {
  assert_safe_install_dir "$APP_INSTALL_DIR"

  if [[ ! -x "$DIST_DIR/$BINARY_NAME" ]]; then
    echo "未找到构建产物，先执行 build..."
    cmd_build
  fi

  echo "=== 安装到 $APP_INSTALL_DIR ==="
  mkdir -p "$(dirname "$APP_INSTALL_DIR")"

  if [[ -e "$APP_INSTALL_DIR" ]]; then
    echo "移除旧安装: $APP_INSTALL_DIR"
    rm -rf -- "$APP_INSTALL_DIR"
  fi

  mkdir -p "$APP_INSTALL_DIR"
  cp -a "$DIST_DIR"/. "$APP_INSTALL_DIR"/
  chmod +x "$APP_INSTALL_DIR/$BINARY_NAME"

  local icon_src="$APP_INSTALL_DIR/_internal/kquick_pic/icons/kquick-pic-tray-v1.png"
  if [[ ! -f "$icon_src" ]]; then
    icon_src="$DEFAULT_ICON"
  fi
  install_desktop_entry \
    "$APP_INSTALL_DIR/$BINARY_NAME" \
    "$APP_INSTALL_DIR" \
    "$icon_src"

  echo "已安装: $APP_INSTALL_DIR/$BINARY_NAME"
  echo "桌面入口: $DESKTOP_FILE"
  echo "启动: ./start.sh start"
}

resolve_binary() {
  if [[ -x "$APP_INSTALL_DIR/$BINARY_NAME" ]]; then
    printf '%s\n' "$APP_INSTALL_DIR/$BINARY_NAME"
    return 0
  fi
  if [[ -x "$DIST_DIR/$BINARY_NAME" ]]; then
    printf '%s\n' "$DIST_DIR/$BINARY_NAME"
    return 0
  fi
  return 1
}

start_dev() {
  # --- 检查系统依赖 ---
  if ! "$PYTHON_BIN" -c "import gi, dbus" 2>/dev/null; then
    echo "缺少系统依赖，请先安装："
    echo "  Arch/SteamOS: sudo pacman -S python-gobject gtk3 python-dbus"
    echo "  Ubuntu/Debian: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-dbus"
    echo "  Fedora:        sudo dnf install python3-gobject gtk3 python3-dbus"
    exit 1
  fi

  if ! command -v uv >/dev/null 2>&1; then
    die "缺少 uv，请先安装：curl -Ls https://astral.sh/uv/install.sh | sh"
  fi

  if [[ -d "$VENV_DIR" ]]; then
    if ! "$VENV_DIR/bin/python" -c "import gi" 2>/dev/null; then
      echo "已有 venv 无法访问系统包，正在重建..."
      rm -rf -- "$VENV_DIR"
    fi
  fi

  if [[ ! -d "$VENV_DIR" ]]; then
    echo "创建 venv..."
    (cd "$ROOT_DIR" && uv venv --system-site-packages --python "$PYTHON_BIN")
  fi

  cd "$ROOT_DIR"
  uv sync --frozen -q

  # 每次开发启动都重写 desktop，防止 start-binary / 旧 install 残留成品 Exec。
  install_dev_desktop_entry

  mkdir -p "$(dirname "$PID_FILE")"
  echo "启动 KQuick Pic（开发模式）..."
  # 直接用 venv 解释器，保证 /proc/self/exe 与 desktop Exec 同一条 symlink 链。
  nohup "$VENV_DIR/bin/python3" -m kquick_pic >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "已启动（PID $(cat "$PID_FILE")），日志：$LOG_FILE"
}

cmd_start() {
  local running_pid
  if running_pid="$(is_running)"; then
    echo "KQuick Pic 已在运行（PID $running_pid）"
    echo "如需重启：$(basename "$0") restart"
    exit 0
  fi

  mkdir -p "$(dirname "$PID_FILE")"
  start_dev
}

cmd_stop() {
  stop_instance
}

cmd_restart() {
  stop_instance
  mkdir -p "$(dirname "$PID_FILE")"
  start_dev
}

cmd_start_binary() {
  local running_pid
  if running_pid="$(is_running)"; then
    echo "KQuick Pic 已在运行（PID $running_pid）"
    echo "如需重启：先 $(basename "$0") stop，再 $(basename "$0") start-binary"
    exit 0
  fi

  mkdir -p "$(dirname "$PID_FILE")"

  local bin=""
  if ! bin="$(resolve_binary)"; then
    die "未找到已安装或 dist 成品，请先 ./start.sh install，或用 ./start.sh start 开发模式"
  fi

  echo "启动成品: $bin"
  local icon_src
  icon_src="$(dirname "$bin")/_internal/kquick_pic/icons/kquick-pic-tray-v1.png"
  if [[ ! -f "$icon_src" ]]; then
    icon_src="$DEFAULT_ICON"
  fi
  # 成品路径写进 desktop，与二进制 /proc/self/exe 对齐。
  install_desktop_entry "$bin" "$(dirname "$bin")" "$icon_src"
  (
    cd "$(dirname "$bin")"
    nohup "./$BINARY_NAME" >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
  )
  echo "已启动（PID $(cat "$PID_FILE")），日志：$LOG_FILE"
}

main() {
  local cmd="${1:-start}"
  case "$cmd" in
    build)
      cmd_build
      ;;
    install)
      cmd_install
      ;;
    start)
      cmd_start
      ;;
    stop)
      cmd_stop
      ;;
    restart)
      cmd_restart
      ;;
    start-binary)
      cmd_start_binary
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      echo "未知命令: $cmd" >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
