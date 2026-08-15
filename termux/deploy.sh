#!/data/data/com.termux/files/usr/bin/bash
# deploy.sh — Single entry point for Termux deployment of drilling-costing.
#
# First run:  installs all dependencies, configures .env files, runs migrations,
#             builds and starts the app.
# Subsequent runs: pulls latest code, updates deps, migrates, rebuilds if needed,
#             and restarts servers.
#
# Usage:
#   bash termux/deploy.sh
#   TERMUX_DEV=1 bash termux/deploy.sh      # dev mode (nuxt hot-reload)
#   TERMUX_REBUILD=1 bash termux/deploy.sh  # force Nuxt rebuild
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SETUP_MARKER="$REPO_DIR/termux/.setup_done"
PIDFILE="$REPO_DIR/termux/.pids"
BACKEND_ENV="$REPO_DIR/backend/.env"
FRONTEND_ENV="$REPO_DIR/frontend/.env"

# ─── Helpers ──────────────────────────────────────────────────────────────────
log()  { echo ""; echo "▶ $*"; }
ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*"; }

detect_lan_ip() {
    local ip
    ip=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || true)
    if [ -z "$ip" ]; then
        ip=$(ip addr 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d/ -f1 || true)
    fi
    echo "${ip:-127.0.0.1}"
}

stop_servers() {
    if [ -f "$PIDFILE" ]; then
        log "Stopping running servers..."
        mapfile -t PIDS < "$PIDFILE"
        for PID in "${PIDS[@]}"; do
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID" && ok "Stopped PID $PID"
            fi
        done
        rm -f "$PIDFILE"
    fi
}

# ─── FIRST-TIME SETUP ─────────────────────────────────────────────────────────
first_time_setup() {
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║   Drilling Costing — First-Time Setup        ║"
    echo "╚══════════════════════════════════════════════╝"

    # ── 1. System packages ────────────────────────────────────────────────────
    log "[1/6] Installing system packages..."
    pkg update -y
    pkg install -y python nodejs git openssl python-numpy python-pandas
    ok "System packages installed"

    # ── 2. Python virtualenv ──────────────────────────────────────────────────
    log "[2/6] Setting up Python environment..."
    cd "$REPO_DIR/backend"
    python -m venv --clear --system-site-packages .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install --upgrade pip --quiet
    # psycopg[binary] cannot be built on Termux ARM; use pure-Python psycopg.
    pip install --prefer-binary -e . --config-settings editable_mode=compat --quiet
    pip install "psycopg>=3.2,<4" --quiet
    ok "Python environment ready"

    # ── 3. Node dependencies ──────────────────────────────────────────────────
    log "[3/6] Installing Node dependencies..."
    cd "$REPO_DIR/frontend"
    npm install --silent
    ok "Node dependencies installed"

    # ── 4. Generate backend .env ──────────────────────────────────────────────
    log "[4/6] Configuring backend environment..."
    if [ ! -f "$BACKEND_ENV" ]; then
        local SECRET LAN_IP
        SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        LAN_IP=$(detect_lan_ip)
        cat > "$BACKEND_ENV" <<EOF
ENVIRONMENT=termux
# ── Supabase connection string ────────────────────────────────────────────────
# Supabase → Settings → Database → Connection string → URI (Transaction pooler, port 6543)
# Replace the placeholder below with your actual Supabase URL.
DATABASE_URL=postgresql+psycopg://postgres.XXXX:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres
SECRET_KEY=$SECRET
CORS_ORIGINS=["http://localhost:3000","http://$LAN_IP:3000"]
LOG_LEVEL=INFO
ACCESS_TOKEN_EXPIRE_MINUTES=120
API_V1_PREFIX=/api/v1
APP_VERSION=0.1.0
EOF
        ok "Created backend/.env (LAN IP: $LAN_IP)"
    else
        ok "backend/.env already exists"
    fi

    # ── 5. Generate frontend .env ─────────────────────────────────────────────
    log "[5/6] Configuring frontend environment..."
    if [ ! -f "$FRONTEND_ENV" ]; then
        cat > "$FRONTEND_ENV" <<EOF
NUXT_PUBLIC_API_BASE=/api/v1
NUXT_API_INTERNAL_BASE=http://127.0.0.1:8000
NUXT_API_PROXY_TIMEOUT_MS=30000
HOST=0.0.0.0
EOF
        ok "Created frontend/.env"
    else
        ok "frontend/.env already exists"
    fi

    # ── 6. Prompt for Supabase URL ────────────────────────────────────────────
    log "[6/6] Checking Supabase DATABASE_URL..."
    if grep -q "XXXX" "$BACKEND_ENV" 2>/dev/null; then
        echo ""
        echo "  ┌─────────────────────────────────────────────────────────────┐"
        echo "  │  ACTION REQUIRED — Paste your Supabase DATABASE_URL        │"
        echo "  │                                                             │"
        echo "  │  1. Open Supabase → your project                           │"
        echo "  │  2. Settings → Database → Connection string → URI          │"
        echo "  │  3. Pick the Transaction pooler URL (port 6543)            │"
        echo "  │  4. Change 'postgresql://' to 'postgresql+psycopg://'      │"
        echo "  └─────────────────────────────────────────────────────────────┘"
        echo ""
        read -r -p "  Paste DATABASE_URL now (or press Enter to set it manually later): " DB_URL
        if [ -n "$DB_URL" ]; then
            # Normalize scheme
            DB_URL="${DB_URL/postgresql:\/\//postgresql+psycopg://}"
            DB_URL="${DB_URL/postgres:\/\//postgresql+psycopg://}"
            sed -i "s|DATABASE_URL=postgresql+psycopg://postgres.XXXX.*|DATABASE_URL=$DB_URL|" "$BACKEND_ENV"
            ok "DATABASE_URL saved"
        else
            warn "DATABASE_URL not set. Edit backend/.env before continuing."
            warn "Then re-run: bash termux/deploy.sh"
            exit 0
        fi
    else
        ok "DATABASE_URL already configured"
    fi

    # Mark setup as complete
    touch "$SETUP_MARKER"
    ok "Setup marker written"

    echo ""
    echo "  Setup complete!"
}

# ─── UPDATE (subsequent runs) ─────────────────────────────────────────────────
update_code() {
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║   Drilling Costing — Updating                ║"
    echo "╚══════════════════════════════════════════════╝"

    log "[1/3] Pulling latest code from git..."
    cd "$REPO_DIR"
    git pull
    ok "Code updated"

    log "[2/3] Updating Python dependencies..."
    cd "$REPO_DIR/backend"
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install --prefer-binary --upgrade -e . --quiet
    pip install --upgrade "psycopg>=3.2,<4" --quiet
    ok "Python dependencies updated"

    log "[3/3] Updating Node dependencies..."
    cd "$REPO_DIR/frontend"
    npm install --silent
    # Clear built output so it rebuilds with the new code
    rm -rf .output
    ok "Node dependencies updated, .output cleared"
}

# ─── MIGRATE ──────────────────────────────────────────────────────────────────
run_migrations() {
    log "Running database migrations..."
    cd "$REPO_DIR/backend"
    # shellcheck disable=SC1091
    source .venv/bin/activate
    python -m alembic upgrade head
    ok "Migrations applied"
}

# ─── START SERVERS ────────────────────────────────────────────────────────────
start_servers() {
    local LAN_IP
    LAN_IP=$(detect_lan_ip)

    log "Starting backend (Uvicorn on :8000)..."
    cd "$REPO_DIR/backend"
    # shellcheck disable=SC1091
    source .venv/bin/activate
    nohup uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 1 \
        > "$REPO_DIR/termux/backend.log" 2>&1 &
    BACKEND_PID=$!
    ok "Backend PID: $BACKEND_PID"

    log "Starting frontend (Nuxt on :3000)..."
    cd "$REPO_DIR/frontend"
    if [ "${TERMUX_DEV:-0}" = "1" ]; then
        # Dev mode: hot-reload
        nohup npm run dev -- --host 0.0.0.0 --port 3000 \
            > "$REPO_DIR/termux/frontend.log" 2>&1 &
    else
        # Production mode: build then serve
        if [ ! -d ".output" ] || [ "${TERMUX_REBUILD:-0}" = "1" ]; then
            echo "  Building Nuxt (takes ~2 min on first run)..."
            npm run build > "$REPO_DIR/termux/build.log" 2>&1
            ok "Nuxt build complete"
        fi
        nohup node .output/server/index.mjs \
            > "$REPO_DIR/termux/frontend.log" 2>&1 &
    fi
    FRONTEND_PID=$!
    ok "Frontend PID: $FRONTEND_PID"

    printf '%s\n%s\n' "$BACKEND_PID" "$FRONTEND_PID" > "$PIDFILE"

    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║   Servers are running!                       ║"
    echo "╠══════════════════════════════════════════════╣"
    printf  "║  Phone (this device):  http://localhost:3000 ║\n"
    if [ "$LAN_IP" != "127.0.0.1" ]; then
        printf "║  Network (LAN):  http://%-20s  ║\n" "$LAN_IP:3000"
    fi
    echo "╠══════════════════════════════════════════════╣"
    echo "║  Logs:  termux/backend.log                   ║"
    echo "║         termux/frontend.log                  ║"
    echo "║  Stop:  bash termux/stop.sh                  ║"
    echo "╚══════════════════════════════════════════════╝"
}

# ─── MAIN ─────────────────────────────────────────────────────────────────────
main() {
    stop_servers

    if [ ! -f "$SETUP_MARKER" ]; then
        first_time_setup
    else
        update_code
    fi

    run_migrations
    start_servers
}

main
