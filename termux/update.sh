#!/data/data/com.termux/files/usr/bin/bash
# update.sh — Pull latest code, reinstall deps, migrate, and restart
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Drilling Costing — Updating ==="

# Stop running servers if any
if [ -f "$REPO_DIR/termux/.pids" ]; then
    bash "$REPO_DIR/termux/stop.sh"
fi

# Pull latest from git
cd "$REPO_DIR"
echo ""
echo "[1/4] Pulling latest code..."
git pull

# Update Python dependencies
echo ""
echo "[2/4] Updating Python dependencies..."
cd "$REPO_DIR/backend"
source .venv/bin/activate
pip install --prefer-binary --upgrade -e .
pip install --upgrade "psycopg>=3.2,<4"

# Update Node dependencies
echo ""
echo "[3/4] Updating Node dependencies..."
cd "$REPO_DIR/frontend"
npm install

# Force Nuxt rebuild on next start
rm -rf "$REPO_DIR/frontend/.output"
echo "  Nuxt .output cleared (will rebuild on next start)"

# Run migrations
echo ""
echo "[4/4] Running migrations..."
bash "$REPO_DIR/termux/migrate.sh"

echo ""
echo "=== Update complete. Run 'bash termux/start.sh' to restart. ==="
