# Phase 9 API — shared-dimension reporting framework

- `GET /api/v1/reports/cost-overview` — filters, 13 shared dimensions, five state cards, drill-through, and pending metrics.
- `GET /api/v1/reports/cost-overview/export` — deterministic Excel workbook with State Summary, Drill Through, and Pending Metrics sheets; export is audited.

Filters cover project, well, requirement, estimate/version, AFE, cost state, date, category/code, item nature, vendor, currency, and source document.

Under `pending-shared-cost-reporting`, financial amounts, variance-to-AFE, and forecast-at-completion are null. Source transaction amounts may appear only as drill-through facts after posting is activated. The export never substitutes zero for an unresolved metric.
