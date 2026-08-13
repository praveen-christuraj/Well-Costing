# Phase 3 API

All routes require bearer authentication.

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

## Requirements

- `GET/POST /api/v1/requirements`
- `GET/PATCH/DELETE /api/v1/requirements/{id}`
- `POST /api/v1/requirements/bulk/create`
- `PATCH /api/v1/requirements/bulk/update`
- `POST /api/v1/requirements/{id}/submit`
- Filter by search, project, well, status, and active state

## Requirement items

- `GET/POST /api/v1/requirements/{id}/items`
- `POST /api/v1/requirements/{id}/items/bulk/validate`
- `POST /api/v1/requirements/{id}/items/bulk/create`
- `PATCH /api/v1/requirement-items/bulk/update`
- `PATCH/DELETE /api/v1/requirement-items/{item_id}`

## Excel

- `POST /api/v1/requirements/{id}/import/preview`
- `POST /api/v1/requirements/{id}/import/commit`
- `GET /api/v1/requirements/{id}/import/template`
- `GET /api/v1/requirements/{id}/export`
