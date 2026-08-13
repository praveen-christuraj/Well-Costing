# Phase 5 completion report — Costing Engine framework

**Date:** 2026-08-13  
**Delivery mode:** Framework only  
**Engine version:** `0.1.0`  
**Rule-set version:** `pending-full-chain`

## Executive result

Phase 5 is complete for the sponsor-selected framework-only scope. The system now has a pure typed costing contract, application orchestration, audited calculation attempts, persistence and API boundaries, and frontend result/trace shells. It deliberately performs no financial calculation because authoritative formulas and certified expected outputs have not been supplied.

A recalculation request creates an audited input snapshot, invokes the pure domain boundary, receives the mandated discovery `NotImplementedError`, commits the run as `blocked`, and returns typed API code `business_rule_pending`. Line amounts, estimate totals, and output snapshots remain null.

This report does **not** claim numeric acceptance or formula completion.

## Delivered scope

### Pure calculation domain

- Frozen dataclass contracts for estimate lines, rates, assumptions, currency, line results, category totals, and estimate totals.
- A framework-independent `calculate_estimate(EstimateInput)` orchestration boundary.
- Explicit placeholder behavior:

  `NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")`

- AST-based domain-purity regression preventing FastAPI, SQLAlchemy, or Pydantic imports.

### Application and persistence boundaries

- Mapping from persisted estimate versions, lines, rates, units, vendors, categories, and assumptions into the pure input contract.
- Audited `EstimateCalculation` records with input/output JSON snapshots, engine/rule-set versions, run status, message, actor IDs, and timestamps.
- Nullable base, contingency, escalation, and grand totals on estimate versions.
- A single future transactional persistence boundary for completed line and estimate results.
- Blocked attempts commit their audit record before a typed API error is returned.

### API

- `POST /api/v1/estimates/{estimate_id}/calculate`
- `GET /api/v1/estimates/{estimate_id}/results`
- Optional `version_id` targeting on both endpoints.
- Typed `business_rule_pending` details containing run ID, engine version, rule-set version, and the pending-rule register.
- Result responses expose nullable totals, future line/category snapshots, latest status, run history, and pending rules.

### Frontend

- Recalculate action and current calculation status on the Cost Builder.
- Typed calculation service/contracts; no financial math in Vue.
- Base, contingency, escalation, and grand-total cards that show `Pending` for null values.
- ECharts-backed category-breakdown component with a safe empty state until completed data exists.
- Existing line grid retains nullable financial columns as the future line-breakdown shell.
- Expandable pending-rule trace and blocked-calculation message.

## Safety and acceptance evidence

The framework enforces the following invariant while `pending-full-chain` is active:

1. An input snapshot is stored.
2. The run is marked `blocked`.
3. The output snapshot stays null.
4. Every estimate-line financial value stays null.
5. Every estimate-version financial total stays null.
6. The API returns `business_rule_pending`, never a guessed total.
7. The frontend renders Pending/empty-state values, never zero as a substitute.

PostgreSQL E2E inspection after the browser recalculation journey returned:

```text
blocked|0.1.0|pending-full-chain|input present|output null
populated estimate-item financial rows: 0
populated estimate-version total rows: 0
```

## Validation results

| Validation | Result |
|---|---|
| PostgreSQL runtime | 16.14 |
| Alembic `upgrade head → downgrade base → upgrade head` | Passed through `20260812_0005` |
| PostgreSQL configured-database smoke test | 1 passed |
| Backend tests | 40 passed |
| Backend coverage | 76.68% (minimum 75%) |
| Ruff | Passed |
| Strict Pyright | 0 errors, 0 warnings |
| Frontend strict typecheck | Passed |
| ESLint | Passed |
| Vitest | 8 passed across 6 files |
| Nuxt production build | Passed |
| npm audit | 0 vulnerabilities |
| Playwright full-stack regression | 3 passed, including blocked Phase 5 flow |

One pre-existing Starlette `TestClient`/HTTPX deprecation warning remains; no unplanned compatibility migration was made. The production build reports the existing Vite large-chunk advisory, not a build failure.

Local validation used Python 3.13.14 and Node 20.20.2 because Python 3.12 and Node 22 were unavailable in this workspace. Project and CI targets remain Python 3.12 and Node 22.

## Files added

### Backend

- `backend/alembic/versions/20260812_0005_add_calculation_audit_framework.py`
- `backend/app/api/v1/routes/calculations.py`
- `backend/app/domain/costing/types.py`
- `backend/app/models/calculations.py`
- `backend/app/schemas/calculations.py`
- `backend/app/services/calculations.py`
- `backend/tests/integration/test_calculation_framework.py`
- `backend/tests/unit/test_costing_framework.py`

### Frontend

- `frontend/components/charts/EstimateBreakdownChart.vue`
- `frontend/types/calculations.ts`
- `frontend/tests/unit/components/EstimateBreakdownChart.spec.ts`

### Documentation

- `docs/api/phase-5.md`
- `docs/architecture/phase-5-decisions.md`
- `docs/database/calculations.md`
- `docs/rules/phase-5-pending-full-chain.md`
- `docs/phase-reports/phase-05-costing-engine-framework.md`

## Files changed

- `backend/app/api/v1/router.py`
- `backend/app/core/exceptions.py`
- `backend/app/domain/costing/calculations.py`
- `backend/app/models/__init__.py`
- `backend/app/models/estimates.py`
- `backend/app/schemas/estimates.py`
- `backend/app/services/estimates.py`
- `backend/tests/unit/test_domain_isolation.py`
- `frontend/assets/css/main.css`
- `frontend/pages/cost-builder/[id].vue`
- `frontend/services/estimates.ts`
- `frontend/types/estimates.ts`
- `frontend/tests/e2e/requirement-intake.spec.ts`
- `README.md`
- `CHANGELOG.md`

## Deferrals and deviations

### Acceptance blockers — required before numeric implementation

The following approved artifacts are still missing:

- original authoritative source workbooks;
- exact full-chain formulas and precedence rules;
- FX source/date/basis rules;
- contingency and escalation applicability/order rules;
- rounding precision and sequence;
- subtotal and grand-total inclusion/exclusion treatment;
- certified normal, edge, and exception scenarios with expected line/category/estimate values.

Accordingly, the following remain deferred:

- effective quantity calculation;
- rate/vendor selection;
- base cost;
- currency conversion;
- contingency;
- escalation;
- rounding;
- category subtotals;
- grand total;
- numeric golden tests and source-workbook reproduction.

### Deviations

- No business formula was guessed.
- No numeric acceptance was claimed.
- No Docker, microservice, or frontend calculation was introduced.
- The framework-only outcome is the explicitly selected Phase 5 mode, not a scope failure.

## Approval gate

Phase 5 framework delivery is ready for sponsor review. Do not begin a later phase or implement any numeric costing strategy until explicit approval is given and, for numeric implementation, authoritative rules plus certified expected outputs are supplied.
