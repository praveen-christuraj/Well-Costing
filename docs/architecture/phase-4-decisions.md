# Phase 4 decisions

## ADR-014 — Generate an unpriced skeleton

A submitted requirement generates one estimate item per active requirement item. Because best-rate selection is unconfirmed, vendor/rate fields start null rather than using a guessed rule.

## ADR-015 — Manual assignments are structurally constrained

A manually selected rate must belong to the same catalogue item; a separately selected vendor must match the rate vendor. This is referential validation, not automatic commercial selection.

## ADR-016 — Assumptions are data only

Contingency and escalation percentages can be stored at estimate/category scope, but Phase 4 never applies them. All cost columns remain null.

## ADR-017 — Versions are copies, not mutable aliases

Duplicating a version creates new line and assumption records. Later edits cannot corrupt the prior version.
