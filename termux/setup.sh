#!/data/data/com.termux/files/usr/bin/bash
# setup.sh — First-time Termux setup for drilling-costing
# Run once after cloning the repo: bash termux/setup.sh
#
# Database: Supabase (PostgreSQL in the cloud).
# You must have your Supabase DATABASE_URL ready before running migrations.
# Get it from: Supabase project → Settings → Database → Connection string → URI
# Use the "Transaction" pooler URL (port 6543) for best mobile compatibility.
#
# The Python backend runs inside a proot-distro Debian container (installed
# automatically below) because Termux's bionic Python has no PyPI wheels for
# pydantic-core / uvicorn[standard] — pip compiles them from Rust source and
# appears to hang. Inside Debian everything installs as prebuilt wheels.
# See lib-debian-backend.sh for details.
#
# Tip: `bash termux/deploy.sh` does everything this script does, then prompts
# for the DATABASE_URL, migrates, and starts the servers in one go.
set -euo pipefail

# shellcheck source=lib-debian-backend.sh
. "$(cd "$(dirname "$0")" && pwd)/lib-debian-backend.sh"

echo "=== Drilling Costing — Termux Setup ==="
echo "Repo: $REPO_DIR"

# ── 1. Termux packages ────────────────────────────────────────────────────────
echo ""
echo "[1/5] Installing Termux packages..."
pkg update -y
pkg install -y nodejs git openssl proot-distro

# ── 2. Python environment (Debian container) ──────────────────────────────────
echo ""
echo "[2/5] Creating Python environment inside Debian..."
ensure_debian_installed
ensure_debian_packages
ensure_debian_python
ensure_backend_venv
install_python_deps

# ── 3. Node dependencies ──────────────────────────────────────────────────────
echo ""
echo "[3/5] Installing Node dependencies..."
cd "$FRONTEND_DIR"
npm install
frontend_setup_env

# ── 4. Backend .env ───────────────────────────────────────────────────────────
echo ""
echo "[4/5] Configuring backend environment..."
write_backend_env

# ── 5. Frontend .env ──────────────────────────────────────────────────────────
echo ""
echo "[5/5] Configuring frontend environment..."
write_frontend_env

# Mark first-time setup complete (used by deploy.sh).
touch "$SETUP_MARKER"

LAN_IP=$(detect_lan_ip)
echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Edit backend/.env — set your Supabase DATABASE_URL"
echo "  2. Run migrations:  bash termux/migrate.sh"
echo "  3. Start servers:   bash termux/start.sh"
echo ""
echo "Access the app:"
echo "  On the phone:    http://localhost:3000"
echo "  On your network: http://$LAN_IP:3000"
