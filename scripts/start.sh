#!/usr/bin/env bash
# 兼容入口：转发到仓库根目录的 start.sh
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT_DIR/start.sh" "$@"
