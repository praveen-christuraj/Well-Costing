"""Unit tests for the daily cost calculation engine.

The rules under test are the ones the Daily Costs page depends on: which AFE
rate is used, how hours/days become money, why Mobilization / Demobilization /
Fixed Charge are never multiplied, how the four consumable categories are
priced (including the manual cement-additive total) and how a day rolls up.
"""

from decimal import Decimal

import pytest
from app.domain import daily_costing as engine


def test_daily_rate_service_converts_hours_to_days() -> None:
    """12 hours at a 1,000/day operation rate is half a day: 500."""

    amount = engine.service_amount(
        charging_basis="Daily Rate",
        charge_category="Operation",
        quantity=Decimal("12"),
        quantity_unit="hours",
        captured_rate=Decimal("1000"),
        override_rate=None,
    )
    assert amount == Decimal("500.00")


def test_daily_rate_service_accepts_decimal_days() -> None:
    """A quantity entered in days is used as-is (0.25 days x 1000)."""

    amount = engine.service_amount(
        charging_basis="Daily Rate",
        charge_category="Standby",
        quantity=Decimal("0.25"),
        quantity_unit="days",
        captured_rate=Decimal("1000"),
        override_rate=None,
    )
    assert amount == Decimal("250.00")


def test_one_time_categories_are_never_multiplied() -> None:
    """Mobilization / Demobilization / Fixed Charge charge the whole amount once."""

    for category in ("Mobilization", "Demobilization", "Fixed Charge"):
        amount = engine.service_amount(
            charging_basis="Daily Rate",
            charge_category=category,
            quantity=Decimal("24"),
            quantity_unit="hours",
            captured_rate=Decimal("7500"),
            override_rate=None,
        )
        assert amount == Decimal("7500.00"), category
        assert engine.is_one_time_category(category)


def test_day_based_categories_are_multiplied() -> None:
    for category in engine.DAY_BASED_CATEGORIES:
        assert not engine.is_one_time_category(category)


def test_override_rate_replaces_the_captured_afe_rate() -> None:
    amount = engine.service_amount(
        charging_basis="Daily Rate",
        charge_category="Operation",
        quantity=Decimal("24"),
        quantity_unit="hours",
        captured_rate=Decimal("1000"),
        override_rate=Decimal("1500"),
    )
    assert amount == Decimal("1500.00")


def test_per_service_and_per_section_rates_are_lump_sums() -> None:
    per_service = engine.service_amount(
        charging_basis="Per Service Rate",
        charge_category="Per Service Rate",
        quantity=Decimal("3"),
        quantity_unit="days",
        captured_rate=Decimal("25000"),
        override_rate=None,
    )
    per_section = engine.service_amount(
        charging_basis="Per Section Rate",
        charge_category="Per Section Rate",
        quantity=Decimal("0.5"),
        quantity_unit="days",
        captured_rate=Decimal("18000"),
        override_rate=None,
    )
    assert per_service == Decimal("25000.00")
    assert per_section == Decimal("18000.00")


@pytest.mark.parametrize(
    ("quantity", "unit"),
    [(Decimal("24.5"), "hours"), (Decimal("-1"), "hours"), (Decimal("1.5"), "days")],
)
def test_quantity_outside_the_entered_range_is_rejected(quantity: Decimal, unit: str) -> None:
    """Hours run 0-24 and days 0-1; anything else is a user error."""

    with pytest.raises(ValueError):
        engine.service_amount(
            charging_basis="Daily Rate",
            charge_category="Operation",
            quantity=quantity,
            quantity_unit=unit,
            captured_rate=Decimal("1000"),
            override_rate=None,
        )


def test_validate_quantity_accepts_the_whole_allowed_range() -> None:
    assert engine.validate_quantity(Decimal("0"), "hours") == Decimal("0")
    assert engine.validate_quantity(Decimal("24"), "hours") == Decimal("24")
    assert engine.validate_quantity(Decimal("7.5"), "hrs") == Decimal("7.5")
    assert engine.validate_quantity(Decimal("1"), "days") == Decimal("1")
    assert engine.validate_quantity(Decimal("0.33"), "d") == Decimal("0.33")


def test_consumable_usage_multiplies_the_unit_rate() -> None:
    amount = engine.consumable_amount(
        category="mud_chemical",
        quantity=Decimal("25"),
        captured_rate=Decimal("120"),
        override_rate=None,
    )
    assert amount == Decimal("3000.00")


def test_consumable_override_rate_wins() -> None:
    amount = engine.consumable_amount(
        category="drill_bit",
        quantity=Decimal("2"),
        captured_rate=Decimal("120"),
        override_rate=Decimal("150"),
    )
    assert amount == Decimal("300.00")


def test_cement_additives_take_the_manual_total() -> None:
    """Cement additives are entered as the day's total consumption cost."""

    amount = engine.consumable_amount(
        category="cement_additive",
        quantity=Decimal("0"),
        captured_rate=Decimal("0"),
        override_rate=None,
        manual_amount=Decimal("4321.55"),
    )
    assert amount == Decimal("4321.55")


def test_tangible_quantity_multiplies_the_unit_rate() -> None:
    amount = engine.tangible_amount(
        quantity=Decimal("120"), captured_rate=Decimal("850"), override_rate=None
    )
    assert amount == Decimal("102000.00")


def test_consumable_category_labels_are_tolerant() -> None:
    assert engine.normalize_consumable_category("Mud Chemicals") == engine.MUD_CHEMICAL
    assert engine.normalize_consumable_category("fuel") == engine.FUEL
    assert engine.normalize_consumable_category("Cement Additives") == engine.CEMENT_ADDITIVE
    assert engine.normalize_consumable_category("Drill Bits") == engine.DRILL_BIT
    assert len(engine.CONSUMABLE_CATEGORIES) == 4
    with pytest.raises(ValueError):
        engine.normalize_consumable_category("Explosives")


def test_compile_daily_cost_totals_the_three_groups() -> None:
    estimate = engine.compile_daily_cost(
        service_lines=[
            engine.DailyServiceLine(
                line_id=1,
                service_id=10,
                service_code="SVC-MWD",
                service_name="MWD",
                charging_basis="Daily Rate",
                charge_category="Operation",
                quantity=Decimal("12"),
                quantity_unit="hours",
                captured_rate=Decimal("1000"),
            ),
            engine.DailyServiceLine(
                line_id=2,
                service_id=10,
                service_code="SVC-MWD",
                service_name="MWD",
                charging_basis="Daily Rate",
                charge_category="Mobilization",
                quantity=Decimal("1"),
                quantity_unit="days",
                captured_rate=Decimal("5000"),
            ),
        ],
        consumable_lines=[
            engine.DailyConsumableLine(
                line_id=3,
                category="mud_chemical",
                item_code="CHEM-1",
                item_name="Caustic soda",
                quantity=Decimal("10"),
                captured_rate=Decimal("50"),
            ),
        ],
        tangible_lines=[
            engine.DailyTangibleLine(
                line_id=4,
                tangible_id=30,
                tangible_code="TNG-1",
                tangible_name="Casing 9-5/8",
                quantity=Decimal("2"),
                captured_rate=Decimal("9000"),
            ),
        ],
    )
    assert estimate.totals.services == Decimal("5500.00")
    assert estimate.totals.consumables == Decimal("500.00")
    assert estimate.totals.tangibles == Decimal("18000.00")
    assert estimate.total == Decimal("24000.00")
    assert estimate.amount_of(1) == Decimal("500.00")
    assert estimate.amount_of(4) == Decimal("18000.00")


def test_same_service_can_repeat_across_sub_activities_without_interference() -> None:
    """One day, one service, two sub activities, different charge categories."""

    estimate = engine.compile_daily_cost(
        service_lines=[
            engine.DailyServiceLine(
                line_id=1,
                service_id=10,
                service_code="SVC-MWD",
                charging_basis="Daily Rate",
                charge_category="Operation",
                sub_activity_id=1,
                quantity=Decimal("6"),
                quantity_unit="hours",
                captured_rate=Decimal("1200"),
            ),
            engine.DailyServiceLine(
                line_id=2,
                service_id=10,
                service_code="SVC-MWD",
                charging_basis="Daily Rate",
                charge_category="Standby",
                sub_activity_id=2,
                quantity=Decimal("3"),
                quantity_unit="hours",
                captured_rate=Decimal("400"),
            ),
        ]
    )
    assert estimate.totals.services == Decimal("350.00")  # 6/24*1200 + 3/24*400
    assert {line.line_id for line in estimate.service_lines} == {1, 2}


def test_missing_rate_and_one_time_quantity_are_warned_not_fatal() -> None:
    estimate = engine.compile_daily_cost(
        service_lines=[
            engine.DailyServiceLine(
                line_id=1,
                service_id=10,
                service_code="SVC-X",
                charging_basis="Daily Rate",
                charge_category="Mobilization",
                quantity=Decimal("12"),
                quantity_unit="hours",
                captured_rate=Decimal("0"),
            )
        ]
    )
    assert estimate.totals.services == Decimal("0.00")
    assert any("no unit rate captured" in warning for warning in estimate.totals.warnings)
    assert any("one-time charge" in warning for warning in estimate.totals.warnings)


def test_rate_card_resolves_category_and_section_amounts() -> None:
    card = engine.RateCardEntry(
        service_id=10,
        service_code="SVC-MWD",
        charging_basis="Daily Rate",
        rates={"Operation": Decimal("1000"), "Standby": Decimal("400")},
        section_rates=(
            engine.SectionRateEntry(section_id=1, amount=Decimal("5000")),
            engine.SectionRateEntry(section_id=2, phase_id=7, amount=Decimal("9000")),
        ),
    )
    assert card.rate_for("operation") == Decimal("1000")
    assert card.rate_for("Personnel-Standby") == Decimal("0")
    assert card.section_amount(1) == Decimal("5000")
    assert card.section_amount(2, 7) == Decimal("9000")
    assert card.section_amount(3) == Decimal("0")
