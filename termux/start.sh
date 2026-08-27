#!/data/data/com.termux/files/usr/bin/bash
# start.sh — Start the backend and frontend servers in Termux.
# Backend: Uvicorn on :8000, running inside the proot-distro Debian container.
# Frontend: Nuxt on :3000, running natively on Termux.
# Both bind to 0.0.0.0 so they are reachable over Wi-Fi/LAN.
# When offline, use http://localhost:3000 on the phone itself.
set -euo pipefail

# shellcheck source=lib-debian-backend.sh
. "$(cd "$(dirname "$0")" && pwd)/lib-debian-backend.sh"

# ── Guard: already running? ───────────────────────────────────────────────────
if [ -f "$PIDFILE" ]; then
    echo "Servers may already be running (found $PIDFILE)."
    echo "Attempting graceful stop first..."
    bash "$TERMUX_DIR/stop.sh" || true
    sleep 2
fi

if [ ! -f "$VENV_MARKER" ]; then
    die "No Debian-managed virtualenv found. Run 'bash termux/deploy.sh' first."
fi

echo "=== Drilling Costing — Starting ==="

# Keep the phone awake while servers run (best effort; harmless if absent).
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock >/dev/null 2>&1 && echo "  (wake lock acquired)"
fi

# Run migrations automatically on each start (idempotent).
run_migrations
seed_admin

start_backend
start_frontend
printf '%s\n%s\n' "$BACKEND_PID" "$FRONTEND_PID" > "$PIDFILE"

LAN_IP=$(detect_lan_ip)

echo ""
echo "=== Servers are starting up ==="
if wait_for_backend 45; then
    echo "  Backend is live:        http://localhost:8000/api/v1/live"
else
    echo "  ⚠ Backend did not answer within 45 s — check termux/backend.log"
fi
echo ""
echo "  On this phone (offline):  http://localhost:3000"
if [ "$LAN_IP" != "127.0.0.1" ]; then
    echo "  On your network (LAN):    http://$LAN_IP:3000"
fi
echo ""
echo "  Backend API:              http://localhost:8000"
echo "  API docs:                 http://localhost:8000/docs"
echo ""
echo "Logs: termux/backend.log | termux/frontend.log"
echo "Stop: bash termux/stop.sh"
