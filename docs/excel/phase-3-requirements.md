# Requirement-item Excel profile

Profile: `requirement-items-default`, version `1.0`.

Required columns:

- `line_number`
- `catalog_item_code`
- `item_type`
- `cost_code`
- `quantity`
- `unit_code`

Optional columns:

- `section_name`
- `planned_duration_days`
- `planned_depth_from`
- `planned_depth_to`
- `depth_unit_code`
- `notes`
- `is_active`

Preview resolves codes to active master-data records and rejects missing, inactive, duplicate, or ambiguous references. A batch cannot commit unless every row is valid. Import/export retains the same profile headers.

This version is structurally representative. Actual source-workbook aliases remain pending until the original workbooks are supplied and certified.
