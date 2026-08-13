# Architecture overview

## Context

The application begins after upstream well planning. It receives approved costing requirements and manages cost libraries, estimates, AFEs, actuals, forecasts, and reporting. Engineering design and simulation remain external.

## Modular monolith

```text
frontend/
  pages/components/composables
  -> centralized services/apiClient.ts
  -> REST JSON
backend/app/api/
  -> backend/app/services/
  -> backend/app/domain/ (pure business calculations)
  -> backend/app/repositories/
  -> backend/app/models/ and PostgreSQL
```

A single deployable backend preserves clear internal boundaries without distributed-system overhead.

## Dependency direction

- API routes depend on schemas, dependencies, and application services.
- Application services orchestrate repositories, transactions, and domain calls.
- Repositories depend on SQLAlchemy models/session.
- The domain layer depends only on the Python standard library and domain-owned types.
- Frontend code has no direct database path and performs no financial calculations.

An AST-based test rejects FastAPI, SQLAlchemy, or Pydantic imports under `app/domain/`.

## Cross-cutting foundations

- Pydantic settings with environment variables and cached loading
- Structured `app` and `app.audit` loggers
- Stable `{ "error": { "code", "message", "details" } }` failures
- JWT access-token authentication using Argon2 password hashes
- SQLAlchemy naming conventions and Alembic migrations
- Timestamp and future actor-audit mixins
- Centralized frontend API error normalization
- Reusable loading, empty, error, status, page-header, and data-grid shells

## Configuration philosophy

Core financial identities and approved records remain strongly typed. Organization-specific code structures, templates, mappings, rates, workflow profiles, and reporting labels will become versioned configuration in later phases. Arbitrary executable rules will not be stored in configuration.

See [`industry-reference-workflow.md`](industry-reference-workflow.md).

## Deployment shape

Local development uses installed PostgreSQL 16, one FastAPI process, and one Nuxt process. No Docker, Kubernetes, or microservices are used. Production topology will be documented during operational hardening without changing the modular-monolith boundary.
