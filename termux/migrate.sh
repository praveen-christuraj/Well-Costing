#!/data/data/com.termux/files/usr/bin/bash
# migrate.sh — Run Alembic migrations against the configured database.
# The backend (and its virtualenv) live inside the proot-distro Debian
# container, so migrations execute there too.
set -euo pipefail

# shellcheck source=lib-debian-backend.sh
. "$(cd "$(dirname "$0")" && pwd)/lib-debian-backend.sh"

if [ ! -f "$VENV_MARKER" ]; then
    die "No Debian-managed virtualenv found. Run 'bash termux/deploy.sh' (or setup.sh) first."
fi

echo "=== Running database migrations ==="
run_migrations
echo "=== Migrations complete ==="
