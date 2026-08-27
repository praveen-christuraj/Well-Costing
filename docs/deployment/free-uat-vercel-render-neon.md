# Free online UAT deployment — Vercel + Render + Neon

## Status and boundary

This is a zero-cost **testing topology**, not production authorization. It provides an online URL for remote testers while preserving the current Nuxt SSR, persistent FastAPI, Alembic, and PostgreSQL architecture.

The deployed build contains authentication and the application shell only — every business module was removed in the restructure. Use synthetic data only.

## Selected topology

```text
Remote tester
    |
    | HTTPS
    v
Vercel Hobby: Nuxt 3 / Nitro SSR (Frankfurt function region)
    |
    | server-side /api/v1 proxy over HTTPS
    v
Render Free: persistent FastAPI web service (Frankfurt)
    |
    | TLS PostgreSQL connection
    v
Neon Free: PostgreSQL 16 (AWS Frankfurt)
```

### Why Neon instead of free Render PostgreSQL

Render's free PostgreSQL instance expires after 30 days and does not receive Render-created logical backups. Neon Free does not use that 30-day database-expiry model, supports PostgreSQL 16, and is sufficient for a small synthetic UAT dataset.

Use:

- Neon's **pooled URL** for `DATABASE_URL` at API runtime.
- Neon's **direct URL** for `MIGRATION_DATABASE_URL`, Alembic, `pg_dump`, and restore operations.

## Zero-cost limitations

### Vercel Hobby

- Free within Hobby quotas.
- Restricted by Vercel's current terms to personal, non-commercial use.
- One function region is sufficient for this UAT.
- Usage is paused when free quotas are exhausted.

Before inviting company users, the account owner must confirm that this evaluation is eligible for Vercel Hobby. If it is considered commercial use, Cloudflare Workers is the preferred zero-cost frontend fallback; otherwise a paid Vercel plan is required.

### Render Free

- Spins down after 15 minutes without inbound traffic.
- The first request after idle can take about one minute to wake the API.
- Provides 750 free instance hours per workspace each month.
- No shell access, one-off jobs, persistent disk, horizontal scaling, or free pre-deploy command.
- Only the two most recent previous deployments are available for service rollback.
- Free resources can be suspended after quota exhaustion or unusually high outbound traffic.

The Nuxt proxy timeout is therefore 90 seconds. This is intentionally unsuitable as a production availability target.

### Neon Free

- PostgreSQL 16 must be selected when creating the project.
- 0.5 GB database storage per project.
- 100 CU-hours per project per month and scale-to-zero after inactivity.
- 5 GB public network transfer per month.
- Limited recovery history and one manual snapshot under the current free plan.

Use small synthetic fixtures and export logical backups regularly.

## Repository deployment files

| File | Purpose |
|---|---|
| `render.yaml` | Free Render FastAPI Blueprint rooted at `backend/`. |
| `backend/.python-version` | Pins the Render native runtime to the latest Python 3.12 patch. |
| `backend/scripts/render_build.sh` | Installs runtime dependencies, migrates with Alembic, and optionally performs the first create-only UAT admin bootstrap. |
| `backend/scripts/bootstrap_uat_admin.py` | Refuses non-UAT or non-empty user stores and never rotates an existing password. |
| `frontend/vercel.json` | Nuxt/Vercel build settings and Frankfurt function region. |
| `backend/.env.example` | Backend variable inventory without secrets. |
| `frontend/.env.example` | Frontend server-only/public variable inventory. |

## Deployment sequence

### 1. Publish the private monorepo

Push the repository to one private GitHub repository. Protect `main` and require the existing GitHub Actions checks.

Do not split `frontend/` and `backend/` into separate repositories.

### 2. Create Neon PostgreSQL

In Neon:

1. Create a Free project in AWS Frankfurt.
2. Select **PostgreSQL 16**.
3. Create a dedicated UAT database/role if the setup flow does not do so.
4. Copy both connection strings:
   - pooled hostname containing `-pooler`;
   - direct hostname without `-pooler`.
5. Retain `sslmode=require` in both URLs.

Do not import the local development database.

### 3. Create the Render API from the Blueprint

In Render:

1. Connect the private GitHub repository.
2. Create a Blueprint from the root `render.yaml`.
3. Confirm the Free instance type and Frankfurt region.
4. Supply prompted variables directly in Render:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon pooled PostgreSQL URL. |
| `MIGRATION_DATABASE_URL` | Neon direct PostgreSQL URL. |
| `CORS_ORIGINS` | Initially `[]`; replace with the exact Vercel HTTPS origin after Vercel is created. |
| `BOOTSTRAP_ADMIN_EMAIL` | A new named UAT administrator email. |
| `BOOTSTRAP_ADMIN_PASSWORD` | A new temporary password of at least 14 characters. |

Render generates `SECRET_KEY`; never copy the local secret.

Because Render Free does not support pre-deploy commands, Alembic runs in the serialized build script. This is a documented free-tier compromise. A future paid deployment must move migrations to a controlled pre-deploy command.

After deployment, verify:

```text
https://<render-service>.onrender.com/api/v1/live
https://<render-service>.onrender.com/api/v1/ready
```

Both must return HTTP 200, and readiness must report `database: connected`.

Immediately after verifying login, delete `BOOTSTRAP_ADMIN_PASSWORD` from Render. The create-only script does not reset an existing user's password, but the bootstrap secret must not remain configured.

### 4. Create the Vercel frontend

In Vercel:

1. Import the same private GitHub repository.
2. Set **Root Directory** to `frontend`.
3. Use the Hobby plan only after confirming plan eligibility.
4. Set Production Branch to `main`.
5. Add these Production environment variables:

```text
NUXT_PUBLIC_API_BASE=/api/v1
NUXT_API_INTERNAL_BASE=https://<render-service>.onrender.com
NUXT_API_PROXY_TIMEOUT_MS=90000
```

`NUXT_API_INTERNAL_BASE` is server-only. Do not rename it with a `NUXT_PUBLIC_` prefix.

Deploy and record the stable `https://<project>.vercel.app` URL.

### 5. Tighten the API origin

Set Render `CORS_ORIGINS` to a JSON list containing the exact stable frontend origin:

```json
["https://<project>.vercel.app"]
```

Redeploy Render. Alembic is idempotent at the existing head; the bootstrap is skipped after its password variable is removed.

### 6. Smoke test through Vercel

Test through the same-origin Nuxt proxy:

```text
https://<project>.vercel.app/api/v1/live
https://<project>.vercel.app/api/v1/ready
```

Then verify:

1. Initial cold request eventually succeeds.
2. UAT administrator can sign in.
3. An unauthenticated protected request returns 401.
4. The dashboard loads and reports a connected database.
5. `/api/v1/health` reports `"schema_status": "current"`.
6. The Master Data stub renders its empty state.
7. No route outside `/live`, `/health`, `/ready`, and `/auth/*` is served.

## Database releases and recovery

### Free-tier migration process

- GitHub checks must pass before Render deploys.
- `render_build.sh` runs `alembic upgrade head` with the direct Neon URL.
- A migration failure stops the Render build.
- Never run migrations from Vercel or from every Uvicorn startup.
- Keep migrations backward-compatible with the prior application artifact.

### Backup before changes

Before each UAT schema or data release:

1. Create the available Neon manual snapshot.
2. Run `pg_dump` with the direct URL and custom format.
3. Store the dump outside Render, Vercel, and the repository.
4. Periodically restore a dump to a disposable Neon branch/project and run readiness checks.

### Rollback

- Roll back the Vercel deployment and Render web service independently.
- Do not automatically run `alembic downgrade`.
- If the upgraded schema remains backward-compatible, keep it and run the previous application artifact.
- For damaging data/schema changes, restore a verified database snapshot/dump, then redeploy the matching application revision.

## UAT data and acceptance boundary

- Use named testers and unique credentials.
- Use only synthetic/non-confidential data on free services.
- Do not upload the local E2E database.
- Enter enterprise configuration one controlled item at a time.
- Safe update, deactivation, version-copy, and complete workflow-profile administration remain separate lifecycle work.
- Publication/activation and all unconfirmed financial behavior remain fail-closed.
- A passing deployment does not certify financial correctness, production security, availability, performance, backup policy, or production authorization.

## Official service references

- Vercel Hobby: <https://vercel.com/docs/plans/hobby>
- Render Free: <https://render.com/docs/free>
- Render Blueprints: <https://render.com/docs/infrastructure-as-code>
- Render FastAPI: <https://render.com/docs/deploy-fastapi>
- Neon plans: <https://neon.com/docs/introduction/plans>
- Neon PostgreSQL compatibility: <https://neon.com/docs/reference/compatibility>
- Neon connection pooling: <https://neon.com/docs/connect/connection-pooling>
