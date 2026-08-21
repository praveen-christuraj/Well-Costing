"""Rate-basis classification and daily-consumption quantity rules."""

from decimal import Decimal

import pytest
from app.domain.afe.rate_basis import (
    RateBasisError,
    allowed_rate_bases,
    default_rate_basis,
    normalize_rate_basis,
    requires_hole_section,
    resolve_planned_quantity,
    validate_rate_basis,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Daily Rate", "daily"),
        ("per-day", "daily"),
        ("PER_SECTION_RATE", "per_section"),
        ("lump sum", "fixed"),
        ("daily usage", "daily_consumption"),
        ("per_unit", "per_unit"),
    ],
)
def test_spelling_variants_fold_onto_one_basis(raw: str, expected: str) -> None:
    assert normalize_rate_basis(raw) == expected


def test_services_and_consumables_offer_different_bases() -> None:
    assert allowed_rate_bases("service") == ("daily", "per_service", "per_section", "fixed")
    assert allowed_rate_bases("mud_chemical") == ("per_unit", "daily_consumption")
    assert allowed_rate_bases("cement_additive") == ("per_unit", "daily_consumption")


def test_a_service_cannot_be_charged_on_daily_consumption() -> None:
    with pytest.raises(RateBasisError, match="not valid for service"):
        validate_rate_basis("service", "daily_consumption")


def test_a_chemical_cannot_be_charged_per_section() -> None:
    with pytest.raises(RateBasisError, match="not valid for mud_chemical"):
        validate_rate_basis("mud_chemical", "per_section")


def test_line_default_comes_from_the_catalogue_item() -> None:
    assert default_rate_basis("service", "per_section") == "per_section"
    assert default_rate_basis("mud_chemical", "daily_consumption") == "daily_consumption"


def test_line_default_falls_back_when_the_catalogue_basis_does_not_fit() -> None:
    assert default_rate_basis("service", None) == "daily"
    assert default_rate_basis("service", "daily_consumption") == "daily"
    assert default_rate_basis("tangible", None) == "per_unit"


def test_per_section_charges_need_a_section() -> None:
    assert requires_hole_section("per_section") is True
    assert requires_hole_section("daily") is False


def test_quantity_is_taken_as_entered_off_daily_consumption() -> None:
    resolved = resolve_planned_quantity(
        rate_basis="daily",
        quantity=Decimal("5"),
        daily_consumption=None,
        planned_duration_days=Decimal("5"),
    )
    assert resolved.quantity == Decimal("5")
    assert resolved.computed_quantity is None
    assert resolved.source == "entered"


def test_daily_consumption_multiplies_usage_by_planned_days() -> None:
    resolved = resolve_planned_quantity(
        rate_basis="daily_consumption",
        quantity=None,
        daily_consumption=Decimal("20"),
        planned_duration_days=Decimal("6"),
    )
    assert resolved.quantity == Decimal("120")
    assert resolved.computed_quantity == Decimal("120")
    assert resolved.source == "computed"


def test_daily_consumption_needs_usage_and_days() -> None:
    with pytest.raises(RateBasisError, match="daily_consumption and planned_duration_days"):
        resolve_planned_quantity(
            rate_basis="daily_consumption",
            quantity=None,
            daily_consumption=Decimal("20"),
            planned_duration_days=None,
        )


def test_an_override_without_a_reason_is_refused() -> None:
    with pytest.raises(RateBasisError, match="record a quantity_override_reason"):
        resolve_planned_quantity(
            rate_basis="daily_consumption",
            quantity=Decimal("150"),
            daily_consumption=Decimal("20"),
            planned_duration_days=Decimal("6"),
        )


def test_a_reasoned_override_is_kept_alongside_the_computed_figure() -> None:
    resolved = resolve_planned_quantity(
        rate_basis="daily_consumption",
        quantity=Decimal("150"),
        daily_consumption=Decimal("20"),
        planned_duration_days=Decimal("6"),
        override_reason="Extra volume held at the rig site as contingency stock",
    )
    assert resolved.quantity == Decimal("150")
    assert resolved.computed_quantity == Decimal("120")
    assert resolved.is_overridden is True
    assert resolved.source == "overridden"
