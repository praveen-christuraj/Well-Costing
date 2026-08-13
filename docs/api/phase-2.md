# Phase 2 API

All endpoints require a bearer token.

## Master data

Base: `/api/v1/master-data/{entity}`

Entities:

- `services`
- `tangibles`
- `materials`
- `equipment`
- `vendors`
- `units`
- `currencies`
- `cost-categories`
- `cost-codes`

Operations:

- `GET /{entity}` — paginated/filterable/sortable list
- `GET /{entity}/{id}`
- `POST /{entity}`
- `PATCH /{entity}/{id}`
- `DELETE /{entity}/{id}` — audit-preserving deactivation
- `POST /{entity}/bulk/validate`
- `POST /{entity}/bulk/create`
- `PATCH /{entity}/bulk/update`

Rates use the same operations under `/api/v1/master-data/rates` with rate-specific schemas.

## Excel

- `POST /api/v1/import/{entity}/preview` — multipart file, optional sheet and mapping JSON
- `POST /api/v1/import/{entity}/commit` — validated batch ID
- `GET /api/v1/import/{entity}/template`
- `GET /api/v1/export/{entity}`
- `GET /api/v1/imports/batches`
- `GET /api/v1/imports/batches/{batch_id}`

## Pagination response

```json
{
  "items": [],
  "page": 1,
  "page_size": 50,
  "total": 0,
  "pages": 0
}
```

## Bulk validation

```json
{
  "valid": false,
  "total_rows": 2,
  "valid_rows": 1,
  "errors": [
    {
      "row_index": 1,
      "column": "code",
      "code": "duplicate_in_batch",
      "message": "Code duplicates row 1"
    }
  ]
}
```
