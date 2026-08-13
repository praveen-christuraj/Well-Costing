# Cost-control persistence framework

Migration `20260813_0008` adds:

- `cost_control_batches` — estimate/version context, optional issued-AFE reference, one explicit cost state, source/mapping metadata, status/counts, timestamps, and actors.
- `cost_control_staged_lines` — normalized row data plus original raw snapshot and correction lineage.
- `cost_control_batch_errors` — row/column error history.
- `cost_control_post_attempts` — immutable posting policy/audit evidence.
- `cost_transactions` — future immutable posted records with required AFE, source batch/line, source-document lineage, and self-referencing reversal/adjustment link.

A discriminator does not merge the states: every transaction has exactly one constrained cost state and never overwrites another state record. Posted records have no update/delete API. Corrections are new records linked through `reverses_transaction_id`.

Staging is permitted without an issued AFE; posting is not. Under the pending policy, transactions remain empty.
