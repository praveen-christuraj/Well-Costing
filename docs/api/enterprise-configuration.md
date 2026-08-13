# Enterprise configuration API

Read summary: `GET /api/v1/enterprise-config/summary`.

Bootstrap-admin writes:

- `POST /node-types`
- `POST /hierarchy-rules`
- `POST /nodes`
- `POST /cost-structures` and `POST /cost-structures/{id}/nodes`
- `POST /rate-books` and `POST /rate-books/{id}/rates`
- `POST /estimate-templates` and `POST /estimate-templates/{id}/lines`
- `POST /reporting-mappings`

Writes require the active `admin` role and retain actor/timestamp audit. Versioned costing configuration is created as Draft. No publish endpoint is exposed, so configuration cannot silently activate formulas, workflows, rate precedence, or historical reinterpretation.
