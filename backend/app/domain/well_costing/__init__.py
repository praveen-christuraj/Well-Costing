"""Pure rate-governance rules for the well rate book and out-of-AFE register.

No framework imports: these rules are exercised directly by unit tests and are
reused by the application services, which translate the exceptions raised here
into API errors.
"""

from app.domain.well_costing.rate_lock import (
    ExposureSummary,
    RateBookLockedError,
    RateChangeReasonRequiredError,
    UnplannedTransitionError,
    WellCostingRuleError,
    assert_rate_change_allowed,
    assert_reason_supplied,
    changed_financial_fields,
    is_locked,
    next_revision_number,
    rate_delta,
    summarise_exposure,
    unplanned_transition,
)

__all__ = [
    "ExposureSummary",
    "RateBookLockedError",
    "RateChangeReasonRequiredError",
    "UnplannedTransitionError",
    "WellCostingRuleError",
    "assert_rate_change_allowed",
    "assert_reason_supplied",
    "changed_financial_fields",
    "is_locked",
    "next_revision_number",
    "rate_delta",
    "summarise_exposure",
    "unplanned_transition",
]
