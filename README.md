# Drilling Costing

A modular-monolith web application replacing an interlinked Excel drilling-cost workflow while retaining bulk grid editing and Excel round trips.

## Current delivery status

**Active well-costing workflow.** The released application now follows one source chain: Master Data → AFE → AFE Cost Estimates → Daily Cost and Well Activities. Cost Analytics, Cost Control and Reports read this chain directly; retired Cost Builder versions, snapshots and financial staging batches are not connected to user-facing pages.

AFE lines use the Primary → Secondary classification configured in Master Data. AFE Cost Estimates show those exact user-defined values, while the selected rate basis controls calculation behaviour. Report and Audit Log results can be printed and exported.

A free online UAT deployment path is now prepared for **Vercel Nuxt + Render FastAPI + Neon PostgreSQL 16**. It has not yet been provisioned in provider accounts. See the [free UAT deployment runbook](docs/deployment/free-uat-vercel-render-neon.md), including cold-start, quota, data-recovery, and Vercel Hobby eligibility limitations.

## Architecture

```text
Nuxt 3 / Vue 3 frontend
          | REST/JSON
FastAPI routes (thin)
          |
Application services
          |
Pure Python domain (no framework imports)
          |
SQLAlchemy repositories
          |
PostgreSQL 16
```

See [`docs/architecture/overview.md`](docs/architecture/overview.md) and the [industry-reference workflow](docs/architecture/industry-reference-workflow.md).

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
  "version": "0.1.0"
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
route users to a page that is not enabled yet.

The shell follows the [PrimeVue Sakai](https://github.com/primefaces/sakai-vue)
layout: a grouped sidebar, a topbar with a light/dark switch, and a theme
configurator (preset, primary colour, surface palette, static or overlay menu)
whose choice is remembered between sessions.

**AFE** (`/afe`) is where a well's cost scope is entered — projects, wells, the AFE
itself, and every AFE line on one page. Each line records how it is charged:
daily, per section, per service, fixed, per unit, or on daily usage for chemicals
and additives. The basis pre-fills from the catalogue item and can be changed for
one line; **Section** is a dropdown of the hole sections configured under Master
Data, never free text; and a chemical on daily usage has its total computed from
usage per day times planned days, overridable only with a recorded reason. See
the [AFE data model](docs/database/afe.md) and the [Phase 3 API](docs/api/phase-3.md).

**Master Data** (`/master-data/primary-categories`) maintains the raw reference data
the AFE is built from. One classification — **Primary → Secondary → Tertiary
Categories** — files everything: a catalogue item's category is its Secondary
Category and its sub category its Tertiary Category, and a cost category takes
its parent and second level from the same hierarchy. The register also holds
vendors classified as third-party or in-house, service and purchase orders (kept
purely for reference, never required to link to a service or an item), the
catalogue items themselves — services, tangibles, mud chemicals, cement
additives — and effective-dated tangible rates with a full revision log.
Deleting a tangible removes its rate revisions with it, after a prompt that
states exactly how many records will go. Services
carry no master rate: they are priced per well in the well rate book, so a
central revision never moves a well that is already drilling — see
[well-scoped rate governance](docs/architecture/well-rate-governance.md). Every page has
server-side pagination, filters, Excel-style bulk entry, clipboard paste, per-row
edit and delete actions, an **Export** button that downloads the entity as an Excel
workbook (re-importable unchanged), and a **Print** button that renders the loaded
rows as a clean printable sheet. See
[AFE reference data](docs/master-data/afe-reference-data.md).

Which master-data section feeds which dropdown is itself configurable. Every
picker in the application resolves through a registry of named slots and
permitted sources, and a super administrator repoints them under
**Administration › Dropdown Sources** — see the
[dropdown source registry](docs/master-data/dropdown-source-registry.md).

Master Data supports spreadsheet-style multi-row editing, bulk changes, clipboard paste, validated workbook imports, exports and printable registers. AFE Cost Estimates price the configured AFE scope, Daily Cost records actuals, and Reports generates AFE Register, AFE Cost Estimate Detail, Daily Cost, Cost Performance and Well Activity accountability workbooks.

## Database migrations

From `backend/` with the virtual environment active:

```powershell
alembic upgrade head
alembic current
alembic downgrade base
alembic upgrade head
```

Never modify an applied migration. Add a new revision for subsequent changes.

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

## Authentication scaffolding

The authentication foundation provides:

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- bcrypt password hashing (Argon2id stays primary where the optional `argon2` extra is installed, e.g. cloud; see `backend/pyproject.toml`)
- Signed, expiring JWT access tokens
- Minimal `users`, `roles`, and `user_roles` tables

A production login page, refresh-token strategy, complete role/permission matrix, password policy, and rate limiting are deferred to their approved phases.

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
| `LOG_LEVEL` | Application/audit logger level |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime |
| `API_V1_PREFIX` | Versioned API prefix |
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
backend/app/domain/       Framework-independent costing code
backend/app/repositories/ SQLAlchemy data access
backend/app/models/       Persistence models
backend/app/integrations/ Excel and external-system boundaries
backend/tests/            Unit and integration tests
database/                 Database scripts/documentation placeholders
docs/                     Architecture, database, Excel, rules, testing
 test_data/                Future anonymized files and golden scenarios
```

## Business-rule safety

The Phase 5 calculation boundary raises:

```text
NotImplementedError: Business rule to be confirmed during Excel/business-rule discovery.
```

Calculation, workflow, AFE, and cost-state posting boundaries audit blocked attempts and return `business_rule_pending`, `workflow_profile_pending`, `afe_policy_pending`, and `cost_state_policy_pending`. Do not replace these boundaries until they have authoritative sources and certified regression expectations. See the pending-policy registers under `docs/rules/`.

## Troubleshooting

### Health shows `database: disconnected`

1. Confirm PostgreSQL 16 is running in Windows Services.
2. Verify `DATABASE_URL` in `backend/.env`.
3. Test the same credentials with `psql`.
4. Run `alembic upgrade head`.

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

## Contribution rules

- Keep routes thin and calculations out of Vue components.
- Use application services for transactions/workflows.
- Keep `app/domain/` free from FastAPI, SQLAlchemy, and Pydantic.
- Design all high-volume entry features bulk-first.
- Add audit fields to every future financial/cost table.
- Never commit secrets, source business workbooks, or non-anonymized data.
- Run all quality commands before opening a pull request.
