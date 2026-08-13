# Phase 5 API — costing-engine framework

Phase 5 exposes a calculation boundary without inventing financial formulas. Authentication is required and errors use the centralized `{ "error": { "code", "message", "details" } }` envelope.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/estimates/{estimate_id}/calculate?version_id={uuid}` | Audit a calculation attempt and invoke the pure domain boundary. |
| `GET` | `/api/v1/estimates/{estimate_id}/results?version_id={uuid}` | Read nullable totals, breakdown snapshots, run history, and pending-rule details. |

Omitting `version_id` targets the estimate's current version.

## Blocked response

Until the full chain is confirmed, calculate returns HTTP 422 with code `business_rule_pending`. Details include the calculation-run ID, engine version `0.1.0`, rule-set version `pending-full-chain`, and seven pending-rule groups. The blocked run is committed before the error is returned.

The results endpoint remains HTTP 200 and reports:

- `calculation_status`: `not_calculated`, `blocked`, or the latest run status;
- nullable base, contingency, escalation, and grand totals;
- line/category result arrays, empty until a completed audited run exists;
- calculation-run history;
- pending-rule descriptions.

A blocked attempt never writes a line amount or estimate total.
