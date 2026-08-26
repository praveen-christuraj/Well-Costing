# Phase 3 API — projects, wells, and the AFE

All routes require bearer authentication.

The AFE *is* the well requirement: what used to be entered as a separate "well
requirement" and then copied into an AFE is now one document. The routes below
replaced the former `/requirements` and `/requirement-items` routes.

## Projects

- `GET/POST /api/v1/projects`
- `GET/PATCH/DELETE /api/v1/projects/{id}`
- `POST /api/v1/projects/bulk/create`
- `PATCH /api/v1/projects/bulk/update`
- `POST /api/v1/projects/{id}/recover`
- `DELETE /api/v1/projects/{id}/hard`

## Wells

- `GET/POST /api/v1/wells`
- `GET/PATCH/DELETE /api/v1/wells/{id}`
- `POST /api/v1/wells/bulk/create`
- `PATCH /api/v1/wells/bulk/update`
- `POST /api/v1/wells/{id}/recover`
- `DELETE /api/v1/wells/{id}/hard`
- Filter by project and active status

## AFEs

- `GET/POST /api/v1/afes`
- `GET/PATCH/DELETE /api/v1/afes/{id}`
- `POST /api/v1/afes/bulk/create`
- `PATCH /api/v1/afes/bulk/update`
- `POST /api/v1/afes/{id}/submit`
- `POST /api/v1/afes/{id}/audit/print` (records browser print)
- `POST /api/v1/afes/{id}/recover`
- `DELETE /api/v1/afes/{id}/hard`
- Filter by search, project, well, status, and active state

## AFE lines

- `GET/POST /api/v1/afes/{id}/lines`
- `POST /api/v1/afes/{id}/lines/bulk/validate`
- `POST /api/v1/afes/{id}/lines/bulk/create`
- `PATCH /api/v1/afe-lines/bulk/update`
- `PATCH/DELETE /api/v1/afe-lines/{line_id}`
- `POST /api/v1/afe-lines/{line_id}/recover`
- `GET /api/v1/afes/{id}/lines/removed`

## The deletion procedure (all entities)

Every user-created entry follows the same audited lifecycle so nothing is ever
lost by accident and no deletion can corrupt references:

1. **Soft delete** — `DELETE /{entity}/{id}` sets `is_active = false`. The row
   stays in the database and in the audit trail; lists filter it out.
2. **Recover** — `POST /{entity}/{id}/recover` restores a soft-deleted entry.
   Refused with 409/422 when doing so would create a duplicate (same code, or
   the parent project is itself deleted).
3. **Permanent delete** — `DELETE /{entity}/{id}/hard` requires a soft delete
   first and refuses with **409 Conflict** while other records still reference
   the entry (an AFE with cost estimates, a well with AFEs, a project with
   wells), naming what blocks it. AFE hard delete removes its sections, lines,
   and audit history with it.

Every create, update, soft delete, recover, and permanent delete writes an entry
to the global audit log (`GET /api/v1/audit-logs`), and AFE-level lifecycle
actions additionally write to the per-AFE audit history.

### Current AFE line scope

| Field | Meaning |
| --- | --- |
| `secondary_category_id` + `cost_code_id` | The selected current classification and its configured cost code. |
| `service_type` + `rate_basis` | Scope type and charging method. Consumables use `per_unit` in the current UI. |
| `hole_section_id` | Optional configured hole section; required for `per_section`. |
| `applies_to_all_sections` | Applies one line to every configured section. |
| `notes` | Optional scope note. |

The current AFE Lines UI does **not** request `quantity`, `unit_id`,
`daily_consumption`, or planned duration. Those legacy nullable fields remain
in the API/model only so historical records stay readable. Actual consumable
quantity and UOM are entered on Daily Cost.

## AFE Cost Estimates

- `GET /api/v1/afes/{id}/cost-estimate`
- `PUT /api/v1/afes/{id}/cost-estimate/rates`
- `POST /api/v1/afes/{id}/cost-estimate/audit/print`
- `GET /api/v1/afes/{id}/cost-estimate/export`

These routes accept only a submitted AFE. The current screen maintains one
estimated rate per scope line, with optional vendor and remarks; its browser
print and Excel export are audited.

## Retired AFE-line Excel routes

The legacy catalogue/quantity AFE-line Excel import/export routes are not part
of the active router. Use the current AFE Lines and AFE Cost Estimates modules
instead.

## Historical notes

Baseline snapshot routes belong to the retired estimate workflow and are not part of the active API surface.
