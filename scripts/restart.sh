#!/usr/bin/env bash
# Kill old Quick-Pic instance and start a new one.
set -euo pipefail

PID_FILE="$HOME/.config/quick-pic/quick-pic.pid"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Kill old instance ---
if [[ -f "$PID_FILE" ]]; then
    pid=$(cat "$PID_FILE")
    if [[ -d "/proc/$pid" ]] && grep -q 'quick_pic' "/proc/$pid/cmdline" 2>/dev/null; then
        echo "Killing old quick-pic (PID $pid)..."
        kill "$pid"
        for _ in $(seq 1 30); do
            [[ -d "/proc/$pid" ]] || break
            sleep 0.1
        done
        if [[ -d "/proc/$pid" ]]; then
            echo "Force killing..."
            kill -9 "$pid" 2>/dev/null || true
        fi
        echo "Old instance stopped."
    else
        echo "Stale PID file, removing."
    fi
    rm -f "$PID_FILE"
fi

# --- Start new instance ---
echo "Starting Quick-Pic..."
cd "$PROJECT_DIR"
exec uv run python -m quick_pic
