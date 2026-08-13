# Power BI mapping — reporting contract v1

## Recommended model

Use `v1_cost_transaction_fact` as the fact table. Relate project, well, cost code, vendor, currency, and AFE dimensions by their stable IDs. Use single-direction dimension-to-fact relationships.

## Safe fields

Identifiers, codes, source transaction dates, source currency/amount, document lineage, state, correction lineage, and audit timestamps are source facts.

## Prohibited derived KPIs until approval

Do not publish AFE variance, committed exposure, accrued-but-not-actual, remaining cost, EAC, currency-converted totals, or cumulative percentages. `v1_reporting_policy` is the machine-readable gate.

## Refresh/security

No refresh SLA, gateway, database principal, RLS policy, or credentials are configured. Use `database/reporting-reader-grants.sql.example` only after production security approval. Never grant Power BI access to transactional schemas.

## Versioning

Pin datasets to `reporting.v1_*`. A future v2 must not silently change v1 columns or meanings.
