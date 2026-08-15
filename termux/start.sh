#!/data/data/com.termux/files/usr/bin/bash
# start.sh — Start the backend and frontend servers in Termux
# Backend runs on port 8000, frontend on port 3000.
# Both bind to 0.0.0.0 so they are reachable over Wi-Fi/LAN.
# When offline, use http://localhost:3000 on the phone itself.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$REPO_DIR/termux/.pids"

# ── Guard: already running? ────────────────────────────────────────────────────
if [ -f "$PIDFILE" ]; then
    echo "Servers may already be running (found $PIDFILE)."
    echo "Run 'bash termux/stop.sh' first, or delete $PIDFILE manually."
    exit 1
fi

# ── Detect LAN IP for display ─────────────────────────────────────────────────
LAN_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || true)
if [ -z "$LAN_IP" ]; then
    LAN_IP=$(ip addr | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d/ -f1 || echo "offline")
fi

echo "=== Drilling Costing — Starting ==="

# ── Backend ────────────────────────────────────────────────────────────────────
echo ""
echo "Starting backend (FastAPI + Uvicorn)..."
cd "$REPO_DIR/backend"
source .venv/bin/activate

# Run migrations automatically on each start
python -m alembic upgrade head

nohup uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1 \
    > "$REPO_DIR/termux/backend.log" 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID  (log: termux/backend.log)"

# ── Frontend ───────────────────────────────────────────────────────────────────
echo ""
echo "Building and starting frontend (Nuxt)..."
cd "$REPO_DIR/frontend"

# Build once for production-like serving; use `nuxt dev` during active development
# by setting TERMUX_DEV=1 before running start.sh.
if [ "${TERMUX_DEV:-0}" = "1" ]; then
    nohup npm run dev -- --host 0.0.0.0 --port 3000 \
        > "$REPO_DIR/termux/frontend.log" 2>&1 &
else
    # Build if .output is missing or TERMUX_REBUILD is set
    if [ ! -d ".output" ] || [ "${TERMUX_REBUILD:-0}" = "1" ]; then
        echo "  Building Nuxt (this takes ~2 min on first run)..."
        npm run build > "$REPO_DIR/termux/build.log" 2>&1
        echo "  Build complete."
    fi
    nohup node .output/server/index.mjs \
        > "$REPO_DIR/termux/frontend.log" 2>&1 &
fi
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID  (log: termux/frontend.log)"

# ── Save PIDs ─────────────────────────────────────────────────────────────────
printf '%s\n%s\n' "$BACKEND_PID" "$FRONTEND_PID" > "$PIDFILE"

echo ""
echo "=== Servers are starting up ==="
echo ""
echo "  On this phone (offline):  http://localhost:3000"
if [ "$LAN_IP" != "offline" ]; then
    echo "  On your network (LAN):    http://$LAN_IP:3000"
fi
echo ""
echo "  Backend API:              http://localhost:8000"
echo "  API Docs (dev mode):      http://localhost:8000/docs"
echo ""
echo "Logs: termux/backend.log | termux/frontend.log"
echo "Stop: bash termux/stop.sh"
