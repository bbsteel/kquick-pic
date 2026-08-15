#!/usr/bin/env bash
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/256x256/apps"
AUTOSTART_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/kuick-pic.desktop"

rm -f "$APP_DIR/kuick-pic.desktop" "$APP_DIR/kquick-pic.desktop" "$APP_DIR/quick-pic.desktop"
rm -f "$ICON_DIR/kuick-pic.png" "$ICON_DIR/kquick-pic.png" "$ICON_DIR/quick-pic.png"
rm -f "$AUTOSTART_FILE"
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/kquick-pic.desktop"
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/quick-pic.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo "Removed Kuick Pic desktop integration"
