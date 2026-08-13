# Phase 3 requirement-intake data model

```text
projects -> wells -> well_requirements -> requirement_items
                                      |         |
                                      |         +-> catalog_items
                                      |         +-> cost_codes
                                      |         +-> units
                                      +-> optional superseded requirement
```

Every table has `created_at`, `created_by`, `updated_at`, and `updated_by`.

## Requirement item fields

The implemented optional planning-context fields are limited to concepts identified in the Phase 0 discovery summary:

- Quantity and unit
- Section name
- Planned duration in days
- Planned depth from/to and depth unit
- Notes

These fields record supplied planning information. They do not calculate depth, duration, trajectory, casing, cement, BHA, hydraulics, or simulations.

## Status and revision safety

Only `draft` and `submitted` are implemented. Submitted requirements and items are read-only. Revision fields (`revision_number`, `supersedes_id`) exist, but revision creation deliberately raises `NotImplementedError` until the business confirms version/locking behavior.

## Referential validation

Requirement lines must reference active catalogue items, cost codes, quantity units, and optional depth units. Inactive/orphaned references are rejected before commit. Depth ranges require a unit and cannot run backwards.
