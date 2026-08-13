# Phase 3 completion report — Requirement Intake

**Date:** 2026-08-12  
**Status:** Implementation and local validation complete; awaiting sponsor approval before Phase 4

## Result

Phase 3 implements project → well → requirement intake with a bulk-first requirement-item grid. Users can add, paste, duplicate, bulk save/update/deactivate, import/export Excel, filter requirements, and submit a completed draft. Every requirement line is validated against active Phase 2 catalogue items, cost codes, and units.

The module records supplied planning context only. It performs no trajectory, BHA, hydraulics, casing/cement design, formation evaluation, simulation, or rig-selection logic.

## Main additions

- Migration `20260812_0003_create_requirement_intake.py`
- `projects`, `wells`, `well_requirements`, and `requirement_items`
- Requirement repositories, services, schemas, routes, and Excel service
- Project/well/requirement CRUD and bulk APIs
- Requirement item bulk validate/create/update and deactivation
- Draft → Submitted transition with read-only submitted records
- Explicit unimplemented revision function pending business confirmation
- Requirement-item Excel profile, template, preview, commit, and export
- Project/well/requirement navigation UI
- Bulk requirement grid with paste, lookup dropdowns, planned days/depth fields, import/export, and submission
- Synthetic valid/invalid requirement Excel fixtures
- Full-stack requirement Playwright journey

## Verification

### Backend

| Check | Result |
|---|---|
| PostgreSQL 16 migration upgrade/downgrade/upgrade | PASS |
| Ruff | PASS |
| Strict Pyright | PASS |
| Pytest including all prior phases | PASS — 34 tests |
| Coverage | PASS — 75.01% |
| Project/well/requirement flow | PASS |
| Active-reference rejection | PASS |
| Draft submission/read-only protection | PASS |
| Requirement Excel valid commit | PASS |
| Requirement Excel orphan/no partial commit | PASS |
| Unknown revision rule | PASS — fails with mandated `NotImplementedError` |

### Frontend

| Check | Result |
|---|---|
| Strict Nuxt/TypeScript typecheck | PASS |
| ESLint | PASS |
| Vitest regression suite | PASS — 7 tests |
| Production build | PASS |
| npm audit | PASS — 0 vulnerabilities |
| Playwright | PASS — 3 tests |
| Project → well → requirement → paste → save → submit E2E | PASS against PostgreSQL 16 |

## Acceptance checklist

| Criterion | Status | Notes |
|---|---|---|
| Project list → Well list → Requirement detail | PASS | Live UI and API |
| Many requirement lines entered by paste/import | PASS | TSV and Excel workflows |
| Multi-row edit, duplicate, deactivate, validate/commit | PASS | Draft-only mutation |
| Invalid/inactive master references rejected | PASS | Row/API errors before commit |
| Search/filter by project, well, status | PASS | Paginated backend filters |
| Draft/Submitted status | PASS | No unconfirmed extra states |
| Submitted data protected | PASS | Revision behavior remains pending |
| Requirement Excel profile and round trip | PASS | Version 1.0 synthetic profile |
| Realistic pagination shape | PASS | Server paging and 500-row UI retrieval in Phase 3 |
| Approved Phase 0 scenarios structurally loaded | BLOCKED | Original workbooks and certified scenarios remain unavailable; synthetic structural scenarios pass |
| Prior-phase regression | PASS | Phase 1 and 2 tests remain green |
| Hosted GitHub Actions result | PENDING EXTERNAL RUN | Workflow is configured; no remote run is available in this workspace |

## Deviations and pending decisions

1. The original Phase 0 workbook files and certified scenarios are still absent. Requirement fields are limited to concepts confirmed in the discovery summary: item, cost code, quantity/unit, section, planned days, and unit-aware planned depth.
2. Requirement revision and lock rules are not confirmed. Schema fields support future revisions, but `create_revision()` deliberately raises the mandated `NotImplementedError`.
3. Only Draft and Submitted statuses are implemented. Submitted records are protected as an audit-safety default.
4. No estimate generation, rate matching, or cost calculation has been introduced.
5. Local Python execution used 3.13; CI/type/lint targets remain Python 3.12.

## Explicitly deferred

- Confirmed requirement revision/locking workflow
- Additional requirement states or approvals
- Actual source workbook mappings and certified scenario files
- Cost estimate generation and rate selection
- All costing formulas
- AFE, actual, forecast, dashboard, and reporting modules

## Phase transition

Phase 3 is ready for sponsor review. Phase 4 Bulk Cost Build must not start without explicit approval. Any rate-matching or estimate-assumption behavior not confirmed by business evidence must remain unimplemented.
