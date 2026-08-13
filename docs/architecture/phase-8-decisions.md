# Phase 8 architecture decisions

Sponsor choices: **framework only**, **all five states**, **bulk grid + Excel staging**, and **reversal/adjustment lineage rather than destructive edits**.

## Separate states

Field estimates, commitments, accruals, booked actuals, and forecasts are explicit constrained values on separate immutable records. Importing an actual cannot overwrite an AFE, commitment, accrual, or forecast.

## Stage before post

Manual/paste and Excel inputs create audited batches, normalized valid rows, and row errors. Validation and preview do not post financial records. Posting is a separate server command.

## Fail-closed domain boundary

The pure `post_cost_batch` boundary raises the mandated discovery `NotImplementedError`. The application commits a blocked attempt and returns `cost_state_policy_pending`.

## Reversal lineage

Posted corrections are append-only records. A reversal must reference its original transaction; original rows cannot carry a reversal reference. Amount/date/period authorization remains pending.

## No formulas in UI/routes

Vue performs grid conveniences only. Recognition, allocation, FX, matching, reconciliation, EAC/forecast, and reversal rules remain server-domain responsibilities.
