#!/data/data/com.termux/files/usr/bin/bash
# update.sh — Pull latest code, reinstall deps, migrate, and restart
set -euo pipefail

# shellcheck source=lib-debian-backend.sh
. "$(cd "$(dirname "$0")" && pwd)/lib-debian-backend.sh"

echo "=== Drilling Costing — Updating ==="

# Stop running servers if any
if [ -f "$PIDFILE" ]; then
    bash "$TERMUX_DIR/stop.sh"
fi

# Pull latest from git
cd "$REPO_DIR"
echo ""
echo "[1/4] Pulling latest code..."
git pull

# Update Python dependencies (inside the Debian container)
echo ""
echo "[2/4] Updating Python dependencies (inside Debian)..."
ensure_backend_toolchain

# Update Node dependencies
echo ""
echo "[3/4] Updating Node dependencies..."
cd "$FRONTEND_DIR"
npm install
frontend_setup_env

# Force Nuxt rebuild on next start
rm -rf "$FRONTEND_DIR/.output"
echo "  Nuxt .output cleared (will rebuild on next start)"

# Run migrations
echo ""
echo "[4/4] Running migrations..."
run_migrations

echo ""
echo "=== Update complete. Run 'bash termux/start.sh' to restart. ==="
