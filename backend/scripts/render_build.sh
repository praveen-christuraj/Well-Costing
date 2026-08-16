#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

python -m pip install --upgrade pip
# `.[argon2]` keeps Argon2id as the primary password hasher on cloud (its
# aarch64 wheel limitation only affects Termux), so hashes created before the
# bcrypt switch keep verifying here. bcrypt hashes stay verifiable everywhere.
python -m pip install ".[argon2]"

# Render's Free web service does not provide a pre-deploy command. Migrations therefore run
# once in the serialized build step. MIGRATION_DATABASE_URL should be Neon's direct URL.
python -m alembic upgrade head

# Create-only bootstrap for the first deployment. Remove BOOTSTRAP_ADMIN_PASSWORD from
# Render immediately after the initial account has been verified.
if [[ -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  python scripts/bootstrap_uat_admin.py
elif [[ -n "${BOOTSTRAP_ADMIN_EMAIL:-}" ]]; then
  echo "UAT administrator bootstrap skipped because no bootstrap password is configured."
fi
