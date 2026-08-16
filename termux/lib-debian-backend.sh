#!/data/data/com.termux/files/usr/bin/bash
# lib-debian-backend.sh — shared helpers for all Termux deployment scripts.
#
# ── Why Debian inside proot? ─────────────────────────────────────────────────
# Termux's Python is linked against Android's *bionic* libc, so PyPI serves NO
# prebuilt wheels for it. Every C/Rust extension the backend needs
# (pydantic-core, uvloop, watchfiles, httptools, bcrypt, …) falls back to a
# source build on the phone: 15+ minutes of
# Rust compilation that usually hangs, crashes for lack of memory, or fails
# outright. That is the "stuck while setting up the Python environment"
# symptom (pydantic-core issue #855 is the classic report).
#
# proot-distro's Debian container is a real *glibc* Linux user-space, so pip
# installs official manylinux_aarch64 wheels for EVERY dependency in
# backend/pyproject.toml — nothing compiles, nothing hangs.
#
# proot-distro login bind-mounts Termux's $HOME at the same absolute path
# inside Debian (unless --isolated is used), so this repository is shared
# between both user-spaces. The backend's virtualenv lives at backend/.venv
# and is created/used ONLY from inside Debian; it carries a .debian-managed
# marker so the scripts can detect (and safely replace) stale native venvs.
#
# The frontend stays Termux-native: Node.js works fine on Termux.
#
# ── Wheels-only install (why the pip step can never hang again) ──────────────
# The pip step runs with --only-binary :all: against an EXPLICIT index (PyPI by
# default) while ignoring any pip.conf / inherited PIP_* variables / HTTP cache
# on the phone. If a prebuilt manylinux aarch64 wheel is missing for some
# version, pip now FAILS FAST (seconds, with a clear message) instead of
# compiling Rust/C for 15+ minutes. termux/requirements-constraints.txt pins
# every native-code package to a version whose aarch64 wheel is confirmed on
# PyPI (see that file for the verification table).
# ─────────────────────────────────────────────────────────────────────────────

# Guard against being sourced twice.
if [ -n "${WELL_COSTING_TERMUX_LIB:-}" ]; then
    return 0
fi
WELL_COSTING_TERMUX_LIB=1

TERMUX_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$TERMUX_LIB_DIR/.." && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
TERMUX_DIR="$REPO_DIR/termux"
BACKEND_ENV="$BACKEND_DIR/.env"
FRONTEND_ENV="$FRONTEND_DIR/.env"
PIDFILE="$TERMUX_DIR/.pids"
SETUP_MARKER="$TERMUX_DIR/.setup_done"

# proot-distro alias to use (override: TERMUX_DEBIAN_DISTRO=ubuntu bash termux/…)
DEBIAN_DISTRO="${TERMUX_DEBIAN_DISTRO:-debian}"

# Python version window the backend accepts (backend/pyproject.toml):
#   requires-python = ">=3.12,<3.14"
PY_MIN="3.12"
PY_MAX_EXCLUSIVE="3.14"

VENV_NAME=".venv"
VENV_DIR="$BACKEND_DIR/$VENV_NAME"
# Proof the venv was created INSIDE Debian (glibc). Native-Termux venvs and the
# venvs left behind by the old broken deploy.sh (.venv-debian) lack it.
VENV_MARKER="$VENV_DIR/.debian-managed"

# Safe-quoted for embedding into guest shell command strings.
printf -v REPO_Q '%q' "$REPO_DIR"
printf -v BACKEND_Q '%q' "$BACKEND_DIR"

# Ensures python3/pip resolve in non-login guest shells (bash -c skips profile).
GUEST_PATH_PREFIX='export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH; '

# Set by ensure_debian_python(): "system" (Debian's python3) or "uv"
# (standalone CPython 3.12 managed by uv). Read by the venv/install helpers.
DEBIAN_PY_BOOTSTRAP=""

# ─── Logging helpers ─────────────────────────────────────────────────────────
log()  { echo ""; echo "▶ $*"; }
ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠ $*"; }
err()  { echo "  ✗ $*" >&2; }

die() { err "$*"; exit 1; }

# ─── Networking / misc ───────────────────────────────────────────────────────
detect_lan_ip() {
    local ip
    ip=$(ip addr show wlan0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 || true)
    if [ -z "$ip" ]; then
        ip=$(ip addr 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | head -1 | awk '{print $2}' | cut -d/ -f1 || true)
    fi
    echo "${ip:-127.0.0.1}"
}

# ─── Debian container plumbing ───────────────────────────────────────────────

# Run a command inside the Debian container as root, returning its exit code.
# Guest-side variables must be escaped (\$) by the caller when single-quoting
# is not practical; Termux-side interpolation happens normally inside double
# quotes at the call site.
run_in_debian() {
    proot-distro login "$DEBIAN_DISTRO" -- bash -c "${GUEST_PATH_PREFIX}$1"
}

# Run a backend command from $BACKEND_DIR inside Debian.
backend_shell() {
    run_in_debian "cd $BACKEND_Q && $1"
}

debian_present() {
    local base="${PREFIX:-/data/data/com.termux/files/usr}/var/lib/proot-distro"
    # proot-distro 4.x stores rootfs at installed-rootfs/<name>; proot-distro
    # 5.x uses containers/<name>/rootfs (and auto-migrates the legacy path on
    # login). Accept both so an upgraded Termux doesn't trigger a spurious
    # reinstall ("container already exists" abort).
    [ -d "$base/installed-rootfs/$DEBIAN_DISTRO" ] || [ -d "$base/containers/$DEBIAN_DISTRO/rootfs" ]
}

ensure_debian_installed() {
    if ! command -v proot-distro >/dev/null 2>&1; then
        log "Installing proot-distro..."
        pkg install -y proot-distro
    fi
    if debian_present; then
        ok "Debian container already installed ($DEBIAN_DISTRO)"
    else
        log "Installing Debian container (one-time download, a few hundred MB)..."
        proot-distro install "$DEBIAN_DISTRO"
    fi
    # Functional probe — catches half-finished/corrupted installs early.
    run_in_debian "true" || die "Debian container '$DEBIAN_DISTRO' failed to start. Try: proot-distro reset $DEBIAN_DISTRO"
    ok "Debian container is working"
}

# Base packages inside Debian. python3-venv provides ensurepip; python3-pip is
# a convenience for debugging; curl + ca-certificates support the uv fallback.
# The quick check actually CREATES a throwaway venv: on Debian, `import venv`
# succeeds even when python3-venv (and thus a working ensurepip) is missing.
ensure_debian_packages() {
    if run_in_debian "rm -rf /tmp/.venv-probe && python3 -m venv /tmp/.venv-probe >/dev/null 2>&1 && rm -rf /tmp/.venv-probe"; then
        ok "Debian Python packages already present"
        return 0
    fi
    run_in_debian "rm -rf /tmp/.venv-probe || true"
    log "Installing Debian packages (python3, venv, pip)..."
    # libpq5: psycopg (pure-Python driver) dlopens libpq at runtime for the
    # Supabase connection; without it the app dies on the first DB request.
    run_in_debian "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends python3 python3-venv python3-pip ca-certificates curl libpq5"
    ok "Debian packages installed"
}

debian_python_ok() {
    run_in_debian "python3 -c 'import sys; sys.exit(0 if (3, 12) <= sys.version_info[:2] < (3, 14) else 1)'" >/dev/null 2>&1
}

# Decide which Python bootstraps the venv. Debian stable currently ships a
# supported Python (gate: >=3.12,<3.14). If a future Debian moves outside the
# window, fall back to a standalone CPython 3.12 via uv — no compilation.
ensure_debian_python() {
    local ver
    ver=$(run_in_debian "python3 --version 2>&1" 2>/dev/null | awk '{print $2}' || true)
    if debian_python_ok; then
        DEBIAN_PY_BOOTSTRAP="system"
        ok "Debian Python ${ver:-unknown} satisfies >=$PY_MIN,<$PY_MAX_EXCLUSIVE"
        return 0
    fi
    warn "Debian Python (${ver:-not found}) is outside $PY_MIN – <$PY_MAX_EXCLUSIVE; installing standalone CPython 3.12 via uv"
    run_in_debian "command -v uv >/dev/null 2>&1 || [ -x \"\$HOME/.local/bin/uv\" ] || curl -LsSf https://astral.sh/uv/install.sh | sh" \
        || die "Failed to install uv inside Debian (check internet). Alternatively: TERMUX_DEBIAN_DISTRO=debian bash termux/deploy.sh after 'proot-distro reset debian'."
    run_in_debian '"$HOME/.local/bin/uv" python install 3.12' \
        || die "Failed to install standalone CPython 3.12 via uv (check internet)."
    DEBIAN_PY_BOOTSTRAP="uv"
    ok "Standalone CPython 3.12 ready (uv)"
}

# ─── Backend virtualenv (created and used only inside Debian) ────────────────

# Wipe venvs that cannot work inside Debian. Called before ensure_backend_venv.
clean_stale_venvs() {
    # Legacy of the old broken deploy.sh: a venv named .venv-debian that no
    # other script referenced. Remove it so it stops confusing users/tools.
    if [ -d "$BACKEND_DIR/.venv-debian" ]; then
        warn "Removing backend/.venv-debian (left behind by the old broken setup)"
        rm -rf "$BACKEND_DIR/.venv-debian"
    fi
    # A .venv without our marker was created by native Termux Python (bionic)
    # or by hand on another OS — the interpreter it points at doesn't exist or
    # can't run inside Debian, so recreate it.
    if [ -d "$VENV_DIR" ] && [ ! -f "$VENV_MARKER" ]; then
        warn "Removing existing backend/.venv (not created inside Debian — it cannot run in the container)"
        rm -rf "$VENV_DIR"
    fi
}

ensure_backend_venv() {
    clean_stale_venvs
    if [ -f "$VENV_MARKER" ]; then
        ok "Debian-managed virtualenv present (backend/$VENV_NAME)"
        return 0
    fi
    log "Creating Python virtualenv inside Debian..."
    if [ "$DEBIAN_PY_BOOTSTRAP" = "uv" ]; then
        backend_shell '"$HOME/.local/bin/uv" venv --python 3.12 --clear '"$VENV_NAME"
    else
        backend_shell "python3 -m venv --clear $VENV_NAME"
    fi
    backend_shell "touch $VENV_NAME/.debian-managed"
    ok "Virtualenv ready (backend/$VENV_NAME)"
}

# ── Isolated, wheels-only pip ─────────────────────────────────────────────────

# Default PyPI index for backend installs. A phone may have a broken/mirror
# PIP_* environment or pip.conf (Termux env vars are inherited into the Debian
# container) that silently makes pip download source tarballs instead of
# wheels — that is exactly the "stuck compiling pydantic-core" symptom. Override
# only if pypi.org is unreachable from your network:
#   TERMUX_PIP_INDEX_URL=https://mirror.example.com/simple bash termux/deploy.sh
PIP_INDEX_URL_DEFAULT="https://pypi.org/simple"

# PIP_* variables whose inherited values could change which files pip picks
# (index, binary policy, platform overrides) or where it caches them. The
# trailing PIP_CONFIG_FILE=/dev/null (set AFTER the unsets, and replacing the
# CLI --config-file flag, which pip removed) makes pip ignore every pip.conf on
# the phone and in the container.
PIP_ISOLATE_ENV="env -u PIP_INDEX_URL -u PIP_EXTRA_INDEX_URL -u PIP_FIND_LINKS \
-u PIP_NO_BINARY -u PIP_ONLY_BINARY -u PIP_PREFER_BINARY -u PIP_CONFIG_FILE \
-u PIP_CACHE_DIR -u PIP_PLATFORM -u PIP_ABI -u PIP_PYTHON_VERSION \
PIP_CONFIG_FILE=/dev/null"

# Run pip inside Debian with a deterministic configuration:
#   PIP_CONFIG_FILE=/dev/null → ignore every pip.conf (Termux + container)
#   env -u PIP_*              → ignore inherited PIP_* environment variables
#   --index-url $index        → explicit index, appended AFTER the subcommand
#                               (pip treats it as a subcommand option)
#   --no-cache-dir            → fresh metadata/files every run (no stale cache)
# $1 = pip subcommand + arguments, already shell-quoted by the caller.
debian_pip() {
    local index="${TERMUX_PIP_INDEX_URL:-$PIP_INDEX_URL_DEFAULT}"
    # shellcheck disable=SC2086
    backend_shell "$PIP_ISOLATE_ENV $VENV_NAME/bin/pip --no-cache-dir $1 --index-url \"$index\""
}

# Version probe — plain `pip --version` only: pip's global parser rejects any
# extra option placed after --version.
debian_pip_version() {
    # shellcheck disable=SC2086
    backend_shell "$PIP_ISOLATE_ENV $VENV_NAME/bin/pip --version"
}

# Explain which wheel platform tags the container's pip supports. When pip
# reports "no matching distributions available for your environment", the cause
# is almost always visible here: the container arch is not aarch64, or its
# glibc is older than a pin's manylinux floor (e.g. pip lists tags only up to
# manylinux_2_24 on a Debian 9 container while a wheel needs 2_26+).
print_guest_platform_diagnostics() {
    warn "Container platform (supported wheel tags decide what pip accepts):"
    run_in_debian "echo \"  arch:   \$(uname -m)\"; echo \"  libc:   \$(ldd --version 2>/dev/null | head -1)\"; echo \"  python: \$(python3 --version 2>&1)\"" || true
    backend_shell "$VENV_NAME/bin/python -m pip debug --verbose 2>/dev/null | grep -m8 -e 'Compatible tags' -e 'manylinux' || true" || true
}

# Install/upgrade all backend dependencies. Wheels only, always: with
# --only-binary :all: pip refuses to compile anything, so a missing prebuilt
# wheel fails in seconds with a clear message instead of a 15-minute hang.
# termux/requirements-constraints.txt pins the native-code packages to versions
# whose manylinux aarch64 wheels are confirmed on PyPI.
install_python_deps() {
    log "Installing backend dependencies (prebuilt wheels only — nothing compiles)..."
    local index="${TERMUX_PIP_INDEX_URL:-$PIP_INDEX_URL_DEFAULT}"
    local constraints="$TERMUX_DIR/requirements-constraints.txt"
    ok "pip index: $index  |  constraints: $(basename "$constraints")"

    if [ "$DEBIAN_PY_BOOTSTRAP" = "uv" ]; then
        # Same wheels-only guarantee as the pip path (uv fallback uses
        # standalone CPython 3.12, whose wheels all exist for the pins).
        backend_shell '"$HOME/.local/bin/uv" pip install --python '"$VENV_NAME"'/bin/python --upgrade --only-binary :all: -e .'
        verify_backend_env
        return 0
    fi

    # Upgrade pip itself with the same isolated config, so an old pip cannot
    # keep rejecting newer manylinux wheel tags. Not fatal: Debian's stock pip
    # already handles every wheel in the constraints file.
    local pip_before pip_after
    pip_before=$(debian_pip_version 2>/dev/null | head -1 || true)
    if ! debian_pip "install --upgrade pip"; then
        warn "pip self-upgrade failed — continuing with: ${pip_before:-unknown}"
    fi
    pip_after=$(debian_pip_version 2>/dev/null | head -1 || true)
    ok "pip: ${pip_after:-unknown}"

    if ! debian_pip "install --upgrade --only-binary :all: --constraint '$constraints' -e ."; then
        err ""
        err "Backend dependency install FAILED (wheels-only mode — pip refused to compile,"
        err "so it failed fast instead of hanging for 15+ minutes)."
        err "  Current index : $index   (override with TERMUX_PIP_INDEX_URL=...)"
        err "  Constraints   : $constraints (pins versions with confirmed aarch64 wheels)"
        echo ""
        print_guest_platform_diagnostics
        echo ""
        err "  If the tags above stop below manylinux_2_17/manylinux2014, or the container"
        err "  holds stale pip state, reset it once (the deploy rebuilds everything):"
        err "      proot-distro reset $DEBIAN_DISTRO   # then re-run: bash termux/deploy.sh"
        die "pip install failed (see above)"
    fi
    verify_backend_env
}

# Fail loudly with a useful message instead of hanging minutes later.
verify_backend_env() {
    log "Verifying backend environment..."
    local out
    if ! out=$(backend_shell "$VENV_NAME/bin/python -c 'import fastapi, pydantic, pydantic_core, sqlalchemy, uvicorn, alembic, psycopg, bcrypt, pwdlib; print(f\"pydantic {pydantic.VERSION} (core {pydantic_core.__version__})\")'" 2>&1); then
        echo "$out" >&2
        die "Backend environment verification failed (see above). Re-run with a clean venv: rm -rf backend/.venv && bash termux/deploy.sh"
    fi
    ok "Imports OK — $out"
}

# Full backend toolchain: Debian → packages → python → venv → deps.
ensure_backend_toolchain() {
    ensure_debian_installed
    ensure_debian_packages
    ensure_debian_python
    ensure_backend_venv
    install_python_deps
}

# ─── Migrations ──────────────────────────────────────────────────────────────
run_migrations() {
    log "Running database migrations (inside Debian)..."
    backend_shell "$VENV_NAME/bin/python -m alembic upgrade head"
    ok "Migrations applied"
}

# ─── Server lifecycle ────────────────────────────────────────────────────────
stop_servers() {
    if [ -f "$PIDFILE" ]; then
        log "Stopping running servers..."
        while read -r pid; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                # || true: process may exit between kill -0 and kill (race).
                kill "$pid" 2>/dev/null && ok "Stopped PID $pid" || true
            fi
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    fi
    # Failsafes for orphaned processes (PIDs change between starts). proot's
    # --kill-on-exit normally cascades; these cover anything left behind.
    pkill -f "uvicorn app.main:app" 2>/dev/null && ok "Killed orphaned uvicorn" || true
    pkill -f "node .output/server/index.mjs" 2>/dev/null && ok "Killed orphaned Nuxt server" || true
    pkill -f "nuxt dev" 2>/dev/null && ok "Killed orphaned nuxt dev" || true
}

wait_for_backend() {
    # Skip silently if curl is unavailable.
    command -v curl >/dev/null 2>&1 || return 0
    local tries="${1:-45}"
    while [ "$tries" -gt 0 ]; do
        if curl -fsS --max-time 2 "http://127.0.0.1:8000/api/v1/live" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        tries=$((tries - 1))
    done
    return 1
}

start_backend() {
    log "Starting backend (Uvicorn inside Debian on :8000)..."
    nohup proot-distro login "$DEBIAN_DISTRO" -- bash -c \
        "${GUEST_PATH_PREFIX}cd $BACKEND_Q && exec $VENV_NAME/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1" \
        >> "$TERMUX_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!
    ok "Backend PID: $BACKEND_PID  (log: termux/backend.log)"
}

# Some Termux/Node combinations cannot execute esbuild's bundled prebuilt
# binary. Detect that at build time and fall back to Termux's system esbuild.
frontend_setup_env() {
    local local_esbuild="$FRONTEND_DIR/node_modules/.bin/esbuild"
    if [ -x "$local_esbuild" ] && "$local_esbuild" --version >/dev/null 2>&1; then
        return 0 # bundled binary works — nothing to do
    fi
    if ! command -v esbuild >/dev/null 2>&1; then
        warn "Bundled esbuild binary not usable; installing Termux's esbuild package"
        pkg install -y esbuild
    fi
    export ESBUILD_BINARY_PATH="${PREFIX}/bin/esbuild"
    warn "Using system esbuild via ESBUILD_BINARY_PATH=$ESBUILD_BINARY_PATH"
}

start_frontend() {
    log "Starting frontend (Nuxt on :3000)..."
    cd "$FRONTEND_DIR"
    frontend_setup_env
    # Propagate frontend/.env to the runtime (HOST/PORT/NITRO_* and the API
    # proxy settings are read from real env vars by the built server too).
    if [ -f "$FRONTEND_ENV" ]; then
        set -a
        # shellcheck disable=SC1090
        . "$FRONTEND_ENV"
        set +a
    fi
    export HOST="${HOST:-0.0.0.0}" PORT="${PORT:-3000}"
    if [ "${TERMUX_DEV:-0}" = "1" ]; then
        nohup npm run dev -- --host 0.0.0.0 --port 3000 \
            >> "$TERMUX_DIR/frontend.log" 2>&1 &
    else
        if [ ! -d ".output" ] || [ "${TERMUX_REBUILD:-0}" = "1" ]; then
            echo "  Building Nuxt (takes a few minutes on the first run)..."
            npm run build > "$TERMUX_DIR/build.log" 2>&1 \
                || die "Nuxt build failed — see termux/build.log"
            ok "Nuxt build complete"
        fi
        nohup node .output/server/index.mjs \
            >> "$TERMUX_DIR/frontend.log" 2>&1 &
    fi
    FRONTEND_PID=$!
    ok "Frontend PID: $FRONTEND_PID  (log: termux/frontend.log)"
}

# start.sh / deploy.sh run run_migrations themselves before calling this.
start_all_servers() {
    start_backend
    start_frontend
    printf '%s\n%s\n' "$BACKEND_PID" "$FRONTEND_PID" > "$PIDFILE"

    if wait_for_backend 45; then
        ok "Backend is live (http://127.0.0.1:8000/api/v1/live)"
    else
        warn "Backend did not answer within 45 s — check termux/backend.log"
    fi
}

print_access_banner() {
    local LAN_IP
    LAN_IP=$(detect_lan_ip)
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║   Servers are running!                       ║"
    echo "╠══════════════════════════════════════════════╣"
    echo "║  Phone (this device): http://localhost:3000  ║"
    if [ "$LAN_IP" != "127.0.0.1" ]; then
        printf '║  Network (LAN): http://%-19s║\n' "$LAN_IP:3000"
    fi
    echo "╠══════════════════════════════════════════════╣"
    echo "║  Logs:  termux/backend.log                   ║"
    echo "║         termux/frontend.log                  ║"
    echo "║  Stop:  bash termux/stop.sh                  ║"
    echo "╚══════════════════════════════════════════════╝"
}

# ─── Admin user seeding ───────────────────────────────────────────────────────
# Called once during first-time setup. Skipped on subsequent deploys unless
# TERMUX_SEED_ADMIN=1 is set explicitly.
seed_admin() {
    local ADMIN_MARKER="$TERMUX_DIR/.admin_seeded"
    if [ -f "$ADMIN_MARKER" ] && [ "${TERMUX_SEED_ADMIN:-0}" != "1" ]; then
        ok "Admin user already seeded (delete termux/.admin_seeded to re-run)"
        return 0
    fi

    echo ""
    echo "  ┌──────────────────────────────────────────────────────────────────┐"
    echo "  │  Create your admin user                                          │"
    echo "  │  This is the account you will use to log in to the app.         │"
    echo "  └──────────────────────────────────────────────────────────────────┘"
    echo ""

    local ADMIN_EMAIL ADMIN_PASSWORD ADMIN_NAME
    read -r -p "  Admin email:     " ADMIN_EMAIL || true
    read -r -s -p "  Admin password (min 12 chars): " ADMIN_PASSWORD || true
    echo ""
    read -r -p "  Full name:       " ADMIN_NAME || true

    if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ] || [ -z "$ADMIN_NAME" ]; then
        warn "Skipping admin seed — run manually later:"
        warn "  SEED_USER_EMAIL=you@example.com SEED_USER_PASSWORD=yourpassword123 \\"
        warn "  SEED_USER_FULL_NAME='Your Name' bash termux/backend-exec.sh python scripts/seed_user.py"
        return 0
    fi

    SEED_USER_EMAIL="$ADMIN_EMAIL" \
    SEED_USER_PASSWORD="$ADMIN_PASSWORD" \
    SEED_USER_FULL_NAME="$ADMIN_NAME" \
    backend_shell "cd $BACKEND_Q && python scripts/seed_user.py"

    touch "$ADMIN_MARKER"
    ok "Admin user created: $ADMIN_EMAIL"
}
# ─── .env writers (shared by setup.sh and deploy.sh) ─────────────────────────
write_backend_env() {
    if [ -f "$BACKEND_ENV" ]; then
        ok "backend/.env already exists"
        return 0
    fi
    local SECRET LAN_IP
    SECRET=$(openssl rand -hex 32)
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
}

write_frontend_env() {
    if [ -f "$FRONTEND_ENV" ]; then
        ok "frontend/.env already exists"
        return 0
    fi
    cat > "$FRONTEND_ENV" <<EOF
NUXT_PUBLIC_API_BASE=/api/v1
NUXT_API_INTERNAL_BASE=http://127.0.0.1:8000
NUXT_API_PROXY_TIMEOUT_MS=30000
HOST=0.0.0.0
EOF
    ok "Created frontend/.env"
}

# Prompt for DATABASE_URL when backend/.env still holds the placeholder.
# Offers both Supabase and SQLite options interactively.
# Returns non-zero (without failing the caller) when the URL is still missing.
prompt_for_database_url() {
    if ! grep -q "postgres\.XXXX:PASSWORD" "$BACKEND_ENV" 2>/dev/null; then
        ok "DATABASE_URL already configured"
        return 0
    fi
    echo ""
    echo "  ┌──────────────────────────────────────────────────────────────────┐"
    echo "  │  ACTION REQUIRED — Choose your database                          │"
    echo "  │                                                                  │"
    echo "  │  1) Supabase / cloud PostgreSQL  (needs internet for data)       │"
    echo "  │  2) SQLite on this phone         (fully offline, data on device) │"
    echo "  └──────────────────────────────────────────────────────────────────┘"
    echo ""
    local CHOICE=""
    read -r -p "  Enter 1 or 2 (or Enter to set DATABASE_URL manually later): " CHOICE || true

    if [ "$CHOICE" = "2" ]; then
        local SQLITE_PATH="$REPO_DIR/data/drilling.db"
        mkdir -p "$REPO_DIR/data"
        local DB_URL_ESCAPED
        DB_URL_ESCAPED=$(printf '%s' "sqlite:////$SQLITE_PATH" | sed -e 's/\\/\\\\/g' -e 's/|/\\|/g' -e 's/&/\\&/g')
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=$DB_URL_ESCAPED|" "$BACKEND_ENV"
        sed -i 's|^# DATABASE_URL=sqlite://.*||' "$BACKEND_ENV"
        ok "SQLite selected — database file: $SQLITE_PATH"
        return 0
    fi

    if [ "$CHOICE" = "1" ]; then
        echo ""
        echo "  Supabase URL format:"
        echo "  postgresql+psycopg://postgres.XXXX:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres"
        echo "  (Supabase → Settings → Database → Connection string → Transaction pooler)"
        echo ""
        local DB_URL=""
        read -r -p "  Paste DATABASE_URL: " DB_URL || true
        if [ -z "$DB_URL" ]; then
            warn "DATABASE_URL not set. Edit backend/.env, then re-run: bash termux/deploy.sh"
            return 1
        fi
        DB_URL="${DB_URL/postgresql:\/\//postgresql+psycopg://}"
        DB_URL="${DB_URL/postgres:\/\//postgresql+psycopg://}"
        local DB_URL_ESCAPED
        DB_URL_ESCAPED=$(printf '%s' "$DB_URL" | sed -e 's/\\/\\\\/g' -e 's/|/\\|/g' -e 's/&/\\&/g')
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=$DB_URL_ESCAPED|" "$BACKEND_ENV"
        ok "DATABASE_URL saved"
        return 0
    fi

    warn "No choice made. Edit backend/.env manually, then re-run: bash termux/deploy.sh"
    return 1
}
