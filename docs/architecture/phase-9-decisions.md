# Phase 9 decisions

Sponsor selected framework-only dashboard + API + Excel and the full shared-dimension set.

Source drill-through is distinct from financial aggregation. Stored source amounts can be displayed, but AFE totals, cost-state overlap, variance, EAC, reporting currency, and rounding remain a pure-domain pending boundary. Null means unresolved; zero is never substituted.

Excel exports are deterministic and actor-audited. SQL reporting views and Power BI contracts are deferred to Phase 10.
