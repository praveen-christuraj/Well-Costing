# Immutable baseline AFE persistence

Migration `20260813_0007` adds three tables.

## `afe_snapshots`

One baseline per estimate version, with unique AFE number, source estimate and completed calculation references, issue date, copied estimate/project/well/currency identity, engine/rule-set provenance, non-null totals, full source snapshot, timestamps, and actors.

The source estimate-version and calculation foreign keys use `RESTRICT`, preventing source removal after an AFE exists. No update/delete API exists.

## `afe_snapshot_lines`

Immutable copied line identity/dimensions, quantity/unit/rate references, and non-null base/contingency/escalation/total values. Lines retain source estimate-item IDs but do not depend on mutable catalogue descriptions after issuance.

## `afe_snapshot_attempts`

Audits explicit completed, blocked, denied, or failed baseline requests. Eligibility snapshots preserve workflow/calculation status and completeness evidence. Blocked attempts never create headers or lines.

Phase 7 seeds no AFE record and no numbering sequence. Revision/supplement tables are intentionally absent under the approved baseline-only scope.
