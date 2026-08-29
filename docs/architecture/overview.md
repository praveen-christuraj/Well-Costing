# Architecture overview

## Context

The application was restructured down to its foundation (ADR-008) and the
business modules are being rebuilt on top of it. Master Data, Rig & Well
Management, AFE Management and the Audit Log are back; Daily Cost, Well
Activities, Cost Control, Cost Analytics, Reports, Assurance, Administration and
Help are still to come. The shell underneath — authentication, the application
layout, the migration chain and schema-drift reporting — never moved.

See [`decisions.md`](decisions.md#adr-008--restructure-to-an-authenticated-empty-shell)
for the rationale behind the reset, and
[ADR-009](decisions.md#adr-009--the-afe-cost-estimate-is-calculated-in-one-framework-free-engine)
for how the rebuilt AFE module keeps its costing rules in one place.

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

The domain layer (`app/domain/`) is back with the AFE module: a framework-free
package whose pure functions own the AFE cost estimation rules. Nothing in it
imports FastAPI, SQLAlchemy or Pydantic — `tests/unit/test_domain_boundaries.py`
parses the package with `ast` and fails the build if that ever changes. Services
translate database rows into the domain's dataclasses and translate the result
back; the browser never recalculates money, it calls
`POST /afe/estimates/{id}/preview`.

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
