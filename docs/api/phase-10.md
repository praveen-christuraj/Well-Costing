# Phase 10 API — reporting contract v1

`GET /api/v1/reports/contracts/v1` returns the stable contract version, PostgreSQL schema, nine published views, direct-grant status, transactional-schema privacy flag, and pending financial metrics.

Contract v1 is framework-only. Direct database grants are `not_applied`; no reporting principal is created. Existing Phase 9 overview/export APIs remain the authenticated application surfaces.
