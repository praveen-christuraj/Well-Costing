# Architecture decision records

## ADR-001 — No Docker in the development workflow

**Status:** Accepted  
**Date:** 2026-08-12

### Decision

Developers install Python 3.12, Node LTS, and PostgreSQL 16 directly on Windows. Setup is documented through PowerShell and standard package managers.

### Consequences

- Setup must be reproducible without container knowledge.
- Version prerequisites and database creation are explicit.
- GitHub Actions may use a PostgreSQL service container because that is CI infrastructure, not the local runtime architecture.

## ADR-002 — Modular monolith

**Status:** Accepted  
**Date:** 2026-08-12

### Decision

Use one Nuxt frontend, one FastAPI backend, and one PostgreSQL database, with strict API/service/domain/repository boundaries inside the backend.

### Consequences

- Transactions and debugging stay straightforward.
- Domain calculations remain independently testable.
- Microservice deployment, service discovery, and distributed consistency are avoided.

## ADR-003 — PrimeVue Aura theme

**Status:** Accepted  
**Date:** 2026-08-12

### Decision

Use PrimeVue 4 with the Aura preset and a restrained navy/teal application shell.

### Rationale

Aura provides dense, accessible data-entry controls suitable for the future bulk grids while allowing design tokens and local CSS customization. PrimeVue DataTable is wrapped by `DataTableWrapper.vue` so common density, pagination, sorting, empty states, and future virtualization policies remain centralized.

## ADR-004 — JWT access-token foundation

**Status:** Accepted for Phase 1; production hardening deferred  
**Date:** 2026-08-12

### Decision

Use short-lived signed JWT bearer access tokens and adaptive password hashing: bcrypt everywhere, with Argon2id preferred where the optional `argon2` extra is installed (it publishes no usable aarch64 wheel for the Termux deployment). The API exposes JSON login and current-user endpoints.

### Consequences

- Tokens contain a stable user ID subject and required issue/expiry claims.
- Invalid credentials always return a generic message.
- Refresh tokens, revocation, MFA, password policy, login rate limiting, and final browser token storage are deferred to the security phase.
- The Phase 1 cookie-backed frontend composable is scaffolding, not the final production session strategy.

## ADR-005 — Industry-reference workflow with configurable edges

**Status:** Accepted  
**Date:** 2026-08-12

### Decision

Use the globally recognizable requirement → estimate → AFE → field cost → actual → forecast → reporting workflow documented in `industry-reference-workflow.md`.

The structure is adopted, while formulas and organization-specific policies still require workbook evidence or explicit business confirmation.

### Consequences

- Estimate, AFE, field estimate, commitment, accrual, actual, and forecast are distinct states.
- Approved financial snapshots will not be overwritten.
- Templates, mappings, cost structures, and workflow profiles will be versioned configuration.
- Phase 1 may proceed by explicit sponsor approval even though the Phase 0 workbook package remains incomplete; no business calculations or assumed business tables are introduced by this exception.

## ADR-006 — The AFE is the well requirement

**Status:** Accepted  
**Date:** 2026-08-21

### Decision

Merge well-requirement intake into the AFE. `well_requirements` becomes `afes`
and `requirement_items` becomes `afe_lines`, with the API, Excel profiles, docs,
and UI renamed to match; the separate Well Intake page and requirement detail
page are replaced by one AFE page that holds every entry row.

The rename is complete rather than a UI relabel: two names for one document is
exactly the ambiguity that lets a planner build a scope in one place and an
approver read a different number somewhere else.

### Consequences

- Breaking API change: `/requirements*` is gone, replaced by `/afes` and
  `/afe-lines`, and `/estimates/from-requirement` becomes `/estimates/from-afe`.
- The immutable baseline snapshot keeps the `afe_snapshots` tables and its own
  routes; only its standalone read moved to `/afe-snapshots/{id}` so it no longer
  collides with the AFE document itself. Baseline snapshots stay a separate,
  later artefact — the merge did not blur that boundary.
- ADR-005's chain reads AFE → estimate → baseline AFE snapshot → field cost →
  actual → forecast → reporting; the first two names collapsed into one, the
  sequence did not change.

## ADR-007 — Rate basis is catalogue default plus per-line override

**Status:** Accepted  
**Date:** 2026-08-21

### Decision

A catalogue item carries the rate basis it is normally charged on; an AFE line
copies that as its default and the planner may override it for that line alone.
Services allow `daily`, `per_service`, `per_section`, and `fixed`; mud chemicals
and cement additives allow `per_unit` and `daily_consumption`. A basis outside
the item type's set is rejected.

For a `daily_consumption` line the app computes the total quantity from
consumption per day and planned days. A different quantity is accepted only with
a recorded reason, and the computed figure is kept beside it.

### Consequences

- The classification lives in `app/domain/afe/rate_basis.py`, framework-free and
  unit-tested, so the same rules govern the API, Excel import, and the UI.
- An override is always an explained decision with the app's own figure still
  visible next to it — the audit question "why is this number not what the
  method gives?" has an answer stored on the line.
- What a rate is *worth* is still not decided here. Rate resolution, contingency,
  and escalation remain unimplemented and continue to fail loudly until the
  business rules are confirmed.
