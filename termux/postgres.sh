#!/data/data/com.termux/files/usr/bin/bash
# postgres.sh — Manage the Termux-native PostgreSQL server for drilling-costing.
#
# The deployment scripts do not ship a PostgreSQL server; this helper makes a
# local database on the phone a one-command setup. It reads backend/.env →
# DATABASE_URL (any port — e.g. 127.0.0.1:5433) and uses the host/port/role/
# database from it, so no extra editing is needed.
#
# Usage:
#   bash termux/postgres.sh status   # is the server installed/running/initialized?
#   bash termux/postgres.sh setup    # FIRST TIME: install + initdb + start + create role/db
#   bash termux/postgres.sh start    # start an initialized server
#   bash termux/postgres.sh stop     # stop the server
#   bash termux/postgres.sh init     # initdb only (advanced)
#
#   PGDATA=$HOME/other-data PGPORT=5433 bash termux/postgres.sh start   # overrides
set -euo pipefail

# shellcheck source=lib-debian-backend.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib-debian-backend.sh"

PGDATA="${PGDATA:-$HOME/postgres-data}"
PGLOG="${PGLOG:-$HOME/postgres.log}"

# URL → host/port (defaults 127.0.0.1:5432 when no DATABASE_URL or a non-Postgres URL).
DEFAULT_DB_HOST="127.0.0.1"
DEFAULT_DB_PORT="5432"
DB_URL="$(active_database_url)"
if is_postgres_url "$DB_URL"; then
    read -r DB_HOST DB_PORT < <(database_url_host_port "$DB_URL")
else
    DB_HOST="$DEFAULT_DB_HOST"
    DB_PORT="$DEFAULT_DB_PORT"
fi
PGHOST="${PGHOST:-$DB_HOST}"
PGPORT="${PGPORT:-$DB_PORT}"

# psql must talk TCP; 'localhost' can resolve to ::1 first, which the server
# (started on 127.0.0.1) does not listen on.
PG_CONNECT_HOST="$PGHOST"
[ "$PG_CONNECT_HOST" = "localhost" ] && PG_CONNECT_HOST="127.0.0.1"

usage() {
    cat <<EOF
Termux local PostgreSQL for drilling-costing

Usage:
  bash termux/postgres.sh status    Show install/running state
  bash termux/postgres.sh setup     First time: install → initdb → start → create role/database
  bash termux/postgres.sh start     Start an initialized server
  bash termux/postgres.sh stop      Stop the server
  bash termux/postgres.sh init      Initialize the data directory only

Reads host/port/role/database from backend/.env DATABASE_URL
(current: $DB_HOST:$DB_PORT). Override with PGDATA / PGHOST / PGPORT.
EOF
}

require_postgresql() {
    if ! command -v pg_ctl >/dev/null 2>&1 || ! command -v initdb >/dev/null 2>&1; then
        err "Termux 'postgresql' package is not installed."
        err "  Install it with:  pkg install -y postgresql"
        err "  Then run:         bash termux/postgres.sh setup"
        return 1
    fi
}

cluster_initialized() {
    [ -f "$PGDATA/PG_VERSION" ]
}

# PostgreSQL identifier quoted for SQL (doubles embedded double quotes).
sql_ident() { printf '"%s"' "$(printf '%s' "$1" | sed 's/"/""/g')"; }

# SQL string literal (doubles embedded single quotes).
sql_string() { printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"; }

valid_identifier() {
    [[ "${1:-}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]
}

cmd_status() {
    if ! command -v pg_ctl >/dev/null 2>&1; then
        echo "PostgreSQL: not installed  (pkg install -y postgresql)"
        return 1
    fi
    if ! cluster_initialized; then
        echo "PostgreSQL: installed, data directory not initialized: $PGDATA"
        echo "  Next: bash termux/postgres.sh setup"
        return 1
    fi
    if port_is_listening "$PG_CONNECT_HOST" "$PGPORT"; then
        echo "PostgreSQL: RUNNING on $PGHOST:$PGPORT  (data: $PGDATA, log: $PGLOG)"
        return 0
    fi
    echo "PostgreSQL: installed but NOT running  (data: $PGDATA)"
    echo "  Next: bash termux/postgres.sh start"
    return 1
}

cmd_init() {
    require_postgresql || return 1
    if cluster_initialized; then
        ok "PostgreSQL data directory already initialized: $PGDATA"
        return 0
    fi
    if [ -d "$PGDATA" ] && [ -n "$(find "$PGDATA" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
        err "$PGDATA exists but is not a PostgreSQL data directory."
        err "  Remove it or choose another location:"
        err "    PGDATA=$HOME/other-postgres bash termux/postgres.sh init"
        return 1
    fi
    log "Initializing PostgreSQL data directory: $PGDATA"
    mkdir -p "$PGDATA"
    if ! initdb -D "$PGDATA" -E UTF8; then
        err "initdb failed — see the output above."
        err "  Try again with: rm -rf '$PGDATA' && bash termux/postgres.sh init"
        return 1
    fi
    ok "PostgreSQL cluster initialized: $PGDATA"
    return 0
}

cmd_start() {
    require_postgresql || return 1
    if ! cluster_initialized; then
        err "No PostgreSQL cluster initialized at $PGDATA."
        err "  First time: bash termux/postgres.sh setup"
        return 1
    fi
    if port_is_listening "$PG_CONNECT_HOST" "$PGPORT"; then
        ok "PostgreSQL is already running on $PGHOST:$PGPORT"
        return 0
    fi
    # Listen only on the loopback address the URL names. 'localhost' URLs use
    # 127.0.0.1 because that is what psycopg inside the Debian container dials.
    local listen="127.0.0.1"
    [ "$PGHOST" = "::1" ] && listen="::1"
    log "Starting PostgreSQL on $PGHOST:$PGPORT (data: $PGDATA)..."
    if ! pg_ctl -D "$PGDATA" -l "$PGLOG" -o "-p $PGPORT -h $listen" start; then
        err "PostgreSQL failed to start — log: $PGLOG"
        [ -f "$PGLOG" ] && tail -n 20 "$PGLOG" >&2 || true
        return 1
    fi
    ok "PostgreSQL started on $PGHOST:$PGPORT  (log: $PGLOG)"
    return 0
}

cmd_stop() {
    require_postgresql || return 1
    if ! cluster_initialized; then
        ok "No initialized PostgreSQL cluster ($PGDATA) — nothing to stop."
        return 0
    fi
    if ! port_is_listening "$PG_CONNECT_HOST" "$PGPORT"; then
        ok "PostgreSQL is not running."
        return 0
    fi
    pg_ctl -D "$PGDATA" stop -m fast
    ok "PostgreSQL stopped."
    return 0
}

# Create the role and database named in DATABASE_URL (idempotent). Connects as
# the initdb superuser (the Termux user) over the loopback address.
ensure_role_and_database() {
    if ! command -v psql >/dev/null 2>&1; then
        err "psql is not available — cannot create role/database automatically."
        err "  Install the client: pkg install -y postgresql"
        err "  Then run: bash termux/postgres.sh setup"
        return 1
    fi
    local user password db superuser
    IFS='|' read -r user password db < <(database_url_user_db "$DB_URL")
    # libpq uses the percent-encoded form; PostgreSQL stores the decoded value.
    password=$(percent_decode "$password")
    user=$(percent_decode "$user")
    db=$(percent_decode "$db")
    if ! valid_identifier "$user"; then
        err "Cannot parse a valid role name from DATABASE_URL ('$user')."
        err "  Expected: postgresql+psycopg://ROLENAME:PASSWORD@$PGHOST:$PGPORT/DATABASE"
        return 1
    fi
    if ! valid_identifier "$db"; then
        err "Cannot parse a valid database name from DATABASE_URL ('$db')."
        return 1
    fi
    superuser="$(id -un 2>/dev/null || echo postgres)"

    local role_exists db_exists
    role_exists=$(psql -h "$PG_CONNECT_HOST" -p "$PGPORT" -U "$superuser" -d postgres -tAc \
        "SELECT 1 FROM pg_roles WHERE rolname = '$user'" 2>/dev/null | tr -d ' ' || true)
    if [ "$role_exists" != "1" ]; then
        if [ -n "$password" ]; then
            psql -h "$PG_CONNECT_HOST" -p "$PGPORT" -U "$superuser" -d postgres -v ON_ERROR_STOP=1 \
                -c "CREATE ROLE $(sql_ident "$user") LOGIN PASSWORD $(sql_string "$password");" >/dev/null
        else
            psql -h "$PG_CONNECT_HOST" -p "$PGPORT" -U "$superuser" -d postgres -v ON_ERROR_STOP=1 \
                -c "CREATE ROLE $(sql_ident "$user") LOGIN;" >/dev/null
        fi
        ok "Role '$user' created"
    elif [ -n "$password" ]; then
        psql -h "$PG_CONNECT_HOST" -p "$PGPORT" -U "$superuser" -d postgres -v ON_ERROR_STOP=1 \
            -c "ALTER ROLE $(sql_ident "$user") LOGIN PASSWORD $(sql_string "$password");" >/dev/null
        ok "Role '$user' already exists — password updated"
    else
        ok "Role '$user' already exists"
    fi

    db_exists=$(psql -h "$PG_CONNECT_HOST" -p "$PGPORT" -U "$superuser" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname = '$db'" 2>/dev/null | tr -d ' ' || true)
    if [ "$db_exists" != "1" ]; then
        psql -h "$PG_CONNECT_HOST" -p "$PGPORT" -U "$superuser" -d postgres -v ON_ERROR_STOP=1 \
            -c "CREATE DATABASE $(sql_ident "$db") OWNER $(sql_ident "$user");" >/dev/null
        ok "Database '$db' created (owner: $user)"
    else
        ok "Database '$db' already exists"
    fi
    return 0
}

cmd_setup() {
    log "Setting up local PostgreSQL for drilling-costing ($PGHOST:$PGPORT)..."
    if ! command -v pg_ctl >/dev/null 2>&1; then
        log "Installing Termux 'postgresql' package..."
        pkg install -y postgresql
    fi
    cmd_init || return 1
    cmd_start || return 1
    ensure_role_and_database || return 1
    echo ""
    ok "Local PostgreSQL is ready: $PGHOST:$PGPORT"
    echo "  DATABASE_URL (backend/.env):"
    echo "    postgresql+psycopg://$(database_url_user_db "$DB_URL" | cut -d'|' -f1):*****@$PGHOST:$PGPORT/$(database_url_user_db "$DB_URL" | cut -d'|' -f3)"
    echo "  Next: bash termux/deploy.sh   (runs migrations and starts the app)"
    echo "  Note: PostgreSQL does not survive a phone reboot — run 'bash termux/postgres.sh start'"
    echo "        (or 'bash termux/deploy.sh', which starts it automatically)."
}

CMD="${1:-status}"
case "$CMD" in
    status) cmd_status ;;
    init) cmd_init ;;
    start) cmd_start ;;
    stop) cmd_stop ;;
    setup) cmd_setup ;;
    *) usage; exit 1 ;;
esac
