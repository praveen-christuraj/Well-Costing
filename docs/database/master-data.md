# Phase 2 master-data model

## Design

The Cost Library uses explicit relational tables for stable reference data and a `catalog_items` supertype for all rate-bearing items.

```text
cost_categories -> cost_codes
       |               |
       +---- catalog_items ---- units
                  |
       +----------+----------+----------+
       |          |          |          |
    services  tangibles  materials  equipment
                  |
                  +---- rates ---- vendors
                         |   |
                    currencies units

import_batches -> import_errors
```

Joined-table inheritance gives services, tangibles, materials, and equipment separate entity tables while retaining one referentially valid `rates.item_id` foreign key.

## Audit fields

Every Phase 2 table has:

- `created_at`
- `created_by`
- `updated_at`
- `updated_by`

Reference records also have `is_active`. The Phase 2 `DELETE` API deactivates records rather than physically deleting them. This is an audit-preserving technical policy and can be refined only through an approved business decision.

## Identifiers and uniqueness

- Units, currencies, categories, cost codes, and vendors have unique normalized codes.
- Catalogue item codes are unique within item type, allowing the same organization code in different item domains if needed.
- Rate effective date ranges are structurally valid (`effective_to >= effective_from`).
- Rate date-range non-overlap is **not enforced** because precedence/overlap rules are not confirmed.

## Rates

A rate references exactly one catalogue item, vendor, currency, unit, amount, and effective-from date. An optional effective-to date and description are retained. No automatic vendor selection, exchange conversion, escalation, or rate precedence is implemented.

## Import tracking

A preview creates an auditable `import_batches` record even though it creates no business records. The batch stores filename, SHA-256, entity, mapping name/version, counts, status, and normalized staged rows. `import_errors` stores Excel row, column when known, error code, message, and actor metadata.

A commit accepts only a fully validated batch. Business rows and the committed batch status are persisted in one transaction.
