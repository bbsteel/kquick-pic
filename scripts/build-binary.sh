#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3.13}"
OUTPUT_DIR="$ROOT_DIR/dist/quick-pic"

echo "=== Cleaning previous build ==="
rm -rf "$OUTPUT_DIR" "$ROOT_DIR/build" "$ROOT_DIR/dist/quick-pic"

echo "=== Creating build venv ==="
BUILD_VENV="$ROOT_DIR/.build-venv"
rm -rf "$BUILD_VENV"
uv venv --system-site-packages --python "$PYTHON_BIN" "$BUILD_VENV"
source "$BUILD_VENV/bin/activate"
uv pip install --python "$PYTHON_BIN" pyinstaller mss pynput Pillow

echo "=== Building with PyInstaller ==="
cd "$ROOT_DIR"
pyinstaller --distpath "$ROOT_DIR/dist" quick-pic.spec

echo "=== Build complete ==="
echo "Output: $OUTPUT_DIR/"
echo "Launch: $OUTPUT_DIR/quick-pic"
echo ""
echo "System requirements on target machine:"
echo "  gtk3 python-gobject cairo dbus-glib libnotify libx11 libxtst"
