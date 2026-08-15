#!/data/data/com.termux/files/usr/bin/bash
# stop.sh — Stop the backend and frontend servers
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$REPO_DIR/termux/.pids"

if [ ! -f "$PIDFILE" ]; then
    echo "No PID file found — servers may not be running."
    exit 0
fi

echo "=== Stopping servers ==="

mapfile -t PIDS < "$PIDFILE"
for PID in "${PIDS[@]}"; do
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" && echo "  Stopped PID $PID"
    else
        echo "  PID $PID already stopped"
    fi
done

rm -f "$PIDFILE"
echo "=== Done ==="
