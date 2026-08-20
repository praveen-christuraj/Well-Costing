"""Unit tests for the pure well rate-governance rules."""

from decimal import Decimal

import pytest
from app.domain.well_costing import (
    RateBookLockedError,
    RateChangeReasonRequiredError,
    UnplannedTransitionError,
    assert_rate_change_allowed,
    assert_reason_supplied,
    changed_financial_fields,
    is_locked,
    next_revision_number,
    rate_delta,
    summarise_exposure,
    unplanned_transition,
)


def test_draft_rates_accept_any_change() -> None:
    assert is_locked("draft") is False
    assert_rate_change_allowed("draft", {"operating_rate": Decimal("100")})


def test_locked_rate_refuses_a_reprice_and_names_the_fields() -> None:
    with pytest.raises(RateBookLockedError) as exc:
        assert_rate_change_allowed("locked", {"operating_rate": Decimal("1"), "notes": "x"})

    assert "operating_rate" in str(exc.value)
    assert "out-of-AFE" in str(exc.value)


def test_locked_rate_still_accepts_descriptive_edits() -> None:
    """Notes and references carry no money, so a locked row keeps them editable."""

    assert_rate_change_allowed("locked", {"notes": "crew changed", "contract_reference": "SO-9"})


def test_repricing_requires_a_reason() -> None:
    with pytest.raises(RateChangeReasonRequiredError):
        assert_reason_supplied(None, {"unit_rate": Decimal("5")})
    with pytest.raises(RateChangeReasonRequiredError):
        assert_reason_supplied("   ", {"unit_rate": Decimal("5")})

    assert_reason_supplied("Contract amendment 3", {"unit_rate": Decimal("5")})
    assert_reason_supplied(None, {"notes": "typo"})


def test_changed_financial_fields_ignores_descriptive_fields() -> None:
    changed = changed_financial_fields(
        {"operating_rate": 1, "unit_rate": 2, "notes": "x", "is_active": True}
    )

    assert changed == {"operating_rate", "unit_rate"}


def test_revision_numbers_start_at_one_and_increment() -> None:
    assert next_revision_number(None) == 1
    assert next_revision_number(0) == 1
    assert next_revision_number(3) == 4


def test_rate_delta_treats_missing_values_as_zero() -> None:
    assert rate_delta(None, Decimal("10")) == Decimal("10")
    assert rate_delta(Decimal("10"), None) == Decimal("-10")
    assert rate_delta(Decimal("10"), Decimal("12.5")) == Decimal("2.5")


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("draft", "submitted"),
        ("draft", "cancelled"),
        ("submitted", "approved"),
        ("submitted", "rejected"),
        ("rejected", "draft"),
    ],
)
def test_permitted_unplanned_transitions(current: str, target: str) -> None:
    assert unplanned_transition(current, target) == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("draft", "approved"),
        ("approved", "draft"),
        ("approved", "cancelled"),
        ("cancelled", "submitted"),
        ("submitted", "posted"),
    ],
)
def test_refused_unplanned_transitions(current: str, target: str) -> None:
    with pytest.raises(UnplannedTransitionError):
        unplanned_transition(current, target)


def test_exposure_reports_approved_spend_as_the_variance() -> None:
    summary = summarise_exposure(
        afe_total=Decimal("1000000"),
        approved_unplanned_total=Decimal("125000"),
        pending_unplanned_total=Decimal("40000"),
    )

    assert summary.committed_total == Decimal("1125000")
    assert summary.variance_amount == Decimal("125000")
    assert summary.variance_percent == Decimal("12.5")
    assert summary.pending_unplanned_total == Decimal("40000")


def test_exposure_without_an_afe_reports_no_percentage() -> None:
    summary = summarise_exposure(
        afe_total=None, approved_unplanned_total=Decimal("500"), pending_unplanned_total=None
    )

    assert summary.afe_total == Decimal("0")
    assert summary.variance_percent is None
    assert summary.committed_total == Decimal("500")
