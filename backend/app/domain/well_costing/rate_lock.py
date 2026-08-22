"""Rate-lock, revision, and out-of-AFE rules expressed without any framework.

The well rate book exists so that a rate revised centrally while a rig is
drilling cannot move the cost basis of that well. Two rules carry that promise:

1. a rate row is copied into the well and never re-read from master data, and
2. once the AFE baseline is issued the row is locked and its financial fields
   are immutable — a deviation becomes an out-of-AFE entry instead.
"""

from dataclasses import dataclass
from decimal import Decimal

DRAFT = "draft"
LOCKED = "locked"
RATE_BOOK_STATUSES: frozenset[str] = frozenset({DRAFT, LOCKED})

ORIGIN_WELL_PLANNING = "well_planning"
ORIGIN_UNPLANNED = "unplanned"
RATE_BOOK_ORIGINS: frozenset[str] = frozenset({ORIGIN_WELL_PLANNING, ORIGIN_UNPLANNED})

UNPLANNED_DRAFT = "draft"
UNPLANNED_SUBMITTED = "submitted"
UNPLANNED_APPROVED = "approved"
UNPLANNED_REJECTED = "rejected"
UNPLANNED_CANCELLED = "cancelled"
UNPLANNED_STATUSES: frozenset[str] = frozenset(
    {
        UNPLANNED_DRAFT,
        UNPLANNED_SUBMITTED,
        UNPLANNED_APPROVED,
        UNPLANNED_REJECTED,
        UNPLANNED_CANCELLED,
    }
)

#: Allowed out-of-AFE transitions. Approved entries are terminal because an
#: approved variance has already been reported against the AFE.
UNPLANNED_TRANSITIONS: dict[str, frozenset[str]] = {
    UNPLANNED_DRAFT: frozenset({UNPLANNED_SUBMITTED, UNPLANNED_CANCELLED}),
    UNPLANNED_SUBMITTED: frozenset({UNPLANNED_APPROVED, UNPLANNED_REJECTED, UNPLANNED_CANCELLED}),
    UNPLANNED_REJECTED: frozenset({UNPLANNED_DRAFT, UNPLANNED_CANCELLED}),
    UNPLANNED_APPROVED: frozenset(),
    UNPLANNED_CANCELLED: frozenset(),
}

#: Fields whose value changes the money a well spends. Locked rows refuse them.
FINANCIAL_FIELDS: frozenset[str] = frozenset(
    {
        "currency_id",
        "unit_id",
        "vendor_id",
        "hole_section_id",
        "rate_basis",
        "operating_rate",
        "standby_rate",
        "mobilisation_rate",
        "demobilisation_rate",
        "personnel_operating_rate",
        "personnel_standby_rate",
        "other_rate",
        "unit_rate",
        "quantity",
    }
)


class WellCostingRuleError(Exception):
    """Base class for well rate-governance rule violations."""

    code = "well_costing_rule_violation"


class RateBookLockedError(WellCostingRuleError):
    """A locked well rate may not be repriced."""

    code = "well_rate_book_locked"


class RateChangeReasonRequiredError(WellCostingRuleError):
    """Repricing an existing well rate requires a recorded reason."""

    code = "rate_change_reason_required"


class UnplannedTransitionError(WellCostingRuleError):
    """The requested out-of-AFE status change is not allowed."""

    code = "unplanned_transition_not_allowed"


def is_locked(status: str) -> bool:
    """Return whether a rate-book row is frozen for the rest of the well."""

    return status == LOCKED


def changed_financial_fields(values: dict[str, object]) -> set[str]:
    """Return the supplied fields that would change what the well pays."""

    return {field for field in values if field in FINANCIAL_FIELDS}


def assert_rate_change_allowed(status: str, values: dict[str, object]) -> None:
    """Refuse financial edits to a locked row; descriptive edits stay allowed.

    Raises:
        RateBookLockedError: when a locked row is repriced.
    """

    if not is_locked(status):
        return
    changed = changed_financial_fields(values)
    if not changed:
        return
    raise RateBookLockedError(
        "This rate is locked to the approved AFE and cannot be changed "
        f"({', '.join(sorted(changed))}). Raise an out-of-AFE entry for the "
        "well instead."
    )


def assert_reason_supplied(reason: str | None, values: dict[str, object]) -> None:
    """Require a reason whenever an existing rate is repriced.

    Raises:
        RateChangeReasonRequiredError: when a rate moves without a reason.
    """

    if not changed_financial_fields(values):
        return
    if reason is not None and reason.strip():
        return
    raise RateChangeReasonRequiredError(
        "A change reason is required when an existing well rate is revised."
    )


def next_revision_number(current: int | None) -> int:
    """Return the revision number that follows ``current`` (1-based)."""

    return (current or 0) + 1


def rate_delta(previous: Decimal | None, new: Decimal | None) -> Decimal:
    """Return ``new - previous``, treating a missing value as zero."""

    return (new or Decimal("0")) - (previous or Decimal("0"))


def unplanned_transition(current: str, target: str) -> str:
    """Validate an out-of-AFE status change and return the target status.

    Raises:
        UnplannedTransitionError: when the transition is not permitted.
    """

    if target not in UNPLANNED_STATUSES:
        raise UnplannedTransitionError(f"'{target}' is not an out-of-AFE status")
    allowed = UNPLANNED_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        permitted = ", ".join(sorted(allowed)) or "no further status"
        raise UnplannedTransitionError(
            f"An out-of-AFE entry in '{current}' can only move to {permitted}."
        )
    return target


@dataclass(frozen=True)
class ExposureSummary:
    """Approved-AFE versus out-of-AFE position for one well."""

    afe_total: Decimal
    approved_unplanned_total: Decimal
    pending_unplanned_total: Decimal
    committed_total: Decimal
    variance_amount: Decimal
    variance_percent: Decimal | None


def summarise_exposure(
    *,
    afe_total: Decimal | None,
    approved_unplanned_total: Decimal | None,
    pending_unplanned_total: Decimal | None,
) -> ExposureSummary:
    """Combine the immutable AFE baseline with out-of-AFE charges.

    ``variance_amount`` is the approved out-of-AFE spend, which is exactly the
    amount by which the well is expected to exceed its approved AFE. The
    percentage is ``None`` when there is no AFE to compare against.
    """

    afe = afe_total or Decimal("0")
    approved = approved_unplanned_total or Decimal("0")
    pending = pending_unplanned_total or Decimal("0")
    committed = afe + approved
    percent = (approved / afe * Decimal("100")) if afe > 0 else None
    return ExposureSummary(
        afe_total=afe,
        approved_unplanned_total=approved,
        pending_unplanned_total=pending,
        committed_total=committed,
        variance_amount=approved,
        variance_percent=percent,
    )
