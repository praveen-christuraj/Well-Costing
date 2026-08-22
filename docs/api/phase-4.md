# Phase 4 API

- `GET /api/v1/estimates`
- `POST /api/v1/estimates/from-afe`
- `GET /api/v1/estimates/{id}`
- `PATCH /api/v1/estimates/items/bulk`
- `POST /api/v1/estimates/versions/{version_id}/bulk-assign`
- `POST /api/v1/estimates/versions/{version_id}/duplicate-items`
- `PUT /api/v1/estimates/versions/{version_id}/assumptions`
- `POST /api/v1/estimates/{id}/versions`
- `POST /api/v1/estimates/versions/{version_id}/import/preview`
- `POST /api/v1/estimates/versions/{version_id}/import/commit`
- `GET /api/v1/estimates/versions/{version_id}/template`
- `GET /api/v1/estimates/versions/{version_id}/export`
- `DELETE /api/v1/estimates/{id}` (soft delete — see the deletion procedure in
  `phase-3.md`)
- `POST /api/v1/estimates/{id}/recover`
- `DELETE /api/v1/estimates/{id}/hard` — refused with 409 while an immutable
  baseline AFE snapshot pins one of the estimate's versions

Estimates follow the same audited delete/recover/permanent-delete procedure as
projects, wells, and AFEs, and every estimate mutation writes to the global
audit log. Deleting an estimate permanently is what unblocks permanently
deleting the AFE it was generated from.

No endpoint calculates a financial amount in Phase 4.
