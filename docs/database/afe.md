# AFE data model

```text
projects -> wells -> afes -> afe_lines
                         |        |
                         |        +-> secondary_categories -> primary_categories
                         |        +-> cost_codes
                         |        +-> hole_sections (optional)
                         |        +-> historical catalogue/quantity fields (nullable)
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

Current AFE lines hold **scope**, not a forecast of daily consumption. A line
contains:

- Primary → Secondary classification and its configured cost code
- Service type and rate basis
- Hole section (a foreign key to `hole_sections`, not free text), or
  `applies_to_all_sections`
- Notes

`applies_to_all_sections` lets a common service be entered once rather than once
per section. `per_section` requires a configured `hole_section_id`.

The historical `quantity`, `unit_id`, `daily_consumption`,
`computed_quantity`, `quantity_override_reason`, and line-level planned duration
columns remain nullable for existing records and imports. They are not requested
by the current AFE Lines UI. Actual consumable quantity and UOM are captured on
Daily Cost, where the saved AFE Cost Estimate rate is applied.

## Rate basis

`afe_lines.rate_basis` supports the historical values
`('daily','per_service','per_section','fixed','per_unit','daily_consumption')`.
The current UI offers `per_unit` for consumables and does not expose
`daily_consumption`; that historical value remains readable so older records do
not lose their audit history.

## AFE Cost Estimate workflow

Only an active **submitted** AFE is available to AFE Cost Estimates. The pricing
screen maintains one estimated rate per current scope line, plus optional vendor
and remarks. For a scope-only line, that rate is its estimated amount; a legacy
line with an explicit quantity remains readable with its historical
quantity-based amount. The saved rate is the source used by Daily Cost.

## Status and revision safety

Only `draft` and `submitted` are implemented. Submitted AFEs and their lines are read-only. Revision fields (`revision_number`, `supersedes_id`) exist, but revision creation deliberately raises `NotImplementedError` until the business confirms version/locking behavior.

## Referential validation

AFE lines must reference active catalogue items, cost codes, quantity units, hole sections, and optional depth units. Inactive/orphaned references are rejected before commit. Depth ranges require a unit and cannot run backwards.
