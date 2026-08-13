# Phase 3 architecture decisions

## ADR-010 — Requirement intake is not well design

The module stores planning-team inputs and references them to the Cost Library. It never derives engineering values. The UI displays this boundary explicitly.

## ADR-011 — Minimal status model

Only `draft` and `submitted` are implemented because the specification permits this minimal state set. `locked`, approval chains, and transitions beyond submission require business confirmation.

## ADR-012 — Submitted records are protected

A submitted requirement is read-only to prevent silent alteration of an accepted input. The revision API remains an explicit `NotImplementedError` until immutable/versioned behavior is confirmed.

## ADR-013 — Depth context carries a unit

The discovery summary identifies planned depth and sections. Optional from/to values therefore require an explicit unit; the application does not infer metres or feet.
