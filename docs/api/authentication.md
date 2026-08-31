# API

Base prefix: `/api/v1`

The restructured application exposes only health and authentication. Module
endpoints return with their modules.

## `GET /live`

Process liveness. Opens no database connection.

```json
{
  "status": "alive",
  "environment": "development",
  "version": "0.1.0"
}
```

## `GET /health`

Checks the database with `SELECT 1` and compares the live schema against what
the code expects. Always returns HTTP 200 for an application-level response,
including when the database is unavailable.

```json
{
  "status": "healthy",
  "database": "connected",
  "environment": "development",
  "version": "0.1.0",
  "schema_status": "current",
  "schema_message": null
}
```

`database` is `connected`, `disconnected`, or `schema_outdated`.

## `GET /ready`

Same payload as `/health`, but returns HTTP 503 while the API cannot reach a
current database. Intended for load-balancer and orchestrator probes.

## `POST /auth/login`

Request:

```json
{
  "email": "engineer@example.com",
  "password": "user-provided-password"
}
```

Response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Credentials are checked against the local `users` table first. When
`SUPABASE_URL` plus an API key are configured, a failed local check falls back
to Supabase Auth's password grant and mirrors the identity locally.

## `GET /auth/me`

Requires `Authorization: Bearer <jwt>`. Returns the safe current-user
projection without password data.

## `POST /auth/refresh`

Requires `Authorization: Bearer <jwt>` (a still-valid token). Returns a fresh
bearer token with the same response shape as login. The frontend calls it
periodically while the application is open so an active session is never
interrupted by an expired token; an expired or invalid token is rejected with
401 — refresh cannot resurrect a dead session.

## Error envelope

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": []
  }
}
```

Stack traces are not returned outside development. Authentication failures use
a generic message. A database error caused by a missing table or column returns
HTTP 503 with `code: "database_schema_outdated"` and the remediation command.
