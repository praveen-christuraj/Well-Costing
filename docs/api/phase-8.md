# Phase 8 API — cost-control staging framework

All routes require authentication.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/cost-control/batches` | List staging/import history across all cost states. |
| `POST` | `/api/v1/cost-control/batches/validate` | Structurally validate and stage up to 10,000 manual/pasted rows. |
| `POST` | `/api/v1/cost-control/imports/preview` | Map, validate, and stage an Excel workbook without posting. |
| `GET` | `/api/v1/cost-control/batches/{id}` | Read rows, errors, lineage, and post attempts. |
| `POST` | `/api/v1/cost-control/batches/{id}/post` | Request immutable posting; audited and blocked while policy is pending. |
| `GET` | `/api/v1/cost-control/template` | Download the versioned staging workbook columns. |

Supported distinct states are `field_estimate`, `commitment`, `accrual`, `actual`, and `forecast`.

Posting returns HTTP 422 code `cost_state_policy_pending` under policy `pending-all-cost-states`. Validated rows remain staged, the batch becomes blocked, an actor-attributed attempt is committed, and no `cost_transactions` row is created.

Structural validation checks required typed fields, master-data code references, and reversal lineage shape. It does not apply recognition, allocation, matching, currency, reconciliation, forecast, or reversal amount rules.
