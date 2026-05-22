#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.13}"
VENV_DIR="$ROOT_DIR/.venv"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
DESKTOP_FILE="$APP_DIR/quick-pic.desktop"
ICON_FILE="$ICON_DIR/quick-pic.png"
DEFAULT_ICON="$ROOT_DIR/quick_pic/icons/quick-pic-tray-v1.png"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd uv
require_cmd "$PYTHON_BIN"

"$PYTHON_BIN" - <<'PY'
import importlib
for module in ("gi", "dbus"):
    importlib.import_module(module)
PY

cd "$ROOT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  uv venv --system-site-packages --python "$PYTHON_BIN"
fi

uv sync --frozen

mkdir -p "$APP_DIR" "$ICON_DIR"
cp "$DEFAULT_ICON" "$ICON_FILE"

cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Quick Pic
Comment=Quick screenshot tool
Exec=$VENV_DIR/bin/quick-pic
Path=$ROOT_DIR
Icon=quick-pic
Terminal=false
Categories=Utility;Graphics;
StartupNotify=false
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo "Installed Quick Pic launcher at $DESKTOP_FILE"
