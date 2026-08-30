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

# ─── Database URL helpers ─────────────────────────────────────────────────────
# These power the "which host/port/role/database did the user configure?" logic
# that replaced the hardcoded localhost:5432 assumptions (fixes the local
# PostgreSQL-on-another-port connection-refused case).
assert_eq() {
    local actual="$1" expected="$2" label="${3:-}"
    if [ "$actual" != "$expected" ]; then
        printf 'FAIL %s\n  expected: [%s]\n  actual:   [%s]\n' "$label" "$expected" "$actual" >&2
        exit 1
    fi
}

assert_eq "$(database_url_host_port 'postgresql+psycopg://drilling_costing:secret@127.0.0.1:5433/drilling_costing')" \
    "127.0.0.1 5433" 'host/port with custom port'
assert_eq "$(database_url_host_port 'postgresql://user:p@db.example.com:6543/postgres?sslmode=require')" \
    "db.example.com 6543" 'host/port with query string'
assert_eq "$(database_url_host_port 'postgresql+psycopg://u:p@localhost/db')" \
    "localhost 5432" 'host without port defaults to 5432'
assert_eq "$(database_url_host_port 'postgresql+psycopg://u:p@[::1]:5433/db')" \
    "::1 5433" 'IPv6 literal with port'
assert_eq "$(database_url_host_port '')" \
    "localhost 5432" 'empty URL defaults to localhost:5432'
assert_eq "$(database_url_host_port 'not-a-db-url')" \
    "not-a-db-url 5432" 'URL without scheme still parses host'

assert_eq "$(database_url_user_db 'postgresql+psycopg://drilling_costing:sec%40ret@127.0.0.1:5433/drilling_costing')" \
    "drilling_costing|sec%40ret|drilling_costing" 'credentials and database name'
assert_eq "$(database_url_user_db 'postgresql://u:p@db.example.com:6543/postgres?sslmode=require')" \
    "u|p|postgres" 'query string stripped from database name'
assert_eq "$(database_url_user_db 'postgresql+psycopg://u:p@localhost/db#frag')" \
    "u|p|db" 'fragment stripped from database name'
assert_eq "$(database_url_user_db 'postgresql+psycopg://localhost/db')" \
    "drilling_costing||db" 'missing credentials fall back to defaults'
assert_eq "$(database_url_user_db 'postgresql+psycopg://u:p@localhost')" \
    "u|p|drilling_costing" 'missing database falls back to default'
assert_eq "$(database_url_user_db 'postgresql+psycopg://drilling_costing@127.0.0.1:5433/drilling_costing')" \
    "drilling_costing||drilling_costing" 'no password in URL means empty password'

if ! is_postgres_url 'postgresql+psycopg://u:p@h:5432/db' \
    || ! is_postgres_url 'postgresql://u:p@h:5432/db' \
    || ! is_postgres_url 'postgres://u:p@h:5432/db' \
    || is_postgres_url 'sqlite:///dev.db' \
    || is_postgres_url ''; then
    echo 'is_postgres_url misclassified a URL' >&2
    exit 1
fi

if ! is_loopback_db_host 'localhost' \
    || ! is_loopback_db_host '127.0.0.1' \
    || ! is_loopback_db_host '::1' \
    || is_loopback_db_host 'db.example.com'; then
    echo 'is_loopback_db_host misclassified a host' >&2
    exit 1
fi

assert_eq "$(percent_decode 'sec%40ret%25')" "sec@ret%" 'percent decoding of password'
assert_eq "$(percent_decode 'plain')" "plain" 'percent decoding leaves plain text'
assert_eq "$(percent_decode 'a%20b')" "a b" 'percent decoding of a space'

# ─── Effective migration URL (DATABASE_URL vs MIGRATION_DATABASE_URL) ────────
# backend/alembic/env.py uses MIGRATION_DATABASE_URL when set, otherwise
# DATABASE_URL. Every preflight/start helper must use the SAME URL; the failure
# this guards against is: DATABASE_URL=localhost:5432 (preflight OK) but
# MIGRATION_DATABASE_URL=127.0.0.1:5433 → migration dies on an unexpected port.
BACKEND_ENV="$BACKEND_DIR/.env"

cat > "$BACKEND_ENV" <<'EOF'
# comment lines must be ignored (last active line wins)
DATABASE_URL=postgresql+psycopg://u:p@localhost:5432/db
MIGRATION_DATABASE_URL=postgresql+psycopg://u:p@127.0.0.1:5433/db
EOF
assert_eq "$(active_database_url)" \
    "postgresql+psycopg://u:p@localhost:5432/db" 'active_database_url reads DATABASE_URL'
assert_eq "$(active_migration_url)" \
    "postgresql+psycopg://u:p@127.0.0.1:5433/db" 'active_migration_url honors MIGRATION_DATABASE_URL'

cat > "$BACKEND_ENV" <<'EOF'
DATABASE_URL=postgresql+psycopg://u:p@127.0.0.1:5432/db
MIGRATION_DATABASE_URL=
EOF
assert_eq "$(active_migration_url)" \
    "postgresql+psycopg://u:p@127.0.0.1:5432/db" 'empty MIGRATION_DATABASE_URL falls back to DATABASE_URL'

cat > "$BACKEND_ENV" <<'EOF'
export DATABASE_URL=postgresql+psycopg://u:p@127.0.0.1:5432/db
# export MIGRATION_DATABASE_URL=postgresql+psycopg://u:p@127.0.0.1:5433/db  (commented; must NOT win)
EOF
assert_eq "$(active_migration_url)" \
    "postgresql+psycopg://u:p@127.0.0.1:5432/db" 'commented migration URL is ignored'

# Conflicting local URLs must be repaired automatically so migrations and the
# app converge on the same server.
cat > "$BACKEND_ENV" <<'EOF'
DATABASE_URL=postgresql+psycopg://u:p@localhost:5432/db
MIGRATION_DATABASE_URL=postgresql+psycopg://u:p@127.0.0.1:5433/db
EOF
repair_migration_url_conflict
assert_eq "$(active_migration_url)" \
    "postgresql+psycopg://u:p@localhost:5432/db" 'conflicting local MIGRATION_DATABASE_URL cleared'
assert_eq "$(env_value_from_backend MIGRATION_DATABASE_URL)" \
    "" 'cleared migration URL is empty'

# A remote (Supabase) migration URL is a legitimate separate endpoint and must
# not be touched.
cat > "$BACKEND_ENV" <<'EOF'
DATABASE_URL=postgresql+psycopg://postgres.xxxx:pw@aws-0-region.pooler.supabase.com:6543/postgres
MIGRATION_DATABASE_URL=postgresql+psycopg://postgres.xxxx:pw@aws-0-region.supabase.com:5432/postgres
EOF
repair_migration_url_conflict
assert_eq "$(active_migration_url)" \
    "postgresql+psycopg://postgres.xxxx:pw@aws-0-region.supabase.com:5432/postgres" \
    'remote MIGRATION_DATABASE_URL left intact'

echo 'Termux backend environment forwarding test passed'
echo 'Termux database URL parsing tests passed'
echo 'Termux effective migration URL tests passed'
