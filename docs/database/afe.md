# AFE data model

```text
projects -> wells -> afes -> afe_lines
                         |        |
                         |        +-> catalog_items
                         |        +-> cost_codes
                         |        +-> units (quantity unit, depth unit)
                         |        +-> hole_sections
                         +-> optional superseded AFE
```

Every table has `created_at`, `created_by`, `updated_at`, and `updated_by`.

The AFE tables were the requirement-intake tables: `well_requirements` became
`afes` and `requirement_items` became `afe_lines` in migration
`20260821_0017`, together with `cost_estimates.afe_id`,
`estimate_items.afe_line_id`, and `afe_snapshots.afe_code`. Well requirements
and the AFE were always the same document under two names.

## AFE line fields

Planning context recorded on a line:

- Quantity and unit
- Hole section (a foreign key to `hole_sections`, not free text)
- Rate basis, and the daily-consumption inputs that follow from it
- Planned duration in days
- Planned depth from/to and depth unit
- Notes

These fields record supplied planning information. They do not calculate depth, duration, trajectory, casing, cement, BHA, hydraulics, or simulations.

## Rate basis

`afe_lines.rate_basis` is checked against
`('daily','per_service','per_section','fixed','per_unit','daily_consumption')`.

The catalogue carries the default: `services.rate_basis` for a service, and
`mud_chemicals.rate_basis` / `cement_additives.rate_basis` for a consumable
(both checked against `('per_unit','daily_consumption')`). A line pre-fills
that default and the planner may change it for that line alone; a basis the
item type does not allow is rejected in `app/domain/afe/rate_basis.py` before
it reaches the database.

`per_section` requires `hole_section_id`.

## Daily consumption

For chemicals and additives charged on daily usage the app derives the total:

```text
computed_quantity = daily_consumption × planned_duration_days
```

`quantity` holds the figure the line is costed on. When it differs from
`computed_quantity` the line must carry a `quantity_override_reason`
(`ck_afe_lines_override_reason_not_blank` keeps it non-blank), so an override
is always an explained decision and the computed figure stays visible beside it.

## Status and revision safety

Only `draft` and `submitted` are implemented. Submitted AFEs and their lines are read-only. Revision fields (`revision_number`, `supersedes_id`) exist, but revision creation deliberately raises `NotImplementedError` until the business confirms version/locking behavior.

## Referential validation

AFE lines must reference active catalogue items, cost codes, quantity units, hole sections, and optional depth units. Inactive/orphaned references are rejected before commit. Depth ranges require a unit and cannot run backwards.
