#!/data/data/com.termux/files/usr/bin/bash
# setup.sh — First-time Termux setup for drilling-costing
# Run once after cloning the repo: bash termux/setup.sh
#
# Database: Supabase (PostgreSQL in the cloud).
# You must have your Supabase DATABASE_URL ready before running this.
# Get it from: Supabase project → Settings → Database → Connection string → URI
# Use the "Transaction" pooler URL (port 6543) for best mobile compatibility.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Drilling Costing — Termux Setup ==="
echo "Repo: $REPO_DIR"

# ── 1. System packages ────────────────────────────────────────────────────────
echo ""
echo "[1/5] Installing system packages..."
pkg update -y
pkg install -y python nodejs git openssl rust clang make pkg-config libffi

# ── 2. Python virtualenv ──────────────────────────────────────────────────────
echo ""
echo "[2/5] Creating Python virtualenv..."
cd "$REPO_DIR/backend"
python -m venv --clear --system-site-packages .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
# psycopg[binary] doesn't build on Termux ARM; use the pure-Python driver instead.
pip install --prefer-binary -e . --config-settings editable_mode=compat
pip install "psycopg>=3.2,<4"

# ── 3. Node dependencies ──────────────────────────────────────────────────────
echo ""
echo "[3/5] Installing Node dependencies..."
cd "$REPO_DIR/frontend"
npm install

# ── 4. Generate backend .env if missing ───────────────────────────────────────
echo ""
echo "[4/5] Configuring backend environment..."
BACKEND_ENV="$REPO_DIR/backend/.env"
if [ ! -f "$BACKEND_ENV" ]; then
    SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
    # Detect LAN IP (wlan0 first, then any non-loopback)
    LAN_IP=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || true)
    if [ -z "$LAN_IP" ]; then
        LAN_IP=$(ip addr | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d/ -f1 || echo "127.0.0.1")
    fi
    cat > "$BACKEND_ENV" <<EOF
ENVIRONMENT=termux
# Replace the placeholder below with your Supabase connection string.
# Supabase → Settings → Database → Connection string → URI (Transaction pooler, port 6543)
DATABASE_URL=postgresql+psycopg://postgres.xxxx:PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres
SECRET_KEY=$SECRET
CORS_ORIGINS=["http://localhost:3000","http://$LAN_IP:3000"]
LOG_LEVEL=INFO
ACCESS_TOKEN_EXPIRE_MINUTES=120
API_V1_PREFIX=/api/v1
APP_VERSION=0.1.0
EOF
    echo "  Created $BACKEND_ENV"
    echo "  LAN IP detected: $LAN_IP"
    echo ""
    echo "  *** ACTION REQUIRED ***"
    echo "  Edit backend/.env and replace DATABASE_URL with your Supabase connection string."
    echo "  Then run: bash termux/migrate.sh"
else
    echo "  $BACKEND_ENV already exists, skipping."
fi

# ── 5. Configure frontend .env if missing ─────────────────────────────────────
echo ""
echo "[5/5] Configuring frontend environment..."
FRONTEND_ENV="$REPO_DIR/frontend/.env"
if [ ! -f "$FRONTEND_ENV" ]; then
    cat > "$FRONTEND_ENV" <<EOF
NUXT_PUBLIC_API_BASE=/api/v1
NUXT_API_INTERNAL_BASE=http://127.0.0.1:8000
NUXT_API_PROXY_TIMEOUT_MS=30000
HOST=0.0.0.0
EOF
    echo "  Created $FRONTEND_ENV"
else
    echo "  $FRONTEND_ENV already exists, skipping."
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit backend/.env — set your Supabase DATABASE_URL"
echo "  2. Run migrations:  bash termux/migrate.sh"
echo "  3. Start servers:   bash termux/start.sh"
echo ""
echo "Access the app:"
echo "  On the phone:  http://localhost:3000"
LAN_IP_DISPLAY=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || true)
if [ -z "$LAN_IP_DISPLAY" ]; then
    LAN_IP_DISPLAY=$(ip addr | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d/ -f1 || echo "<your-phone-ip>")
fi
echo "  On your network: http://$LAN_IP_DISPLAY:3000"
