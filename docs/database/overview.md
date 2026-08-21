# Database overview

## Runtime database

PostgreSQL 16 is the only supported application database. SQLAlchemy 2.x provides typed ORM access and Alembic owns schema evolution.

## Phase 1 objects

```text
users
  id UUID PK
  email unique
  hashed_password
  full_name
  is_active
  last_login_at
  created_at / updated_at

roles
  id UUID PK
  name unique
  description
  is_active
  created_at / updated_at

user_roles
  user_id FK -> users
  role_id FK -> roles
  composite PK
  created_at / updated_at
```

Phase 2 adds the Cost Library and import tracking described in [`master-data.md`](master-data.md). Phase 3 adds project/well/AFE preparation described in [`afe.md`](afe.md). Estimate, AFE, actual, forecast, and reporting tables do not yet exist.

## Conventions

Constraint names are deterministic:

- `pk_<table>`
- `fk_<table>_<column>_<referred-table>`
- `uq_<table>_<column>`
- `ix_<column-label>`
- `ck_<table>_<constraint-name>`

All later financial tables must use `TimestampMixin` and `AuditMixin` from their first migration. Historical actor identifiers may not be removed merely because a user is deactivated.

## Sessions and transactions

`app/db/session.py` owns the Engine and `SessionLocal`. FastAPI receives one session per request through `get_db()`. Application services, not route functions, will define workflow transaction boundaries as write features arrive.

## Migrations

The first revision is `20260812_0001_create_auth_tables`. CI verifies:

```text
upgrade head -> downgrade base -> upgrade head
```

The database URL is read from environment settings; migration files contain no credentials.

## Testing

CI starts PostgreSQL 16 and runs the migration chain plus a real `SELECT 1` integration test. Fast isolated fixture tests use SQLite as a test double, not as a supported deployment database.
