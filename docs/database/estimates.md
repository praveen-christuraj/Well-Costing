# Phase 4 estimate-build model

`cost_estimates` is the logical estimate header linked to one submitted requirement and currency. `estimate_versions` preserve independent builds. Each version owns `estimate_items` and optional header/category `estimate_assumptions`.

Estimate items copy requirement item, catalogue item, cost code, quantity and unit references. Vendor and rate remain nullable until manually assigned. Cost fields exist but remain null until Phase 5.

Approved automatic rate-selection precedence is unavailable. Generation therefore creates a complete line skeleton without choosing a rate; `resolve_default_rate()` raises the mandated `NotImplementedError`.

Version duplication copies lines, manual vendor/rate choices, quantities and assumptions into a new version without altering the source version.
