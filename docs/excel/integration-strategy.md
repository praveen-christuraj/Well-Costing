# Excel integration strategy

## Goal

Preserve Excel's high-throughput editing experience while moving validation, audit, persistence, and calculations into the application.

## Implementation status

Phase 2 implements `reader.py`, `mapper.py`, `validator.py`, `importer.py`, `exporter.py`, and `templates.py` for Cost Library entities. See [`phase-2-import.md`](phase-2-import.md). Requirement and later-phase workbook profiles remain deferred.

## Phase 2 pipeline

```text
Upload
 -> safe file/type/size checks
 -> read selected workbook/sheet with Pandas/OpenPyXL
 -> apply a named and versioned mapping profile
 -> normalize only approved representations
 -> validate required/type/reference/duplicate rules
 -> preview rows and cell-level errors
 -> commit the validated batch in one transaction
 -> retain source, mapping, actor, counts, and errors
```

## Principles

1. Preview never writes business records.
2. Invalid financial batches do not partially commit unless a later confirmed requirement explicitly defines partial behavior.
3. Every error identifies row, column, code, and message.
4. Export uses the same versioned column template used for import.
5. Formula cells, cached values, macros, hidden sheets, named ranges, and external links remain discovery evidence; they are not trusted executable content in the web application.
6. Uploaded filenames are display metadata, not trusted storage paths.
7. Mapping ambiguity requires user confirmation rather than guessing.
8. Import batches are auditable and reproducible.

## Template/version strategy

Templates and mapping profiles will have stable names plus published versions. Historical batches keep the exact profile/template version used. Changing a header or mapping creates a new version and never reinterprets a committed batch.

## Security considerations

Future implementation must address workbook size limits, compressed-file expansion, path traversal, formula injection on export, macro preservation policy, external links, malformed XML, and temporary-file cleanup. Macros will not execute on the server.
