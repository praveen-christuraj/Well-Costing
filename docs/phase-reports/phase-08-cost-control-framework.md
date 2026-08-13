# Phase 8 completion report — Cost Control framework

**Date:** 2026-08-13  
**Mode:** Framework only  
**States:** Field estimate, commitment, accrual, actual, forecast  
**Entry:** Bulk grid/paste + Excel preview  
**Corrections:** Append-only reversal/adjustment lineage  
**Policy:** `pending-all-cost-states`

## Result

Phase 8 is complete for the selected framework scope. All five cost states are separately represented; manual/paste and Excel data can be structurally validated and staged; source and correction lineage are retained; and post attempts are audited. No financial transaction posts because authoritative recognition, allocation, reconciliation, forecasting, and reversal rules are absent.

## Delivered

- Pure typed cost-state/posting contracts and mandated discovery placeholder.
- Audited batch, staged-line, error, post-attempt, and immutable future transaction models.
- Required issued-AFE link for posted transactions; staging may exist before AFE issuance.
- Source document type/reference, external ID, cost/vendor/unit/currency dimensions, amount, and raw input snapshot.
- Original/reversal/adjustment structure with self-referencing immutable lineage.
- Manual bulk validation up to 10,000 rows.
- Versioned Excel mapping, preview, template, and history.
- Cost Control page with state/estimate/version selectors, editable grid, paste, duplicate, Excel preview, validation, blocked posting, and history.
- No update/delete posted-transaction route.

## Safety evidence

- All five states passed separate staging tests.
- Posting returned `cost_state_policy_pending` and committed a blocked actor-attributed attempt.
- PostgreSQL E2E: `forecast|blocked|manual|1|1|0|AFE missing`; policy snapshot and actors present; `cost_transactions=0`; original row has no reversal target.
- Existing estimate/AFE/calculation values remained unchanged.

## Validation

| Check | Result |
|---|---|
| PostgreSQL | 16.14 |
| Migration round trip | Passed through `20260813_0008` |
| PostgreSQL configured-database smoke | 1 passed |
| Backend | 49 passed; 79.79% coverage |
| Ruff / strict Pyright | Passed; 0 errors/warnings |
| Frontend typecheck / ESLint | Passed |
| Vitest | 11 passed across 9 files |
| Production build | Passed |
| npm audit | 0 vulnerabilities |
| Playwright full stack | 3 passed, including blocked Phase 5–8 chain |

The existing Starlette TestClient warning and Vite chunk advisory remain non-failing. Local Python/Node differ from CI targets as previously documented.

## Files added

- `backend/alembic/versions/20260813_0008_add_cost_control_staging_framework.py`
- `backend/app/api/v1/routes/cost_control.py`
- `backend/app/domain/cost_control/{__init__,types,posting}.py`
- `backend/app/models/cost_control.py`
- `backend/app/schemas/cost_control.py`
- `backend/app/services/cost_control.py`
- `backend/tests/integration/test_cost_control_framework.py`
- `backend/tests/unit/test_cost_control_posting_framework.py`
- `frontend/pages/cost-control/index.vue`
- `frontend/composables/useCostControl.ts`
- `frontend/services/costControl.ts`
- `frontend/types/costControl.ts`
- `frontend/tests/unit/services/costControl.spec.ts`
- `docs/api/phase-8.md`
- `docs/database/cost-control.md`
- `docs/architecture/phase-8-decisions.md`
- `docs/rules/phase-8-pending-cost-states.md`
- `docs/phase-reports/phase-08-cost-control-framework.md`

## Files changed

- `backend/app/api/v1/router.py`
- `backend/app/core/exceptions.py`
- `backend/app/integrations/excel/mapper.py`
- `backend/app/models/__init__.py`
- `frontend/components/layout/AppSidebar.vue`
- `frontend/assets/css/main.css`
- `frontend/tests/e2e/requirement-intake.spec.ts`
- `README.md`
- `CHANGELOG.md`

## Blockers/deferred

Before posting: define each state's recognition point; AFE allocation; duplicate/matching/cut-off; currency/tax/gross-net/sign/rounding; state reconciliation; forecast/EAC; reversal authorization/amount/date/period; and certified scenarios.

No industry default was activated, no staged amount was posted, and no posted record can be destructively edited.

## Approval gate

Phase 8 is ready for sponsor review. Do not begin Phase 9 or activate posting without explicit approval. Phase 9 is shared-dimension reporting and drill-through.
