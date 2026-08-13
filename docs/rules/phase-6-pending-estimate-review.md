# Pending estimate-review workflow policy

Status: **not authoritative**  
Policy ID: `pending-estimate-review`

The following require explicit business approval before an estimate workflow profile can be published:

1. Estimate review states and display labels.
2. Permitted transitions and transition prerequisites.
3. Reviewer/approver role mappings, delegation, and separation of duties.
4. Calculation and validation checks required before each transition.
5. Rejection, revision, resubmission, and mandatory-comment behavior.
6. Profile publication, effective-date, retirement, and in-flight-instance migration policy.

Required acceptance inputs:

- approved state diagram;
- transition matrix with from/to/action;
- role/permission matrix and delegation rules;
- preconditions and failure behavior per transition;
- comment/reason requirements;
- treatment of existing estimate versions when a profile changes;
- named business owner and source/approval reference;
- trusted normal, denied, rejection, revision, and resubmission scenarios.

Until these inputs are supplied:

- no profile, state, transition, or role mapping is seeded;
- the UI displays no Approve/Reject/Submit action;
- transition attempts return `workflow_profile_pending`;
- no workflow instance or approval state is created;
- estimate and financial state remain unchanged.
