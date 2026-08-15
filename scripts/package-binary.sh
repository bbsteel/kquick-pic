#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BINARY_DIR="$ROOT_DIR/dist/kuick-pic"

if [[ ! -f "$BINARY_DIR/kuick-pic" ]]; then
  echo "ERROR: Binary not found. Run scripts/build-binary.sh first." >&2
  exit 1
fi

VERSION=$(python3 -c "
import tomllib
with open('$ROOT_DIR/pyproject.toml', 'rb') as f:
    print(tomllib.load(f)['project']['version'])
")
ARCHIVE_NAME="kuick-pic-${VERSION}-linux-x86_64.tar.gz"

echo "=== Packaging binary distribution ==="
mkdir -p "$ROOT_DIR/dist"
tar -czf "$ROOT_DIR/dist/$ARCHIVE_NAME" \
  -C "$ROOT_DIR/dist" \
  "kuick-pic"

echo "Created: dist/$ARCHIVE_NAME"
ls -lh "$ROOT_DIR/dist/$ARCHIVE_NAME"
