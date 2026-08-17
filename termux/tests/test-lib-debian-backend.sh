#!/usr/bin/env bash
# Regression tests for Termux helpers that do not require an Android device.
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
# shellcheck source=../lib-debian-backend.sh
. "$REPO_ROOT/termux/lib-debian-backend.sh"

TEST_TMP=$(mktemp -d)
trap 'rm -rf "$TEST_TMP"' EXIT

# Point the helper at a fake backend. The fake run_in_debian starts with an
# empty environment, matching proot-distro's relevant behavior.
BACKEND_DIR="$TEST_TMP/backend"
TERMUX_DIR="$TEST_TMP/termux"
BACKEND_Q=$(printf '%q' "$BACKEND_DIR")
mkdir -p "$BACKEND_DIR/.venv/bin" "$BACKEND_DIR/scripts" "$TERMUX_DIR"

cat > "$BACKEND_DIR/.venv/bin/python" <<'FAKE_PYTHON'
#!/usr/bin/env bash
set -euo pipefail
: "${SEED_USER_EMAIL:?missing SEED_USER_EMAIL}"
: "${SEED_USER_PASSWORD:?missing SEED_USER_PASSWORD}"
: "${SEED_USER_FULL_NAME:?missing SEED_USER_FULL_NAME}"
printf 'email=%s\npassword=%s\nname=%s\n' \
    "$SEED_USER_EMAIL" "$SEED_USER_PASSWORD" "$SEED_USER_FULL_NAME" \
    > seed-environment.txt
FAKE_PYTHON
chmod +x "$BACKEND_DIR/.venv/bin/python"
touch "$BACKEND_DIR/scripts/seed_user.py"

run_in_debian() {
    env -i PATH=/usr/bin:/bin bash -c "$1"
}

EMAIL='admin+termux@example.com'
PASSWORD='A complex $password! 2026'
FULL_NAME="O'Brien Admin"
printf '%s\n%s\n%s\n' "$EMAIL" "$PASSWORD" "$FULL_NAME" | seed_admin >/dev/null

EXPECTED=$(printf 'email=%s\npassword=%s\nname=%s' "$EMAIL" "$PASSWORD" "$FULL_NAME")
ACTUAL=$(cat "$BACKEND_DIR/seed-environment.txt")
if [ "$ACTUAL" != "$EXPECTED" ]; then
    printf 'Seed environment mismatch.\nExpected:\n%s\nActual:\n%s\n' \
        "$EXPECTED" "$ACTUAL" >&2
    exit 1
fi

if [ ! -f "$TERMUX_DIR/.admin_seeded" ]; then
    echo 'seed_admin did not create its completion marker' >&2
    exit 1
fi

echo 'Termux backend environment forwarding test passed'
