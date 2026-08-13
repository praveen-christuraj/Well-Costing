# Pending baseline AFE policy

Policy ID: `pending-baseline-afe`  
Status: **not authoritative**

Required approval inputs:

1. Eligible approved estimate workflow state and AFE gate.
2. Required completed calculation/rule-set status.
3. AFE numbering, ownership, and duplicate-reference policy.
4. Authoritative header, line, assumption, and attachment snapshot contents.
5. Issue date, authorization actor, status, and accounting handoff semantics.
6. Void, cancellation, correction, and duplicate-attempt treatment.

Also required are trusted eligible, ineligible, duplicate, incomplete-calculation, and unauthorized scenarios with expected audit outcomes.

Until supplied, explicit requests return `afe_policy_pending`; zero AFE snapshots/lines are created. Revisions and supplements are outside the selected Phase 7 baseline-only framework.
