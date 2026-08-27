# Testing strategy

## Test pyramid

### Unit tests

Pure Python tests verify configuration, security, and URL-escaping rules
without FastAPI, SQLAlchemy, Pydantic, or a database.

When a business module returns, its calculation rules belong in a
framework-free domain package covered by unit tests, plus an AST-based
import-boundary test that rejects FastAPI, SQLAlchemy, or Pydantic imports
inside it.

### Repository/service tests

Persistence queries and application workflows are tested separately from HTTP.
Transactional workflows receive integration coverage.

### API integration tests

FastAPI `TestClient` tests verify the HTTP contract, authentication, normalized
errors, dependencies, database interactions, and schema-drift reporting.

### Frontend unit/component tests

Vitest and Vue Test Utils cover composables, reusable design-system components,
navigation, and the application shell.

### End-to-end tests

Playwright covers high-value user journeys. Today that is the smoke test that
loads the shell and verifies a signed-out visitor is redirected to sign-in.

## Commands

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

- CI uses PostgreSQL 16 for migrations and the configured database connection
  test.
- In-memory SQLite is allowed only for fast isolated fixture tests.
- Features relying on PostgreSQL-specific behavior require PostgreSQL
  integration tests.

## Golden regression discipline

Numeric modules need certified scenarios before they ship. Reintroduce
`test_data/scenarios/scenario-NNN/` with:

- `description.md`
- `input.json`
- `expected_output.json`
- source/approval metadata

A numeric change then requires an explicit approved business-rule change and a
changelog entry.

## CI gates

A pull request cannot pass when linting, static typing, migrations,
unit/integration tests, build, or smoke E2E fails. Coverage is reported for the
backend with a minimum of 75%.
