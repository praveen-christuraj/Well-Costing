# Phase 7 API — immutable baseline AFE framework

Phase 7 adds an explicit baseline-snapshot command and read boundaries without activating AFE issuance policy.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/estimates/{estimate_id}/afe?version_id={uuid}` | Read baseline status, snapshot if issued, attempt history, and pending policy. |
| `POST` | `/api/v1/estimates/{estimate_id}/afe/snapshots` | Explicitly request baseline creation. The request is audited and blocked while policy is pending. |
| `GET` | `/api/v1/afes/{snapshot_id}` | Read a future immutable baseline snapshot and lines. |

Under policy `pending-baseline-afe`, POST returns HTTP 422 with code `afe_policy_pending`. Details include the attempt ID, policy version, and six pending requirement groups.

The attempt is committed before the error response and captures calculation/workflow eligibility, completeness flags, estimate/version identity, actors, and timestamps. No AFE header or line is created.

`afe_status` is `policy_pending` or `issued`. Current framework-only behavior is `policy_pending` with a null snapshot.
