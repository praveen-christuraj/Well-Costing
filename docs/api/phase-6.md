# Phase 6 API — estimate review workflow framework

Phase 6 exposes a generic state-machine boundary integrated with estimate versions. No organization-specific approval policy is active. All routes require authentication and use the centralized error envelope.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/workflow/profiles` | Read estimate workflow profiles visible to the framework. Returns an empty list while no profile is approved. |
| `GET` | `/api/v1/estimates/{estimate_id}/workflow?version_id={uuid}` | Read profile status, current state, available configured actions, transition-attempt history, review notes, and pending requirements. |
| `POST` | `/api/v1/estimates/{estimate_id}/workflow/transitions` | Request a configured transition. Requests are audited and blocked while the profile/role policy is pending. |
| `GET` | `/api/v1/estimates/{estimate_id}/review-comments?version_id={uuid}` | Read immutable review notes for an estimate version. |
| `POST` | `/api/v1/estimates/{estimate_id}/review-comments` | Add an authenticated, actor-attributed review note without changing workflow state. |

Omitting `version_id` targets the estimate's current version.

## Pending transition response

With no published authoritative profile, transition requests return HTTP 422 with code `workflow_profile_pending`. Error details contain:

- transition-attempt ID;
- policy version `pending-estimate-review`;
- six pending policy groups.

The blocked attempt is committed before the error is returned. It records the estimate/version identity, requested action, actor role names, timestamps, and actor IDs. It does not create a workflow instance or mutate estimate/calculation state.

## Workflow status

`workflow_status` is one of:

- `profile_pending` — no singular published estimate profile is available;
- `not_started` — a valid profile exists but the version has no persisted workflow instance;
- `active` — the version has an instance and current configured state.

Under the Phase 6 framework-only mode, the expected status is `profile_pending`, profile/current state are null, and available actions are empty.

## Review comments

Review notes are collaborative audit records, not approvals. The API supports create/read only; no update or destructive delete route exists. Adding a note cannot move state, approve an estimate, or alter financial values.
