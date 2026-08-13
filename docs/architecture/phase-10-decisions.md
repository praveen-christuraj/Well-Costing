# Phase 10 decisions

Sponsor selected framework-only fact + dimensions + policy metadata and no active database grants.

The `reporting` schema is the only future direct-database contract. Transactional table names remain private implementation details. Breaking changes require new versioned views (for example `v2_*`), coexistence/migration documentation, and consumer approval.

No aggregate financial view is published while metric policy is pending. The grant file is a commented template only; production identity, row-level security, network, refresh, and credential policy remain external approvals.
