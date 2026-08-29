# Architecture decision records

## ADR-001 — No Docker in the development workflow

**Status:** Accepted
**Date:** 2026-08-12

### Decision

Developers install Python 3.12, Node LTS, and PostgreSQL 16 directly on
Windows. Setup is documented through PowerShell and standard package managers.

### Consequences

- Setup must be reproducible without container knowledge.
- Version prerequisites and database creation are explicit.
- GitHub Actions may use a PostgreSQL service container because that is CI
  infrastructure, not the local runtime architecture.

## ADR-002 — Modular monolith

**Status:** Accepted
**Date:** 2026-08-12

### Decision

Use one Nuxt frontend, one FastAPI backend, and one PostgreSQL database, with
strict API/service/repository boundaries inside the backend.

### Consequences

- Transactions and debugging stay straightforward.
- Microservice deployment, service discovery, and distributed consistency are
  avoided.

## ADR-003 — PrimeVue Aura theme

**Status:** Accepted
**Date:** 2026-08-12

### Decision

Use PrimeVue 4 with the Aura preset and a restrained navy/teal application
shell.

### Rationale

Aura provides dense, accessible data-entry controls suitable for the bulk grids
a costing module needs, while allowing design tokens and local CSS
customization. The shell — topbar, sidebar, configurator, page header, and the
loading/empty/error panels — is kept and is what rebuilt modules render inside.

## ADR-004 — JWT access-token foundation

**Status:** Accepted; production hardening deferred
**Date:** 2026-08-12

### Decision

Use short-lived signed JWT bearer access tokens and adaptive password hashing:
bcrypt everywhere, with Argon2id preferred where the optional `argon2` extra is
installed (it publishes no usable aarch64 wheel for the Termux deployment). The
API exposes JSON login and current-user endpoints. Supabase Auth may back
sign-in when configured, mirroring the identity into the local `users` table.

### Consequences

- Tokens contain a stable user ID subject and required issue/expiry claims.
- Invalid credentials always return a generic message.
- Refresh tokens, revocation, MFA, password policy, login rate limiting, and
  final browser token storage are deferred to the security phase.
- The cookie-backed frontend composable is scaffolding, not the final
  production session strategy.

## ADR-005 — Industry-reference workflow with configurable edges

**Status:** Superseded by ADR-008 (2026-08-27)

The requirement → estimate → AFE → field cost → actual → forecast → reporting
chain described the removed modules. The decision is preserved here for history;
its artifacts (the `app/domain/` costing package, the AFE and estimate tables,
and the reporting contract) no longer exist in this codebase.

## ADR-006 — The AFE is the well requirement

**Status:** Superseded by ADR-008 (2026-08-27)

Merging well-requirement intake into the AFE was the right call for the module
it governed, but the module itself is gone. Recorded for history.

## ADR-007 — Rate basis is catalogue default plus per-line override

**Status:** Superseded by ADR-008 (2026-08-27)

Rate-basis classification lived in `app/domain/afe/rate_basis.py`, which was
removed with the AFE module. Recorded for history; the rule should be
reintroduced with the rate model that replaces it.

## ADR-008 — Restructure to an authenticated empty shell

**Status:** Accepted
**Date:** 2026-08-27

### Decision

Remove every business module and rebuild from a clean foundation. The
application keeps authentication, the PrimeVue shell, a dashboard that reports
platform health, and an empty Master Data page. Everything else — Master Data
catalogues, AFE, AFE Cost Estimates, Daily Cost, Well Activities, Cost
Analytics, Cost Control, Reports, Assurance, Audit Log, Administration, and
Help — is deleted along with its API routes, services, repositories, models,
Pydantic schemas, domain packages, Excel integration, and database tables.

The Alembic history is reset to one baseline revision
(`20260827_0001_create_auth_tables`) rather than extended with a large drop
migration.

### Rationale

Eleven modules had grown on top of a data model that the business no longer
wants. Rewriting them in place would have meant carrying the old tables,
foreign keys, Excel profiles, and reporting contract through every change.
Starting from a shell that still authenticates, migrates, deploys, and renders
correctly keeps the parts worth keeping and removes the coupling.

### Consequences

- **Breaking:** an existing database cannot be migrated onto the new baseline.
  It must be dropped and recreated, or replaced by a fresh branch.
- The API surface is `/live`, `/health`, `/ready`, `/auth/login`, `/auth/me`.
  Frontend code has no service, type, or composable for a removed module, so
  nothing can call an endpoint that no longer exists.
- `CRITICAL_SCHEMA` now covers only `users`, `roles`, and `user_roles`. A
  rebuilt module must add its tables there or schema drift goes unreported.
- Login no longer writes an audit-log row; the audit module is gone. Re-add
  audit logging when the audit module returns.
- Docs, Excel test fixtures, and scenario data for the removed modules were
  deleted. Only the shell-level architecture, deployment, database, API, and
  testing docs remain.
- A rebuilt module is expected to reintroduce a framework-free domain package
  with an import-boundary test (see [`../testing/strategy.md`](../testing/strategy.md)).

## ADR-009 — The AFE cost estimate is calculated in one framework-free engine

**Status:** Accepted
**Date:** 2026-08-29

### Decision

Rebuild the AFE module with its calculation rules in
`backend/app/domain/afe_costing.py`: pure functions over frozen dataclasses, no
FastAPI, no SQLAlchemy, no Pydantic. The AFE Cost Estimation tab sends its
unsaved lines to `POST /afe/estimates/{id}/preview`, which prices them with the
same code path that `PUT /afe/estimates/{id}` saves, and shows the result. The
browser never recalculates money.

The AFE is well-scoped and its sections and phases are referenced by
**master-data** ids (`hole_sections`, `phases`) rather than by `well_sections`
rows, which a configuration re-save replaces wholesale.

### Rationale

The estimate combines day-based charging (planned days from the well
configuration, or hours/decimal days entered by the user), one-time
mobilization / demobilization / fixed charges, per-section amounts, per-service
lump sums and override rates. Rules that live in two places drift, and a
Vue-side copy would be untestable without a browser. Keeping them in one pure
module means every rule has a unit test and the preview, the save and the print
sheet cannot disagree.

Pointing scope at `well_sections` would have been the obvious modelling choice
and would silently break every AFE the first time a well configuration was
re-saved.

### Consequences

- The eight charge categories, the three charging bases and the estimation rules
  are declared once, in the domain module, and are covered by unit tests.
- A live preview costs one extra request per debounced edit; it writes nothing
  and is not audited.
- Scope that has drifted out of the well configuration is not priced: it is
  reported as a warning on the estimate, so a stale AFE is visible instead of
  quietly wrong.
- Only the AFE itself is soft-deleted; its estimate lines are replaced wholesale
  on save, like the well configuration they mirror.
- `CRITICAL_SCHEMA` covers the seven new tables, so a database missing them
  reports `schema_outdated` instead of failing on the first request.
