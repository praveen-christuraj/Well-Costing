# Phase 6 architecture decisions

## Selected delivery mode

The sponsor selected:

- **framework only**;
- **generic state-machine core with estimate-version integration**;
- **pending role mappings**.

No candidate industry state labels or generic Reviewer/Approver roles are treated as approved policy.

## Pure structural core

`app/domain/workflow` contains frozen profile/state/transition/evaluation contracts and deterministic structural evaluation. It has no FastAPI, SQLAlchemy, or Pydantic imports.

The evaluator can process a synthetic published profile for framework tests. At runtime, a missing/unpublished profile or a transition without role mappings raises:

`NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")`

The application layer audits this as typed API code `workflow_profile_pending`.

## Configuration, not executable rules

Profiles use explicit versioned state, transition, and role-mapping rows. The framework stores no Python, SQL, JavaScript, or unrestricted formula text. Publishing/administration APIs are intentionally absent until configuration permissions and policy approval are defined.

## Separate workflow state

Workflow state is not added to or inferred from the existing estimate calculation status. `EstimateWorkflowInstance` is separate from `EstimateVersion.status`, preventing an unapproved review model from rewriting existing lifecycle semantics.

## Hard authorization boundary

A transition requires a published profile and an explicit mapping between that transition and an active role held by the actor. Empty role mappings fail closed. No transition is permitted merely because a user is authenticated.

## Audit before error

Blocked or denied attempts are committed with actor, timestamp, requested action, context snapshot, and profile/version references before the normalized error is returned. A blocked request creates no workflow instance and changes no estimate state.

## Review notes are not approvals

Authenticated users may append review notes to support collaboration and traceability. Notes have no transition side effect, cannot be edited/deleted through the API, and are visibly separated from transition history.
