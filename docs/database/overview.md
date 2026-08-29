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

The rebuilt business modules add their own tables (master data, catalogues,
`rigs` / `wells` / `well_sections` / `well_phases`, and the AFE tables below).
Each migration is the authoritative description of its columns.

### AFE Management

```text
afes
  id serial PK
  afe_code unique            -- manual, never duplicated
  afe_name
  afe_type                   -- "Drilling" | "Completion"
  rig_id FK -> rigs
  well_id FK -> wells        -- an AFE is always well-scoped
  remarks
  status                     -- "draft" | "submitted" | "approved"
  status_remarks / submitted_at / approved_at
  is_deleted / deleted_at    -- soft delete -> Deleted Entries tab
  created_at / updated_at / created_by / updated_by

afe_service_lines            -- one service added to an AFE
  id serial PK
  afe_id FK -> afes
  service_id FK -> services  -- from the Master Data services list
  charging_basis             -- "Daily Rate" | "Per Service Rate" | "Per Section Rate"
  section_id FK -> hole_sections (nullable)   -- master-data ids on purpose, see below
  phase_id FK -> phases (nullable)
  per_service_amount / effective_date / remarks / sort_order

afe_service_rates            -- the rate card: one row per charge category
  line_id FK -> afe_service_lines, category, unit_rate
  unique (line_id, category)

afe_service_charge_lines     -- day-based quantities (days or hours 0-24)
  line_id FK, category, quantity, quantity_unit ("days" | "hours"), sort_order

afe_service_section_rates    -- per-section amounts (optionally per phase)
  line_id FK, section_id FK -> hole_sections, phase_id FK -> phases, amount

afe_consumable_lines         -- consumables, scoped to a section and/or a phase
  afe_id FK, item_kind ("mud_chemical" | "drill_bit"), item_id,
  item_code / item_name (snapshot), quantity, captured_rate, override_rate,
  uom, currency, section_id, phase_id, remarks, sort_order

afe_tangible_lines           -- tangibles with an optional override rate
  afe_id FK, tangible_id FK -> tangibles, quantity, captured_rate,
  override_rate, uom, currency, remarks, sort_order
```

Two deliberate choices:

- **Only the AFE is soft-deleted.** It is the user's entry, so a delete moves it
  to Deleted Entries. Its estimate lines are part of the AFE and are replaced
  wholesale when an estimate is saved — the same lifecycle the well
  configuration uses.
- **Sections and phases reference the master-data ids** (`hole_sections`,
  `phases`) rather than `well_sections` rows. Saving a well configuration
  replaces those rows, so pointing at them would silently invalidate every AFE
  scope; the estimation engine resolves the master ids against the current
  configuration instead.

`afe_consumable_lines.item_id` has no foreign key because the item can come
from either `mud_chemicals` or `drill_bits`; `item_kind` selects the list and
the code, name, UOM and captured rate are snapshotted on the row.

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
