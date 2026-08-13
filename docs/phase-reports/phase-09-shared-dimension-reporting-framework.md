# Phase 9 completion report — Shared-Dimension Reporting framework

**Date:** 2026-08-13  
**Mode:** Framework only  
**Surfaces:** Dashboard, API, Excel  
**Policy:** `pending-shared-cost-reporting`

## Result

Phase 9 is complete for framework scope. It provides 13 shared dimensions, five cost-state cards, source drill-through, chart empty states, deterministic Excel export, and actor/file-hash export audit. No financial KPI was guessed: amount cards, variance-to-AFE, and forecast-at-completion remain null.

## Delivered

- Pure reporting entry/summary contracts and mandated discovery placeholder.
- Filters for project, well, requirement, estimate/version, AFE, state, date, category/code, item nature, vendor, currency, and source document.
- Separate source transaction drill-through.
- Five pending state summaries with structural source-record counts.
- Null variance and EAC plus six-item pending metric register.
- Three-sheet Excel export preserving null metrics.
- `report_export_attempts` with filters, policy, row count, SHA-256, actors, and timestamps.
- Reports dashboard and navigation.

## Validation

| Check | Result |
|---|---|
| PostgreSQL | 16.14 |
| Migration round trip | Passed through `20260813_0009` |
| PostgreSQL configured-database smoke | 1 passed |
| Backend | 51 passed; 80.15% coverage |
| Ruff / strict Pyright | Passed |
| Frontend typecheck / ESLint | Passed |
| Vitest | 12 passed across 10 files |
| Production build / npm audit | Passed; 0 vulnerabilities |
| Playwright | 3 passed, including report dashboard/download |

PostgreSQL E2E confirmed an audited `completed_shell` export under the pending policy, SHA and actor present, zero drill-through rows, and zero posted transactions. Existing non-failing Starlette and Vite advisories remain.

## Files added

- `backend/alembic/versions/20260813_0009_add_report_export_audit_framework.py`
- `backend/app/api/v1/routes/reporting.py`
- `backend/app/domain/reporting/{__init__,types,metrics}.py`
- `backend/app/models/reporting.py`
- `backend/app/schemas/reporting.py`
- `backend/app/services/reporting.py`
- `backend/tests/integration/test_reporting_framework.py`
- `backend/tests/unit/test_reporting_metrics_framework.py`
- `frontend/pages/reports/index.vue`
- `frontend/components/charts/CostStateReportChart.vue`
- `frontend/composables/useReporting.ts`
- `frontend/services/reporting.ts`
- `frontend/types/reporting.ts`
- `frontend/tests/unit/components/CostStateReportChart.spec.ts`
- Phase 9 API/database/architecture/rule documents.

## Changed

API router/model exports, sidebar, global CSS, full-stack regression, README, and CHANGELOG.

## Blockers

Confirm reporting currency/FX, AFE family, state overlap, variance formula/sign, EAC methodology, and period/rounding/reversal/zero-budget treatment with certified scenarios.

## Approval gate

Phase 9 is ready for review. Do not begin Phase 10 without explicit approval. Phase 10 publishes stable reporting views and mapping documentation while keeping the transactional schema private.
