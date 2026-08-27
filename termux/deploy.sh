#!/data/data/com.termux/files/usr/bin/bash
# deploy.sh — Single entry point for Termux deployment of drilling-costing.
#
# First run:  installs Termux packages + the Debian container, creates the
#             backend Python environment INSIDE Debian (prebuilt wheels — no
#             compilation), configures .env files, runs migrations, builds and
#             starts the app.
# Subsequent runs: pulls latest code, updates deps, migrates, rebuilds if
#             needed, and restarts servers.
#
# Usage:
#   bash termux/deploy.sh
#   TERMUX_DEV=1 bash termux/deploy.sh      # dev mode (nuxt hot-reload)
#   TERMUX_REBUILD=1 bash termux/deploy.sh  # force Nuxt rebuild
#   TERMUX_PIP_INDEX_URL=... bash termux/deploy.sh  # alternate PyPI mirror
#                                                (default: https://pypi.org/simple)
#
# The Python backend runs inside a proot-distro Debian container because PyPI
# has no wheels for Termux's bionic Python: pydantic-core (Rust) & friends stay
# stuck compiling for 15+ minutes or crash outright. See lib-debian-backend.sh
# for the full rationale.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# shellcheck source=lib-debian-backend.sh
. "$(cd "$(dirname "$0")" && pwd)/lib-debian-backend.sh"

# ─── FIRST-TIME SETUP ─────────────────────────────────────────────────────────
first_time_setup() {
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║   Drilling Costing — First-Time Setup        ║"
    echo "╚══════════════════════════════════════════════╝"

    # ── 1. Termux packages ────────────────────────────────────────────────────
    # Node.js (frontend), git, openssl-tool (secret generation), proot-distro
    # (the Debian container that hosts the Python backend). Termux splits the
    # OpenSSL CLI into openssl-tool; the `openssl` package alone has no command.
    # No rust/clang/python on the Termux side — nothing compiles natively.
    log "[1/7] Installing Termux packages..."
    pkg update -y
    pkg install -y nodejs git openssl-tool proot-distro
    ok "Termux packages installed"

    # ── 2. Debian container ───────────────────────────────────────────────────
    log "[2/7] Setting up the Debian container..."
    ensure_debian_installed

    # ── 3. Python environment (inside Debian) ────────────────────────────────
    log "[3/7] Setting up the Python environment (inside Debian)..."
    ensure_debian_packages
    ensure_debian_python
    ensure_backend_venv
    install_python_deps

    # ── 4. Node dependencies ──────────────────────────────────────────────────
    log "[4/7] Installing Node dependencies..."
    cd "$FRONTEND_DIR"
    npm install --silent
    frontend_setup_env
    ok "Node dependencies installed"

    # ── 5. Backend .env ───────────────────────────────────────────────────────
    log "[5/7] Configuring backend environment..."
    write_backend_env

    # ── 6. Frontend .env ──────────────────────────────────────────────────────
    log "[6/7] Configuring frontend environment..."
    write_frontend_env

    # ── 7. Supabase URL ───────────────────────────────────────────────────────
    log "[7/7] Checking Supabase DATABASE_URL..."
    if ! prompt_for_database_url; then
        warn "DATABASE_URL not set — skipping migrations."
        warn "Edit backend/.env, then re-run: bash termux/deploy.sh"
        exit 0
    fi

    # Mark setup as complete only once everything above succeeded.
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

    log "[2/3] Updating Python dependencies (inside Debian)..."
    ensure_backend_toolchain

    log "[3/3] Updating Node dependencies..."
    cd "$FRONTEND_DIR"
    npm install --silent
    frontend_setup_env
    # Clear built output so it rebuilds with the new code.
    rm -rf .output
    ok "Node dependencies updated, .output cleared"

    # Self-heal a missing backend/.env (recreate it) and re-prompt for the
    # database if it still holds the placeholder. Without this, migrations
    # would run against the built-in localhost:5432 default — and nothing on
    # this phone listens there, so they would fail with 'connection refused'.
    if [ ! -f "$BACKEND_ENV" ]; then
        log "backend/.env is missing — recreating it..."
        write_backend_env
    fi
    if ! prompt_for_database_url; then
        warn "DATABASE_URL not set — skipping migrations."
        warn "Edit backend/.env, then re-run: bash termux/deploy.sh"
        exit 0
    fi
}

# ─── MAIN ─────────────────────────────────────────────────────────────────────
main() {
    stop_servers

    # Self-heal: marker present but venv gone/never Debian-managed → redo setup.
    if [ -f "$SETUP_MARKER" ] && [ ! -f "$VENV_MARKER" ]; then
        warn "Setup marker exists but the Debian-managed venv is missing."
        warn "Re-running first-time setup to repair the environment..."
        rm -f "$SETUP_MARKER"
    fi

    if [ ! -f "$SETUP_MARKER" ]; then
        first_time_setup
    else
        update_code
    fi

    run_migrations
    seed_admin
    start_all_servers
    print_access_banner
}

main
