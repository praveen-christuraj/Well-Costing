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

### Line fields that decide how a line is charged

| Field | Meaning |
| --- | --- |
| `hole_section_id` | The configured hole section (`/master-data/hole-sections`) the line belongs to. Replaced the free-text `section_name`. Required when `rate_basis` is `per_section`. |
| `rate_basis` | `daily`, `per_service`, `per_section`, `fixed`, `per_unit`, or `daily_consumption`. Defaults from the catalogue item and may be overridden per line. A basis the item type does not allow is rejected. |
| `daily_consumption` | Usage per day, for chemicals and additives charged on `daily_consumption`. |
| `computed_quantity` | Read-only: `daily_consumption` × `planned_duration_days`, recorded so an override stays visible against the figure the app proposed. |
| `quantity_override_reason` | Required when the supplied `quantity` differs from `computed_quantity`; an unexplained mismatch returns 422. |
| `quantity_source` | Read-only: `entered`, `computed`, or `overridden`. |

`quantity` is optional on a `daily_consumption` line — omit it and the app
computes the total. Changing usage or planned days on a line the app computed
recomputes it; a line with a recorded override keeps the override.

## Excel

- `POST /api/v1/afes/{id}/import/preview`
- `POST /api/v1/afes/{id}/import/commit`
- `GET /api/v1/afes/{id}/import/template`
- `GET /api/v1/afes/{id}/export`

## Baseline AFE snapshots

The immutable baseline snapshot is a separate, later artefact and keeps its own
routes; only the standalone read moved, to avoid colliding with `/afes/{id}`.

- `GET /api/v1/estimates/{id}/afe`
- `POST /api/v1/estimates/{id}/afe/snapshots`
- `GET /api/v1/afe-snapshots/{snapshot_id}` (was `GET /api/v1/afes/{snapshot_id}`)
