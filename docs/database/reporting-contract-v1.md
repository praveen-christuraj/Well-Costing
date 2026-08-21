# PostgreSQL reporting contract v1

Schema: `reporting`; contract version: `1.0`.

## Fact

`reporting.v1_cost_transaction_fact` exposes immutable posted source transactions with AFE snapshot, estimate/version, AFE, well, project, state/date, code/category, nullable item nature, vendor, currency, source amount/document, correction lineage, and posting audit. `source_amount` is a stored fact, not a converted or aggregated KPI.

## Dimensions

- `v1_dim_project`
- `v1_dim_well`
- `v1_dim_cost_code`
- `v1_dim_vendor`
- `v1_dim_currency`
- `v1_dim_afe`

## Metadata

- `v1_reporting_policy` — six financial metrics marked `policy_pending`.
- `v1_contract_metadata` — version, framework status, publication date, metric status, and `direct_grants_status=not_applied`.

Migrations publish/drop views transactionally. Consumers must bind to versioned view names, never private transactional tables.
