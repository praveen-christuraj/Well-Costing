# Workflow and review persistence framework

Migration `20260813_0006` adds versioned workflow configuration and estimate-review audit tables.

## Configuration tables

### `workflow_profiles`

Stores profile identity, record type, version, lifecycle (`draft`, `validated`, `published`, `retired`), description, source reference, effective dates, timestamps, and actors.

### `workflow_states`

Stores profile-scoped state keys, labels, order, and initial/terminal flags. No organization-specific states are seeded.

### `workflow_transition_definitions`

Stores profile-scoped action keys, from/to state keys, labels, order, and comment requirement. No transitions are seeded.

### `workflow_transition_roles`

Maps configured transitions to existing authorization roles. No Reviewer, Approver, or other role mapping is guessed or seeded.

## Estimate integration tables

### `estimate_workflow_instances`

Binds one estimate version to one immutable profile version and its current state. No instance is created until a valid published profile authorizes a transition.

### `workflow_transition_attempts`

Audits completed, blocked, denied, and failed transition requests. It retains version/profile/instance references, requested action, before/after state keys, context snapshot, message, timestamps, and actors.

### `estimate_review_comments`

Stores actor-attributed review notes against an estimate version. The current API is append/read only.

## Pending-policy invariant

While no approved profile and role mappings exist:

1. profile count is zero;
2. transition requests persist as `blocked`;
3. no workflow instance is created;
4. estimate version status is unchanged;
5. financial fields remain unchanged/null;
6. review notes may be appended but cannot authorize or transition anything.

Configuration and history records use explicit relational tables rather than executable expressions or unrestricted scripts.
