# Phase 7 completion report — Immutable AFE Baseline framework

**Date:** 2026-08-13  
**Mode:** Framework only  
**Scope:** Original baseline only  
**Trigger:** Explicit request after future eligibility  
**Policy:** `pending-baseline-afe`

## Result

Phase 7 is complete for the selected framework-only scope. It establishes pure baseline snapshot contracts, immutable header/line persistence, calculation/source provenance, audited explicit creation attempts, API boundaries, and a Cost Builder AFE panel.

No AFE was issued. No AFE number, approval eligibility, issue rule, or snapshot content policy was guessed. Explicit requests are audited as blocked and return `afe_policy_pending`.

## Delivered

- Frozen pure-domain AFE source, line, and immutable-result contracts.
- Mandated `NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")` boundary.
- `afe_snapshots`, `afe_snapshot_lines`, and `afe_snapshot_attempts`.
- Unique baseline-per-estimate-version guard and restrictive source/calculation foreign keys.
- Non-null future issued totals/line costs and full copied source snapshot/provenance.
- Eligibility audit containing workflow instance/state, calculation run/rule set, total completeness, line completeness, estimate identity, actor, and timestamps.
- `GET` status, explicit `POST` create, and future immutable `GET` snapshot APIs.
- Frontend baseline status, explicit request, pending policy, error, and attempt trace.
- No update/delete route for issued AFE data.

## Safety invariant verified

Under `pending-baseline-afe`:

1. explicit request is recorded as `blocked`;
2. typed code is `afe_policy_pending`;
3. AFE snapshot count remains zero;
4. AFE line count remains zero;
5. actor IDs and eligibility evidence are present;
6. estimate status remains `pending_calculation`;
7. version/line financial values remain null;
8. revisions and supplements are not modeled as active records.

PostgreSQL E2E evidence:

```text
afe snapshots: 0
afe lines: 0
latest attempt: blocked | eligibility present | actors present | totals_complete=false
estimate: pending_calculation | grand_total null
populated line totals: 0
```

## Validation

| Check | Result |
|---|---|
| PostgreSQL | 16.14 |
| Migration round trip | Passed through `20260813_0007` |
| PostgreSQL configured-database smoke | 1 passed |
| Backend | 46 passed; 78.63% coverage |
| Ruff / strict Pyright | Passed; 0 errors/warnings |
| Frontend typecheck / ESLint | Passed |
| Vitest | 10 passed across 8 files |
| Production build | Passed |
| npm audit | 0 vulnerabilities |
| Playwright full stack | 3 passed, including blocked calculation/workflow/AFE and review note |

The existing Starlette TestClient/HTTPX deprecation warning and Vite chunk-size advisory remain non-failing. Local versions remain Python 3.13.14 and Node 20.20.2; CI targets remain Python 3.12 and Node 22.

## Files added

- `backend/alembic/versions/20260813_0007_add_immutable_afe_snapshot_framework.py`
- `backend/app/api/v1/routes/afe.py`
- `backend/app/domain/afe/__init__.py`
- `backend/app/domain/afe/snapshots.py`
- `backend/app/domain/afe/types.py`
- `backend/app/models/afe.py`
- `backend/app/schemas/afe.py`
- `backend/app/services/afe.py`
- `backend/tests/integration/test_afe_framework.py`
- `backend/tests/unit/test_afe_snapshot_framework.py`
- `frontend/components/afe/AfeSnapshotPanel.vue`
- `frontend/composables/useAfe.ts`
- `frontend/services/afe.ts`
- `frontend/types/afe.ts`
- `frontend/tests/unit/components/AfeSnapshotPanel.spec.ts`
- `docs/api/phase-7.md`
- `docs/database/afe-snapshots.md`
- `docs/architecture/phase-7-decisions.md`
- `docs/rules/phase-7-pending-baseline-afe.md`
- `docs/phase-reports/phase-07-immutable-afe-baseline-framework.md`

## Files changed

- `backend/app/api/v1/router.py`
- `backend/app/core/exceptions.py`
- `backend/app/models/__init__.py`
- `frontend/assets/css/main.css`
- `frontend/pages/cost-builder/[id].vue`
- `frontend/tests/e2e/requirement-intake.spec.ts`
- `README.md`
- `CHANGELOG.md`

## Blockers and deferrals

Required before AFE issuance:

- approved eligible workflow state;
- completed accepted calculation/rule set;
- numbering and ownership policy;
- authoritative snapshot fields and attachments;
- authorization/issue-date/accounting semantics;
- duplicate, cancellation, void, and correction behavior;
- trusted eligible/ineligible/duplicate scenarios.

Revisions and supplements are explicitly deferred under the selected baseline-only scope.

## Approval gate

Phase 7 framework delivery is ready for review. Do not begin Phase 8 or activate AFE issuance without explicit approval. Phase 8 concerns separate field estimates, commitments, accruals, actuals, and forecasts and will require authoritative definitions before active financial behavior.
