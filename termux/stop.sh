#!/data/data/com.termux/files/usr/bin/bash
# stop.sh — Stop the backend and frontend servers
set -euo pipefail

# shellcheck source=lib-debian-backend.sh
. "$(cd "$(dirname "$0")" && pwd)/lib-debian-backend.sh"

echo "=== Stopping servers ==="
stop_servers

# Release the wake lock (best effort; harmless if absent).
if command -v termux-wake-unlock >/dev/null 2>&1; then
    termux-wake-unlock >/dev/null 2>&1 || true
fi

echo "=== Done ==="
