# Phase 11 API — framework assurance

`GET /api/v1/assurance/status` is authenticated and returns migration/reporting contract versions, six live structural invariant checks, and four explicit acceptance blockers.

`framework_ready` means implemented framework invariants currently have zero detected violations. It does not mean numeric formulas, workflow policy, AFE issuance, financial posting, production roles, or reporting access are approved.
