# Phase 5 architecture decisions

## Framework-only calculation boundary

**Decision:** build typed inputs, outputs, orchestration, audit persistence, API contracts, and frontend trace/result shells while leaving all financial strategies unimplemented.

**Reason:** neither authoritative formulas nor certified expected scenarios have been supplied. An apparently obvious calculation such as quantity multiplied by rate would still be an unapproved business rule.

## Pure domain contract

`app/domain/costing` uses frozen dataclasses and Python standard-library value types. It imports no FastAPI, SQLAlchemy, or Pydantic modules. The application service maps the persisted estimate aggregate into this contract and maps future results back at one transaction boundary.

## Explicit pending rule set

- Engine version: `0.1.0`
- Rule-set version: `pending-full-chain`
- Domain execution raises `NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")`.
- The service converts that discovery boundary to typed API code `business_rule_pending` after auditing the blocked attempt.

Pending strategy groups cover quantity precedence, rate/vendor resolution, FX, contingency, escalation, rounding, subtotals, and grand totals.

## Null financial semantics

Null means not calculated under an approved rule set. Blocked runs cannot populate line costs, breakdowns, or totals. Results are shown as Pending rather than zero.

## Frontend boundary

Vue calls calculate/results endpoints and displays status, nullable summary cards, chart empty state, pending rules, and future category data. It performs no calculation. ECharts is loaded only when completed category data exists, preserving a small and safe empty-state path.
