#!/data/data/com.termux/files/usr/bin/bash
# share.sh — Expose the running app to testers OUTSIDE your Wi-Fi network.
#
# Your phone's LAN IP (e.g. 192.168.1.X) only works for devices on the SAME
# Wi-Fi/router. To let testers connect from any network (mobile data, a
# different Wi-Fi, another city), this opens a free Cloudflare Tunnel that
# gives you a public HTTPS URL forwarding to your phone's frontend (port 3000).
#
# Requirements: the app must already be running (bash termux/deploy.sh or
# bash termux/start.sh). Run this in a SEPARATE Termux session/tab so it can
# keep printing the tunnel URL and logs while your servers keep running.
#
# Usage:
#   bash termux/share.sh
# Stop with Ctrl+C. Each run gives you a brand-new random URL — testers must
# use whatever URL is printed each time you run this.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PIDFILE="$REPO_DIR/termux/.pids"

if [ ! -f "$PIDFILE" ]; then
    echo "⚠ The app doesn't look like it's running."
    echo "  Start it first in another Termux session:  bash termux/deploy.sh"
    echo ""
    read -r -p "Continue anyway? [y/N] " CONTINUE
    if [ "${CONTINUE,,}" != "y" ]; then
        exit 1
    fi
fi

if ! command -v cloudflared >/dev/null 2>&1; then
    echo "▶ Installing cloudflared (one-time)..."
    pkg install -y cloudflared
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   Opening a public tunnel to http://localhost:3000         ║"
echo "║   Share the https://...trycloudflare.com URL below with    ║"
echo "║   testers on ANY network (mobile data, other Wi-Fi, etc).  ║"
echo "║   Keep this window open. Press Ctrl+C to stop sharing.     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

exec cloudflared tunnel --url http://localhost:3000
