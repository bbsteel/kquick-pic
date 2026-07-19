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
BUILD_INFO_FILE="$ROOT_DIR/build/build-info.json"
mkdir -p "$(dirname "$BUILD_INFO_FILE")"
COMMIT_ID="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || printf 'unknown')"
BUILD_NUMBER="$(git -C "$ROOT_DIR" rev-list --count HEAD 2>/dev/null || printf 'unknown')"
BUILD_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
python - "$BUILD_INFO_FILE" "$COMMIT_ID" "$BUILD_NUMBER" "$BUILD_TIME" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(
    json.dumps(
        {
            "commit_id": sys.argv[2],
            "build_number": sys.argv[3],
            "build_time": sys.argv[4],
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
PY
QUICK_PIC_BUILD_INFO_FILE="$BUILD_INFO_FILE" pyinstaller --distpath "$ROOT_DIR/dist" quick-pic.spec

echo "=== Build complete ==="
echo "Output: $OUTPUT_DIR/"
echo "Launch: $OUTPUT_DIR/quick-pic"
echo ""
echo "System requirements on target machine:"
echo "  gtk3 python-gobject cairo dbus-glib libnotify libx11 libxtst"
