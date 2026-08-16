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
