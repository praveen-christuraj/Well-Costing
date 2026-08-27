# Database overview

## Runtime database

PostgreSQL 16 is the only supported application database. SQLAlchemy 2.x
provides typed ORM access and Alembic owns schema evolution.

## Objects

The restructure dropped every business table, so authentication is the only
persisted concern:

```text
users
  id UUID PK
  email unique
  hashed_password nullable
  auth_provider ("local" | "supabase")
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

`hashed_password` is nullable because a user authenticated exclusively through
Supabase Auth has their password stored by Supabase; such a row carries
`auth_provider = "supabase"` and is mirrored here only so application roles can
be assigned.

## Conventions

Constraint names are deterministic:

- `pk_<table>`
- `fk_<table>_<column>_<referred-table>`
- `uq_<table>_<column>`
- `ix_<column-label>`
- `ck_<table>_<constraint-name>`

Every new table uses `TimestampMixin`, and auditable business records use
`AuditMixin`, from their first migration. Historical actor identifiers may not
be removed merely because a user is deactivated.

New tables must also be registered in `CRITICAL_SCHEMA` in
`backend/app/db/schema.py`. That mapping is what `/health` compares against the
live database, so a table left out of it fails silently instead of being
reported as pending.

## Sessions and transactions

`app/db/session.py` owns the Engine and `SessionLocal`. FastAPI receives one
session per request through `get_db()`. Application services, not route
functions, define transaction boundaries.

## Migrations

The migration history was reset with the restructure. The single baseline
revision is `20260827_0001_create_auth_tables`, which creates `users`, `roles`,
and `user_roles`.

The 28 revisions that built the removed modules are gone, so an existing
database still carrying their tables cannot be migrated onto this baseline.
Recreate it:

```bash
cd backend
python -m alembic downgrade base   # only if the old chain is still installed
python -m alembic upgrade head
```

For a hosted database the practical path is to drop and recreate the schema
(or provision a new branch/database) and then run `alembic upgrade head`.

CI verifies:

```text
upgrade head -> downgrade base -> upgrade head
```

The database URL is read from environment settings; migration files contain no
credentials.

## Testing

CI starts PostgreSQL 16 and runs the migration chain plus a real `SELECT 1`
integration test. Fast isolated fixture tests use SQLite as a test double, not
as a supported deployment database.
