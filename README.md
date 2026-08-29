# Drilling Costing

A modular-monolith web application for drilling cost management.

## Current delivery status

**Rebuilt on an empty foundation.** The application was first cut back to its
shell (ADR-008) and the modules are being rebuilt on top of it, one vertical
slice at a time. Daily Cost, Well Activities, Cost Analytics, Cost Control,
Reports, Assurance, Administration and Help are still to come.

What exists today — the shell plus the rebuilt modules:

- Authentication (sign-in, JWT bearer tokens, `users`/`roles`/`user_roles`)
- The PrimeVue application shell: grouped sidebar, topbar, dark mode, theme
  configurator
- A **Dashboard** that reports API, database, and migration state
- **Master Data** at `/master-data` — UOM, currencies, phases, activities, hole
  sections, vendors, PO/SO, and the Services / Consumables / Tangibles catalogues
- **Rig & Well Management** at `/rig-well-management` — rigs, wells and each
  well's section → phase → days configuration
- **AFE Management** at `/afe-management` — well-scoped AFEs and the AFE Cost
  Estimation engine (Services / Consumables / Tangibles → the compiled AFE cost,
  with draft → submitted → approved)
- **Audit Log** at `/audit-logs`

The Alembic history was reset to a single baseline revision
(`20260827_0001_create_auth_tables`). **An existing database cannot be migrated
onto this baseline** — see [Database migrations](#database-migrations).

The rationale and the expectations for a rebuilt module are recorded in
[ADR-008](docs/architecture/decisions.md#adr-008--restructure-to-an-authenticated-empty-shell).

## Architecture

```text
Nuxt 3 / Vue 3 frontend
          | REST/JSON (relative /api/v1 proxy)
FastAPI routes (thin)
          |
Application services
          |
SQLAlchemy repositories
          |
PostgreSQL 16
```

See [`docs/architecture/overview.md`](docs/architecture/overview.md).

The domain layer (`backend/app/domain/`) is back with the AFE module:
`app/domain/afe_costing.py` holds the cost estimation rules as pure functions
over plain dataclasses, and `tests/unit/test_domain_boundaries.py` fails the
build if anything in that package imports FastAPI, SQLAlchemy or Pydantic. No
money is calculated in a Vue component — the browser asks the API to price an
unsaved estimate (`POST /afe/estimates/{id}/preview`).

## Prerequisites — Windows, no Docker

Install these directly on the development workstation:

- Git
- Python 3.12
- Node.js 22 LTS (or newer supported LTS) and npm
- PostgreSQL 16, including `psql`
- VS Code (recommended)

Docker, Kubernetes, and local microservices are intentionally not used.

## 1. Clone and configure

```powershell
git clone <repository-url> drilling-costing
cd drilling-costing
Copy-Item .env.example backend/.env
```

Edit `backend/.env` and replace the local database password and `SECRET_KEY`. Generate a development key with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not commit `.env`.

## 2. Create the PostgreSQL database

Run `psql` as the local PostgreSQL administrator:

```sql
CREATE ROLE drilling_costing WITH LOGIN PASSWORD 'choose-a-local-password';
CREATE DATABASE drilling_costing OWNER drilling_costing;
```

Set the matching URL in `backend/.env`:

```text
DATABASE_URL=postgresql+psycopg://drilling_costing:choose-a-local-password@localhost:5432/drilling_costing
```

## 3. Start the backend

From the repository root in PowerShell:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

To create a local development user, use environment variables rather than putting a password in source control:

```powershell
$env:SEED_USER_EMAIL = "admin@example.com"
$env:SEED_USER_PASSWORD = "choose-a-long-local-password"
$env:SEED_USER_FULL_NAME = "Local Administrator"
python scripts/seed_user.py
Remove-Item Env:SEED_USER_PASSWORD
```

Open:

- API documentation: http://localhost:8000/docs
- Liveness endpoint: http://localhost:8000/api/v1/live
- Compatibility health endpoint: http://localhost:8000/api/v1/health
- Database readiness endpoint: http://localhost:8000/api/v1/ready

Expected healthy response:

```json
{
  "status": "healthy",
  "database": "connected",
  "environment": "development",
  "version": "0.1.0",
  "schema_status": "current",
  "schema_message": null
}
```

The compatibility health endpoint returns a degraded response rather than throwing if PostgreSQL is unavailable. The readiness endpoint returns HTTP 503 when PostgreSQL is unavailable and is the deployment-platform health-check target.

## 4. Start the frontend

Open a second PowerShell terminal:

```powershell
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open http://localhost:3000 and sign in with the local user you seeded. Nuxt calls the backend through the relative `/api/v1` server proxy, so browser code does not hard-code `localhost` API URLs.

The application opens on the **Dashboard**. `frontend/utils/navigation.ts` is the
single source of truth for which top-level modules are released; the sidebar, the
`/` landing route, and the post-login redirect all read from it, so nothing can
route users to a page that is not enabled yet. Today that list is Dashboard and
Master Data.

The shell follows the [PrimeVue Sakai](https://github.com/primefaces/sakai-vue)
layout: a grouped sidebar, a topbar with a light/dark switch, and a theme
configurator (preset, primary colour, surface palette, static or overlay menu)
whose choice is remembered between sessions.

**Master Data** (`/master-data`) is a spreadsheet-style catalogue for UOM,
Currencies, Phases, Activities, Hole Sections, Vendors/Suppliers and PO/SO.
Add a single row or five at a time, paste from Excel, then Save All. Print
outputs the table only (title, filters, data — not the data-entry chrome).

## Database migrations

From `backend/` with the virtual environment active:

```powershell
alembic upgrade head
alembic current
alembic downgrade base
alembic upgrade head
```

Never modify an applied migration. Add a new revision for subsequent changes.

**Reset baseline.** The 28 revisions that built the removed modules were deleted
and replaced by `20260827_0001_create_auth_tables`. A database that already
carries the old tables cannot be upgraded onto this baseline. Drop and recreate
the schema (or provision a new database/branch) and then run
`alembic upgrade head`.

New tables must also be registered in `CRITICAL_SCHEMA` in
`backend/app/db/schema.py`; that mapping is what `/health` compares against the
live database to report `schema_outdated`.

## Backend quality commands

```powershell
cd backend
ruff check .
pyright
pytest --cov=app --cov-report=term-missing
```

The configured database integration test uses PostgreSQL in CI. Isolated repository/API fixtures use SQLite only as a fast test double; PostgreSQL 16 remains the runtime database.

## Frontend quality commands

```powershell
cd frontend
npm run typecheck
npm run lint
npm run test
npm run build
npx playwright install chromium
npm run test:e2e
```

## Free online UAT deployment

The repository contains provider configuration for one private GitHub monorepo:

- `frontend/vercel.json` — Nuxt SSR on Vercel;
- `render.yaml` — FastAPI on a Render Free web service;
- Neon Free PostgreSQL 16 — external database, created in the Neon console;
- `backend/scripts/render_build.sh` — free-tier migration/build path;
- `backend/scripts/bootstrap_uat_admin.py` — create-only initial UAT administrator.

Follow [`docs/deployment/free-uat-vercel-render-neon.md`](docs/deployment/free-uat-vercel-render-neon.md). Free services have cold starts, quotas, limited recovery, and no production SLA. Vercel Hobby eligibility must be confirmed because its free plan is restricted to personal, non-commercial use.

## Authentication

The authentication foundation provides:

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- bcrypt password hashing (Argon2id stays primary where the optional `argon2` extra is installed, e.g. cloud; see `backend/pyproject.toml`)
- Signed, expiring JWT access tokens
- Minimal `users`, `roles`, and `user_roles` tables

A refresh-token strategy, complete role/permission matrix, password policy, and rate limiting are deferred.

A successful sign-in writes a `LOGIN` row to the audit log (failed attempts are not recorded). Catalogue create/update/delete/import/export actions are also audited.

No default administrator password or seeded production credential is committed.

### Hosted user provisioning

No self-service signup is exposed in the application. After the first bootstrap administrator is created, provision additional cloud users directly against the hosted PostgreSQL database with:

```powershell
cd backend
$env:DATABASE_URL = "<direct-hosted-postgresql-url>"
$env:PROVISION_USER_EMAIL = "user@example.com"
$env:PROVISION_USER_PASSWORD = "choose-a-long-password"
$env:PROVISION_USER_FULL_NAME = "Named User"
python scripts/provision_user.py
```

Use a direct Neon or Supabase PostgreSQL connection string when running the provisioning script locally.

### Supabase Auth sign-in

When the backend is connected to a Supabase project, users created in **Supabase Authentication** can sign in through the normal login page without a local password hash. Set the following in `backend/.env`:

```text
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<project settings → API → anon public key>
```

On login, the application first checks the password hash stored in its own `users` table (existing provisioned users and the bootstrap administrator keep working). If that does not match — or the user has no local hash because it was created in Supabase — the backend validates the email and password against Supabase Auth's password grant and mirrors the identity into the application `users` table with `auth_provider='supabase'`. The password itself never touches the application database.

To let a Supabase user administer the application, assign the `admin` role to the mirrored `users` row directly in the database. The mirrored row is created on that user's first successful sign-in.

## Environment variables

| Variable | Purpose |
|---|---|
| `ENVIRONMENT` | `development`, `test`, `uat`, `staging`, or `production` |
| `DATABASE_URL` | Runtime SQLAlchemy PostgreSQL URL; provider `postgresql://` URLs are normalized to Psycopg 3 |
| `MIGRATION_DATABASE_URL` | Optional direct PostgreSQL URL for Alembic; recommended when runtime uses a pooler |
| `SECRET_KEY` | JWT signing secret, minimum 32 characters; development default is rejected in hosted environments |
| `CORS_ORIGINS` | JSON list of allowed browser origins |
| `LOG_LEVEL` | Application logger level |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime |
| `API_V1_PREFIX` | Versioned API prefix |
| `AUTO_MIGRATE` | `development`/`termux` only: apply pending migrations on startup |
| `SUPABASE_URL` | Optional Supabase project URL; enables Supabase Auth sign-in when set with an API key |
| `SUPABASE_ANON_KEY` | Optional Supabase anon/public key used for password sign-in |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional service-role key; used for sign-in when the anon key is absent |
| `NUXT_PUBLIC_API_BASE` | Browser-visible relative API prefix |
| `NUXT_API_INTERNAL_BASE` | Server-only Nuxt API proxy target |
| `NUXT_API_PROXY_TIMEOUT_MS` | Server-proxy timeout; 90 seconds supports Render Free cold starts |

## Repository map

```text
frontend/                 Nuxt/Vue application
backend/app/api/          Thin FastAPI routes and dependencies
backend/app/services/     Workflow orchestration
backend/app/repositories/ SQLAlchemy data access
backend/app/models/       Persistence models
backend/app/integrations/ External-system boundaries (Supabase Auth)
backend/tests/            Unit and integration tests
database/                 Database scripts/documentation placeholders
docs/                     Architecture, database, API, deployment, testing
```

## Contribution rules

- Keep routes thin and calculations out of Vue components.
- Use application services for transactions/workflows.
- A rebuilt domain package must stay free of FastAPI, SQLAlchemy, and Pydantic.
- Design all high-volume entry features bulk-first.
- Add audit fields to every future financial/cost table, and register its tables
  in `CRITICAL_SCHEMA`.
- Never commit secrets, source business workbooks, or non-anonymized data.
- Run all quality commands before opening a pull request.

## Troubleshooting

### Health shows `database: disconnected`

1. Confirm PostgreSQL 16 is running in Windows Services.
2. Verify `DATABASE_URL` in `backend/.env`.
3. Test the same credentials with `psql`.
4. Run `alembic upgrade head`.

### Health shows `database: schema_outdated`

The live database is reachable but missing a table or column the code expects.
Run `cd backend && alembic upgrade head` (the local dev servers do this on
startup) and reload.

### Frontend cannot reach the API

1. Confirm FastAPI is listening on port 8000.
2. Keep `NUXT_PUBLIC_API_BASE=/api/v1`.
3. Confirm `NUXT_API_INTERNAL_BASE=http://127.0.0.1:8000`.
4. Restart `npm run dev` after changing environment variables.

### PowerShell blocks virtual-environment activation

For the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
