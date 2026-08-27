# Architecture overview

## Context

The application was restructured down to its foundation. Every business module
— Master Data catalogues, AFE, AFE Cost Estimates, Daily Cost, Well Activities,
Cost Control, Cost Analytics, Reports, Assurance, Audit Log and Administration —
was removed together with its pages, API routes, services, models and database
tables. What remains is the shell those modules will be rebuilt inside:
authentication, the application layout, and an empty Master Data stub.

See [`decisions.md`](decisions.md#adr-008--restructure-to-an-authenticated-empty-shell)
for the rationale and for what a rebuilt module must provide.

## Modular monolith

```text
frontend/
  pages/components/composables
  -> centralized services/apiClient.ts
  -> REST JSON (proxied by server/routes/api/v1/[...path].ts)
backend/app/api/
  -> backend/app/services/
  -> backend/app/repositories/
  -> backend/app/models/ and PostgreSQL
```

A single deployable backend preserves clear internal boundaries without
distributed-system overhead.

## Dependency direction

- API routes depend on schemas, dependencies, and application services.
- Application services orchestrate repositories and transactions.
- Repositories depend on SQLAlchemy models/session.
- Frontend code has no direct database path and performs no calculations.

The domain layer (`app/domain/`) was removed with the costing rules. A rebuilt
module should reintroduce it as a framework-free package with an AST-based
import-boundary test, rather than growing calculation logic inside services.

## Cross-cutting foundations

- Pydantic settings with environment variables and cached loading
- Structured `app` logger
- Stable `{ "error": { "code", "message", "details" } }` failures
- JWT access-token authentication using bcrypt password hashes (Argon2id where
  the `argon2` extra is installed), with optional Supabase Auth sign-in
- SQLAlchemy naming conventions and Alembic migrations
- Timestamp and future actor-audit mixins
- Schema-drift detection: `/health` reports `schema_outdated`, and missing
  tables/columns become an actionable 503 instead of a generic 500
- Centralized frontend API error normalization
- Reusable loading, empty, error, and page-header shells

## What the running application contains

| Area | Routes |
| --- | --- |
| Liveness and health | `GET /api/v1/live`, `GET /api/v1/health`, `GET /api/v1/ready` |
| Authentication | `POST /api/v1/auth/login`, `GET /api/v1/auth/me` |

| Area | Pages |
| --- | --- |
| Unauthenticated | `/login`, `/forgot-password`, `/reset-password` |
| Shell | `/dashboard` (landing) |
| Stub | `/master-data` (intentionally empty) |

## Deployment shape

Local development uses installed PostgreSQL 16, one FastAPI process, and one
Nuxt process. No Docker, Kubernetes, or microservices are used.
