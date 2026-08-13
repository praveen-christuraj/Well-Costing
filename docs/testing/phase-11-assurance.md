# Phase 11 assurance evidence

## Regression

- Backend: 53 passed; 80.52% coverage; Ruff and strict Pyright clean.
- Frontend: strict typecheck, ESLint, 13 Vitest tests, production build, and zero npm vulnerabilities.
- Full stack: 3 Playwright tests passed through requirement, estimate, blocked calculation/workflow/AFE/posting, reporting export/contract, and assurance dashboard.
- PostgreSQL 16.14: migration round trip through `20260813_0010` and configured smoke passed.

## Scale

10,000 valid cost-control rows were staged as one audited batch:

- SQLite isolated integration: 2.833 seconds.
- PostgreSQL 16.14 local assurance: 4.886 seconds.
- Result: 10,000 total, 10,000 valid, 0 errors.

These are observed local timings, not a production SLA or concurrency benchmark.

## Structural invariants

Blocked calculation output, pending workflow instances, blocked AFE results, blocked post transactions, transition actors, and post actors all returned zero violations.

## Numeric reconciliation

Blocked: original source workbooks and certified expected scenarios are unavailable. Candidate values in the discovery summary were not treated as acceptance baselines.
