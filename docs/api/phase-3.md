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

## Wells

- `GET/POST /api/v1/wells`
- `GET/PATCH/DELETE /api/v1/wells/{id}`
- `POST /api/v1/wells/bulk/create`
- `PATCH /api/v1/wells/bulk/update`
- Filter by project and active status

## AFEs

- `GET/POST /api/v1/afes`
- `GET/PATCH/DELETE /api/v1/afes/{id}`
- `POST /api/v1/afes/bulk/create`
- `PATCH /api/v1/afes/bulk/update`
- `POST /api/v1/afes/{id}/submit`
- Filter by search, project, well, status, and active state

## AFE lines

- `GET/POST /api/v1/afes/{id}/lines`
- `POST /api/v1/afes/{id}/lines/bulk/validate`
- `POST /api/v1/afes/{id}/lines/bulk/create`
- `PATCH /api/v1/afe-lines/bulk/update`
- `PATCH/DELETE /api/v1/afe-lines/{line_id}`

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
