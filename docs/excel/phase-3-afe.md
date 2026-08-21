# AFE-line Excel profile

Profile: `afe-lines-default`, version `2.0`.

Required columns:

- `line_number`
- `catalog_item_code`
- `item_type`
- `cost_code`
- `quantity`
- `unit_code`

Optional columns:

- `hole_section_code` (aliases: `hole_section`, `section_code`, `section`, `section_name`)
- `rate_basis` (aliases: `rate_type`, `basis`, `charge_basis`)
- `daily_consumption` (aliases: `consumption_per_day`, `usage_per_day`, `qty_per_day`)
- `quantity_override_reason` (aliases: `override_reason`, `quantity_reason`)
- `planned_duration_days`
- `planned_depth_from`
- `planned_depth_to`
- `depth_unit_code`
- `notes`
- `is_active`

Version 2.0 replaced the free-text `section_name` with `hole_section_code`,
which is resolved against the configured hole sections: a section that is not
configured is a row error, not a new section. The rate-basis and
daily-consumption columns carry the same rules the API applies — a basis the
item type does not allow is rejected, and a quantity that contradicts
`daily_consumption × planned_duration_days` needs a reason.

Preview resolves codes to active master-data records and rejects missing, inactive, duplicate, or ambiguous references. A batch cannot commit unless every row is valid. Import/export retains the same profile headers.

This version is structurally representative. Actual source-workbook aliases remain pending until the original workbooks are supplied and certified.
