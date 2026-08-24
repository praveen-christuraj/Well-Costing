# AFE data model

```text
projects -> wells -> afes -> afe_lines
                         |        |
                         |        +-> catalog_items
                         |        +-> cost_codes
                         |        +-> units (quantity unit, depth unit)
                         |        +-> hole_sections
                         |-> afe_sections -> afe_section_phases
                         +-> optional superseded AFE
```

Every table has `created_at`, `created_by`, `updated_at`, and `updated_by`.

The AFE tables were the requirement-intake tables: `well_requirements` became
`afes` and `requirement_items` became `afe_lines` in migration
`20260821_0017`, together with `cost_estimates.afe_id`,
`estimate_items.afe_line_id`, and `afe_snapshots.afe_code`. Well requirements
and the AFE were always the same document under two names.

## Sections and phases

An AFE is planned as a sequence of sections (`afe_sections`). A section is
defined first by its hole section and the depth interval it covers
(`planned_depth_from` / `planned_depth_to`). The operational phases inside the
section are entered as child rows in `afe_section_phases`, each with its own
planned days.

- A section's `planned_days` is derived as the sum of the planned days of its
  active phases (`afe_section_phases.planned_days`).
- The AFE's `total_planned_days` is the sum of all its sections' planned days,
  and `total_planned_depth` is the deepest `planned_depth_to`.
- The legacy single `phase` / `planned_days` columns on `afe_sections` remain
  for backward compatibility; new writes carry phases and the service
  recomputes both values from them.

## AFE line fields

Planning context recorded on a line:

- Quantity and unit
- Hole section (a foreign key to `hole_sections`, not free text)
- `applies_to_all_sections` — when true the line's rate applies to every
  section of the AFE, so a common service (for example a rig day rate) is
  entered once instead of being duplicated per section. The `hole_section_id`
  is ignored while the flag is set.
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
