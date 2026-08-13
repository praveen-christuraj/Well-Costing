# Calculation persistence framework

Migration `20260812_0005` adds nullable estimate-version totals and the audited `estimate_calculations` table.

## `estimate_versions` additions

- `base_total numeric(18,4) null`
- `contingency_total numeric(18,4) null`
- `escalation_total numeric(18,4) null`
- `grand_total numeric(18,4) null`

Null is intentional and means no authoritative calculation result exists. Zero must never be used as a substitute for an unconfirmed result.

## `estimate_calculations`

Each calculation attempt records:

- estimate-version foreign key;
- engine and rule-set versions;
- constrained status: `started`, `completed`, `blocked`, or `failed`;
- message;
- immutable-at-completion JSON input and output snapshots;
- created/updated timestamps and actor IDs.

Indexes support version/time history and status queries. Deleting an estimate version cascades to its run records as part of deleting the version aggregate. Published/immutable-history policy remains a later workflow decision.

Under `pending-full-chain`, attempts transition from `started` to `blocked`, persist the input snapshot, leave output null, and keep every line and version financial field null.
