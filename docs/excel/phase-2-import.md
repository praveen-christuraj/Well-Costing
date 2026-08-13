# Phase 2 Excel import and export

## Supported files

- `.xlsx`
- `.xlsm` (macros are never executed)
- `.xls` through `xlrd`
- Maximum upload: 15 MB

## Pipeline

```text
Upload -> Read -> Map -> Resolve references -> Validate -> Stage preview
       -> user confirmation -> one-transaction commit -> import history
```

`ExcelImportPipeline` orchestrates reader, mapper, and validator. `ExcelImportService` owns persistence and transaction behavior.

## Mapping profiles

Each entity has a named profile at version `1.0`. Header matching is case-insensitive and normalizes spaces, dashes, and slashes. Approved aliases support common labels such as `UOM`, `vendor`, `rate`, and `effective date`. The preview response shows detected columns, applied source-to-target mapping, profile, and version.

The API accepts explicit `mapping_json` overrides for ambiguous source headers. A mapping target must still be part of the entity profile. Actual workbook-specific mappings remain pending because the source files referenced by Phase 0 were not supplied in this workspace.

## Validation

- Required headers and required values
- Pydantic type/length/date/decimal checks
- Boolean normalization
- Duplicate codes within a workbook
- Duplicate codes already in the database
- Existing category, cost code, unit, item, vendor, and currency references
- Ambiguous rate item codes require `item_type`
- No partial commit of invalid batches

## Templates and exports

`GET /api/v1/import/{entity}/template` returns a blank workbook with profile headers, styling, frozen header, filter, and active-status validation.

`GET /api/v1/export/{entity}` writes the same profile headers. API integration tests verify export, deletion in an isolated fixture, preview, commit, and equivalent re-imported data.

## Security

- Paths use sanitized display filenames.
- File size and extension are checked.
- Workbook macros do not execute.
- Uploaded formulas are treated as cell content, not executable application rules.
- Source bytes are hashed but are not stored in Phase 2.
- Future malware scanning and enterprise retention policy remain deployment concerns.
