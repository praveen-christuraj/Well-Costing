# Phase 1 API

Base prefix: `/api/v1`

## `GET /health`

Checks the database with `SELECT 1`. Always returns HTTP 200 for an application-level health response, including when the database is unavailable.

```json
{
  "status": "healthy",
  "database": "connected",
  "environment": "development",
  "version": "0.1.0"
}
```

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

## `GET /auth/me`

Requires `Authorization: Bearer <jwt>`. Returns the safe current-user projection without password data.

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

Stack traces are not returned outside development. Authentication failures use a generic message.
