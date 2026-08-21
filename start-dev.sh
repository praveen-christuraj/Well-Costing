#!/usr/bin/env bash
# start-dev.sh — Start both backend and frontend servers for local development
# This script starts both servers and handles cleanup on exit.
# Run from the repository root: bash start-dev.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "Shutting down servers..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null && echo "  Backend stopped (PID $BACKEND_PID)"
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null && echo "  Frontend stopped (PID $FRONTEND_PID)"
    exit 0
}

trap cleanup INT TERM

echo "=== Drilling Costing — Development Server ==="
echo ""

# ── Backend ────────────────────────────────────────────────────────────────────
if [ ! -d "$REPO_DIR/backend/.venv" ]; then
    echo "Backend virtual environment not found. Run:"
    echo "  cd backend && python -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
    exit 1
fi

echo "Running database migrations ..."
cd "$REPO_DIR/backend"
source .venv/bin/activate
if ! python -m alembic upgrade head; then
    echo "ERROR: Migration failed. Check your DATABASE_URL in backend/.env"
    exit 1
fi

echo "Starting backend (FastAPI) on http://localhost:8000 ..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd "$REPO_DIR"

# ── Frontend ───────────────────────────────────────────────────────────────────
if [ ! -d "$REPO_DIR/frontend/node_modules" ]; then
    echo "Frontend dependencies not found. Run:"
    echo "  cd frontend && npm install"
    exit 1
fi

echo "Starting frontend (Nuxt) on http://localhost:3000 ..."
cd "$REPO_DIR/frontend"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!
cd "$REPO_DIR"

echo ""
echo "=== Servers started ==="
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."
echo ""

wait