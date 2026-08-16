#!/data/data/com.termux/files/usr/bin/bash
# stop.sh — Stop the backend and frontend servers
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$REPO_DIR/termux/.pids"

echo "=== Stopping servers ==="

# Kill by saved PIDs first
if [ -f "$PIDFILE" ]; then
    mapfile -t PIDS < "$PIDFILE"
    for PID in "${PIDS[@]}"; do
        if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null && echo "  Stopped PID $PID" || true
        else
            echo "  PID $PID already stopped"
        fi
    done
    rm -f "$PIDFILE"
fi

# Kill any orphaned uvicorn / node processes from this project
# (failsafe in case PIDs changed between starts)
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "  Killed orphaned uvicorn process" || true
pkill -f "nuxt dev" 2>/dev/null && echo "  Killed orphaned nuxt dev process" || true
pkill -f ".output/server/index.mjs" 2>/dev/null && echo "  Killed orphaned Nuxt server" || true

echo "=== Done ==="