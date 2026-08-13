# Phase 6 completion report — Review & Approval Workflow framework

**Date:** 2026-08-13  
**Delivery mode:** Framework only  
**Integration scope:** Generic state-machine core + estimate versions  
**Authorization mode:** Pending role mappings  
**Policy ID:** `pending-estimate-review`

## Executive result

Phase 6 is complete for the sponsor-selected framework-only scope. The system now has pure state-machine contracts, versioned workflow configuration persistence, hard role-mapping boundaries, estimate-version workflow integration, audited transition attempts, immutable review notes, typed APIs, and a frontend review/trace panel.

No organization-specific state, transition, Reviewer/Approver role, or approval behavior was guessed. No workflow profile is seeded or published. A transition request is audited as `blocked`, returns `workflow_profile_pending`, creates no workflow instance, and leaves estimate and financial state unchanged.

This report does **not** claim that an approval workflow is active.

## Sponsor decisions applied

At the Phase 6 gate, the sponsor selected:

1. **Framework only** rather than candidate workflow defaults.
2. **Generic core + estimate integration** rather than hard-coding a one-off estimate state machine or expanding to requirements.
3. **Pending role mappings** rather than inventing Reviewer/Approver roles or allowing any authenticated user to approve.

## Delivered scope

### Pure workflow domain

- Frozen contracts for states, transitions, profiles, role names, and transition evaluations.
- Deterministic structural evaluation of a supplied published profile.
- Fail-closed behavior for absent/unpublished profiles and missing role mappings.
- Mandatory discovery exception:

  `NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")`

- Existing AST isolation regression covers the new domain package and prevents FastAPI, SQLAlchemy, or Pydantic imports.

### Versioned persistence

- `workflow_profiles` with version, lifecycle, effective dates, source, timestamps, and actors.
- `workflow_states` and `workflow_transition_definitions` with profile-scoped explicit keys.
- `workflow_transition_roles` linked to existing authorization roles.
- `estimate_workflow_instances` binding an estimate version to one profile version and current state.
- `workflow_transition_attempts` retaining completed/blocked/denied/failed requests and context snapshots.
- Append/read-only `estimate_review_comments` with actor/timestamp audit.

No configuration rows or workflow instances are seeded.

### Application and API boundaries

- Profile/status mapping between SQLAlchemy records and the pure domain contract.
- Singular published-profile safeguard; absence or ambiguity fails closed.
- Explicit role intersection and comment-requirement evaluation for future approved profiles.
- Transition auditing before normalized blocked/denied errors.
- No mutation of `EstimateVersion.status` by the generic workflow framework.
- APIs to read profiles/status, request transitions, and create/read review notes.

### Frontend

- Review & Approval panel integrated into the Cost Builder.
- Visible `profile_pending` status and six-item pending-policy register.
- No Approve, Reject, Submit, or other guessed action button.
- Immutable review-note composer and review-note history.
- Transition-attempt history with status, requested action, and timestamp.
- Version changes reload both calculation and workflow context.
- Responsive styling and strict typed service/composable boundaries.

## Safety and acceptance evidence

The following invariant is enforced while `pending-estimate-review` is unresolved:

1. Workflow-profile count is zero.
2. Available actions are empty.
3. A transition request returns `workflow_profile_pending`.
4. The blocked attempt records action, context, actor, and timestamps.
5. No `estimate_workflow_instances` row is created.
6. Existing estimate status is unchanged.
7. Financial values remain unchanged/null.
8. Review notes can be added but have no transition side effect.

PostgreSQL E2E inspection after the browser journey confirmed:

```text
workflow profiles: 0
latest attempt: blocked | submit_for_review | context present | actors present
workflow instances: 0
review comments: 1 | actor present
estimate status: pending_calculation | grand total null
populated estimate-item financial rows: 0
```

## Validation results

| Validation | Result |
|---|---|
| PostgreSQL runtime | 16.14 |
| Alembic `upgrade head → downgrade base → upgrade head` | Passed through `20260813_0006` |
| PostgreSQL configured-database smoke test | 1 passed |
| Backend tests | 44 passed |
| Backend coverage | 77.51% (minimum 75%) |
| Ruff | Passed |
| Strict Pyright | 0 errors, 0 warnings |
| Frontend strict typecheck | Passed |
| ESLint | Passed |
| Vitest | 9 passed across 7 files |
| Nuxt production build | Passed |
| npm audit | 0 vulnerabilities |
| Playwright full-stack regression | 3 passed, including Phase 5 and Phase 6 blocked flows plus review note |

One pre-existing Starlette `TestClient`/HTTPX deprecation warning remains. The production build reports the existing Vite large-chunk advisory, not a build failure.

Local validation used Python 3.13.14 and Node 20.20.2 because Python 3.12 and Node 22 were unavailable in this workspace. Project and CI targets remain Python 3.12 and Node 22.

## Files added

### Backend

- `backend/alembic/versions/20260813_0006_add_workflow_review_framework.py`
- `backend/app/api/v1/routes/workflow.py`
- `backend/app/domain/workflow/__init__.py`
- `backend/app/domain/workflow/state_machine.py`
- `backend/app/domain/workflow/types.py`
- `backend/app/models/workflow.py`
- `backend/app/schemas/workflow.py`
- `backend/app/services/workflow.py`
- `backend/tests/integration/test_workflow_framework.py`
- `backend/tests/unit/test_workflow_state_machine.py`

### Frontend

- `frontend/components/workflow/EstimateWorkflowPanel.vue`
- `frontend/composables/useWorkflow.ts`
- `frontend/services/workflow.ts`
- `frontend/types/workflow.ts`
- `frontend/tests/unit/components/EstimateWorkflowPanel.spec.ts`

### Documentation

- `docs/api/phase-6.md`
- `docs/architecture/phase-6-decisions.md`
- `docs/database/workflow.md`
- `docs/rules/phase-6-pending-estimate-review.md`
- `docs/phase-reports/phase-06-review-approval-workflow-framework.md`

## Files changed

- `backend/app/api/v1/router.py`
- `backend/app/core/exceptions.py`
- `backend/app/models/__init__.py`
- `frontend/assets/css/main.css`
- `frontend/pages/cost-builder/[id].vue`
- `frontend/pages/cost-builder/index.vue`
- `frontend/tests/e2e/requirement-intake.spec.ts`
- `README.md`
- `CHANGELOG.md`

## Deferrals and acceptance blockers

The following authoritative inputs are required before publishing an active estimate profile:

- approved state diagram and display labels;
- transition matrix with exact actions and prerequisites;
- role/permission matrix;
- delegation and separation-of-duties policy;
- calculation/validation checks required before review or approval;
- rejection, revision, resubmission, and mandatory-comment behavior;
- profile effective-date, retirement, and in-flight migration policy;
- business owner and approval/source reference;
- trusted allowed, denied, rejection, revision, and resubmission scenarios.

Accordingly, the following remain deferred:

- active Submit/Approve/Reject/Reopen behavior;
- seeded Reviewer or Approver roles;
- workflow profile administration and publication APIs/UI;
- approval thresholds or amount-based routing;
- notifications, escalation, delegation, and substitute approvers;
- immutable approved AFE snapshot creation, which belongs to Phase 7 and also requires business confirmation.

## Deviations

- No candidate industry-reference workflow state was activated.
- No authenticated-user approval shortcut was introduced.
- No profile management endpoint was exposed before administration permissions are defined.
- No estimate status or financial value was changed by the workflow framework.
- The framework-only outcome is the explicitly selected Phase 6 mode, not a scope failure.

## Approval gate

Phase 6 framework delivery is ready for sponsor review. Do not begin Phase 7 or activate any approval transition until explicit approval is given. Phase 7 must treat an approved AFE as an immutable snapshot and must keep revision/supplement behavior pending until authoritative policy is supplied.
