#!/data/data/com.termux/files/usr/bin/bash
# migrate.sh — Run Alembic migrations against the configured database
# Works with both SQLite (Termux) and PostgreSQL (local/cloud).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Running database migrations ==="
cd "$REPO_DIR/backend"
source .venv/bin/activate
python -m alembic upgrade head
echo "=== Migrations complete ==="
