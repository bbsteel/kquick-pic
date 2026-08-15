#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(
  cd "$ROOT_DIR" &&
    python3 - <<'PY'
import tomllib
from pathlib import Path
data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)"
OUT_DIR="$ROOT_DIR/dist"
ARCHIVE_NAME="kuick-pic-$VERSION.tar.gz"

mkdir -p "$OUT_DIR"

tar \
  --exclude=".git" \
  --exclude=".venv" \
  --exclude=".build-venv" \
  --exclude="dist" \
  --exclude="build" \
  --exclude=".pytest_cache" \
  --exclude="__pycache__" \
  --exclude="*.pyc" \
  -czf "$OUT_DIR/$ARCHIVE_NAME" \
  -C "$(dirname "$ROOT_DIR")" \
  "$(basename "$ROOT_DIR")"

echo "Created $OUT_DIR/$ARCHIVE_NAME"
