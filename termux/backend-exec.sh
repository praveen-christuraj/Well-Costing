#!/data/data/com.termux/files/usr/bin/bash
# backend-exec.sh — Run any backend command inside the Debian container's venv.
#
# The backend's Python lives in proot-distro Debian (Termux's Python cannot run
# it). Use this wrapper whenever documentation tells you to
# "cd backend && source .venv/bin/activate && ...":
#
#   bash termux/backend-exec.sh python scripts/seed_user.py
#   bash termux/backend-exec.sh alembic current
#   bash termux/backend-exec.sh pytest
#
# SEED_USER_* / DATABASE_URL / MIGRATION_DATABASE_URL variables exported in
# Termux are forwarded into the container, e.g.:
#
#   SEED_USER_EMAIL=admin@example.com SEED_USER_PASSWORD=secret \
#     bash termux/backend-exec.sh python scripts/seed_user.py
set -euo pipefail

# shellcheck source=lib-debian-backend.sh
. "$(cd "$(dirname "$0")" && pwd)/lib-debian-backend.sh"

if [ $# -lt 1 ]; then
    echo "Usage: bash termux/backend-exec.sh <command> [args...]" >&2
    echo "Example: bash termux/backend-exec.sh python scripts/seed_user.py" >&2
    exit 2
fi

if [ ! -f "$VENV_MARKER" ]; then
    die "No Debian-managed virtualenv found. Run 'bash termux/deploy.sh' first."
fi

# Resolve bare tool names against the venv (python → .venv/bin/python).
CMD="$1"
shift
if ! [[ "$CMD" == */* ]] && [ -x "$VENV_DIR/bin/$CMD" ]; then
    CMD="$VENV_NAME/bin/$CMD"
fi

# Forward selected environment variables into the container.
ENV_ARGS=""
for VAR in SEED_USER_EMAIL SEED_USER_PASSWORD SEED_USER_FULL_NAME \
           DATABASE_URL MIGRATION_DATABASE_URL ENVIRONMENT LOG_LEVEL; do
    if [ -n "${!VAR:-}" ]; then
        printf -v ESC '%q' "${!VAR}"
        ENV_ARGS+="$VAR=$ESC "
    fi
done

# "$@" is expanded inside the guest (the literal token 'backend-cmd' is $0).
# shellcheck disable=SC2016
exec proot-distro login "$DEBIAN_DISTRO" -- \
    bash -c "${GUEST_PATH_PREFIX}cd $BACKEND_Q && ${ENV_ARGS}exec \"\$@\"" backend-cmd "$CMD" "$@"
