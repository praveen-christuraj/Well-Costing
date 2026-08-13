# Phase 7 architecture decisions

Sponsor selections: **framework only**, **baseline snapshot only**, **explicit request after approval**.

## Immutable copy, not a live estimate view

A future issued AFE copies header, line, totals, currency, calculation provenance, and source snapshot. It does not calculate from or dynamically render mutable estimate rows. Source foreign keys are restrictive and no mutation endpoint is exposed.

## Explicit command

AFE creation is a deliberate server-side command. Estimate approval does not automatically issue an AFE. This avoids an unconfirmed side effect and provides a distinct audit attempt.

## Fail-closed eligibility

The pure AFE boundary raises the mandated discovery `NotImplementedError`. The service records workflow/calculation eligibility and maps the result to `afe_policy_pending`. No number, issue date, or snapshot is guessed.

## Baseline only

A unique estimate-version constraint permits one original baseline. Revisions, supplements, parent/child AFE families, voids, and corrections remain deferred rather than partially modeled as active policy.

## Financial integrity

Issued header and line amounts are non-null and require completed calculation provenance. Framework attempts can exist with incomplete estimates, but snapshots cannot. All AFE tables have timestamp and actor fields from creation.
