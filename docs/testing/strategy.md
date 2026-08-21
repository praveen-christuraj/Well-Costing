# Testing strategy

## Test pyramid

### Domain unit tests

Pure Python tests verify every costing rule without FastAPI, SQLAlchemy, Pydantic, or a database. Phase 1 uses an import-boundary test and confirms every unknown rule fails with the mandated `NotImplementedError`.

### Repository/service tests

Later phases test persistence queries and application workflows separately. Transactional import and calculation workflows receive integration coverage.

### API integration tests

FastAPI `TestClient` tests verify the HTTP contract, authentication, normalized errors, dependencies, and database interactions.

### Frontend unit/component tests

Vitest and Vue Test Utils cover composables, reusable design-system components, bulk-grid behavior, and workflow state stores.

### End-to-end tests

Playwright covers high-value user journeys. Phase 1 includes a smoke test that loads the shell and verifies locked roadmap modules.

## Phase 1 commands

Backend:

```text
ruff check .
pyright
pytest --cov=app --cov-report=term-missing
```

Frontend:

```text
npm run typecheck
npm run lint
npm run test
npm run build
npm run test:e2e
```

## Database coverage

- CI uses PostgreSQL 16 for migrations and the configured database connection test.
- In-memory SQLite is allowed only for fast isolated fixture tests.
- Features relying on PostgreSQL-specific behavior require PostgreSQL integration tests.

## Golden regression discipline

`test_data/scenarios/scenario-NNN/` will eventually contain:

- `description.md`
- `input.json`
- `expected_output.json`
- source/approval metadata

Later phases extend the same scenarios through AFE, build, estimate, AFE, actual, forecast, and dashboard outputs. Numeric changes require an explicit approved business-rule change and changelog entry.

## CI gates

A pull request cannot pass when linting, static typing, migrations, unit/integration tests, build, or smoke E2E fails. Coverage is reported for the backend with a Phase 1 minimum of 75%.
