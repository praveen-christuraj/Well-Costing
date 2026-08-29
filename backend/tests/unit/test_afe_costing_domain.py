"""Unit tests for the AFE cost estimation engine.

These cover the calculation rules of the AFE Cost Estimation tab without a
database or an HTTP request: day-based charging (hours or decimal days), the
one-time Mobilization / Demobilization / Fixed Charge special case, per-section
and per-service pricing, consumable/tangible override rates and the compiled
totals.
"""

from decimal import Decimal

import pytest
from app.domain import afe_costing as engine


def make_well() -> engine.WellScope:
    """Two sections: Surface (Drilling 5.5 + Casing 2.5) and Intermediate (Drilling 4)."""

    return engine.WellScope(
        well_code="WELL001",
        well_name="Exploratory 1",
        depth_unit="m",
        sections=(
            engine.WellSectionScope(
                section_id=1,
                section_code="SEC1",
                section_name="Surface Section",
                from_depth=Decimal("0"),
                to_depth=Decimal("1500"),
                phases=(
                    engine.WellPhaseScope(11, "PH1", "Drilling", Decimal("5.5")),
                    engine.WellPhaseScope(12, "PH2", "Casing", Decimal("2.5")),
                ),
            ),
            engine.WellSectionScope(
                section_id=2,
                section_code="SEC2",
                section_name="Intermediate",
                from_depth=Decimal("1500"),
                to_depth=Decimal("3000"),
                phases=(engine.WellPhaseScope(11, "PH1", "Drilling", Decimal("4")),),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Vocabulary and quantity conversion
# ---------------------------------------------------------------------------


def test_charge_categories_are_the_constant_eight() -> None:
    assert engine.CHARGE_CATEGORIES == (
        "Mobilization",
        "Demobilization",
        "Operation",
        "Standby",
        "Personnel-Operation",
        "Personnel-Standby",
        "Fixed Charge",
        "Others",
    )
    assert engine.ONE_TIME_CATEGORIES == ("Mobilization", "Demobilization", "Fixed Charge")


@pytest.mark.parametrize(
    ("quantity", "unit", "expected"),
    [
        ("12", "hours", Decimal("0.5000")),
        ("24", "hrs", Decimal("1.0000")),
        ("0.2", "days", Decimal("0.2000")),
        ("0.73", "day", Decimal("0.7300")),
        (Decimal("3"), None, Decimal("3.0000")),
    ],
)
def test_days_from_quantity_accepts_hours_and_decimal_days(quantity: object, unit: object, expected: Decimal) -> None:
    assert engine.days_from_quantity(quantity, unit) == expected


def test_hours_and_days_are_equivalent() -> None:
    assert engine.days_from_quantity(12, "hours") == engine.days_from_quantity("0.5", "days")


def test_negative_quantity_is_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        engine.days_from_quantity("-1", "days")


def test_category_and_basis_labels_are_tolerant() -> None:
    assert engine.normalize_category("personnel operation") == "Personnel-Operation"
    assert engine.normalize_category("FIXED_CHARGE") == "Fixed Charge"
    assert engine.normalize_basis("daily rate") == "Daily Rate"
    assert engine.normalize_basis("PER SECTION RATE") == "Per Section Rate"
    with pytest.raises(ValueError, match="charge category"):
        engine.normalize_category("Transport")


# ---------------------------------------------------------------------------
# Daily rate services
# ---------------------------------------------------------------------------


def test_daily_rate_uses_planned_days_plus_one_time_charges() -> None:
    well = make_well()
    line = engine.ServiceLine(
        service_id=1,
        service_code="SVC-0001",
        service_name="Directional Drilling",
        charging_basis=engine.BASIS_DAILY,
        rates={
            "Operation": Decimal("1000"),
            "Mobilization": Decimal("5000"),
            "Demobilization": Decimal("4000"),
            "Fixed Charge": Decimal("1500"),
        },
    )
    estimate = engine.estimate_service_line(line, well)

    # 12 planned days x 1000 + 5000 + 4000 + 1500
    assert estimate.amount == Decimal("22500.00")
    categories = [component.category for component in estimate.components]
    assert categories == ["Operation", "Mobilization", "Demobilization", "Fixed Charge"]
    operation = estimate.components[0]
    assert operation.quantity == Decimal("12.0")
    assert operation.rate == Decimal("1000.00")


def test_daily_rate_planned_days_follow_the_line_scope() -> None:
    well = make_well()
    scoped = engine.ServiceLine(
        service_id=1,
        service_code="SVC-0001",
        charging_basis=engine.BASIS_DAILY,
        rates={"Operation": Decimal("1000")},
        section_id=1,
        phase_id=11,
    )
    estimate = engine.estimate_service_line(scoped, well)
    # Only the 5.5 drilling days of SEC1 apply.
    assert estimate.amount == Decimal("5500.00")
    assert estimate.section_label == "SEC1 — Surface Section"
    assert estimate.phase_label == "PH1 — Drilling"


def test_entered_day_quantity_overrides_the_planned_days_for_operation() -> None:
    well = make_well()
    line = engine.ServiceLine(
        service_id=1,
        service_code="SVC-0001",
        charging_basis=engine.BASIS_DAILY,
        rates={"Operation": Decimal("1000"), "Standby": Decimal("200")},
        charge_lines=(
            engine.ChargeLine("Operation", Decimal("6"), "hours"),
            engine.ChargeLine("Standby", Decimal("12"), "hours"),
        ),
    )
    estimate = engine.estimate_service_line(line, well)
    # 0.25 day operation (6h) + 0.5 day standby (12h); planned days are not added.
    assert estimate.amount == Decimal("350.00")
    assert len(estimate.components) == 2
    assert estimate.components[0].quantity == Decimal("0.2500")


def test_missing_unit_rate_is_reported_as_a_warning() -> None:
    well = make_well()
    line = engine.ServiceLine(
        service_id=1,
        service_code="SVC-0001",
        charging_basis=engine.BASIS_DAILY,
        rates={"Operation": Decimal("0")},
        charge_lines=(engine.ChargeLine("Standby", Decimal("2"), "days"),),
    )
    estimate = engine.estimate_service_line(line, well)
    assert estimate.amount == Decimal("0.00")
    assert any("Standby: no unit rate configured" in warning for warning in estimate.warnings)


def test_operation_rate_without_a_configuration_warns_instead_of_guessing() -> None:
    line = engine.ServiceLine(
        service_id=1,
        service_code="SVC-0001",
        charging_basis=engine.BASIS_DAILY,
        rates={"Operation": Decimal("1000")},
    )
    estimate = engine.estimate_service_line(line, engine.WellScope())
    assert estimate.amount == Decimal("0.00")
    assert any("no planned days" in warning for warning in estimate.warnings)


# ---------------------------------------------------------------------------
# Per section and per service rates
# ---------------------------------------------------------------------------


def test_per_section_rate_is_constant_for_each_section() -> None:
    well = make_well()
    line = engine.ServiceLine(
        service_id=2,
        service_code="SVC-0002",
        service_name="Casing",
        charging_basis=engine.BASIS_PER_SECTION,
        rates={"Mobilization": Decimal("2500")},
        section_rates=(
            engine.SectionRate(1, None, Decimal("25000")),
            engine.SectionRate(2, 11, Decimal("30000")),
        ),
    )
    estimate = engine.estimate_service_line(line, well)
    # 25000 + 30000 + one mobilization
    assert estimate.amount == Decimal("57500.00")
    assert [component.category for component in estimate.components] == [
        "Per Section Rate",
        "Per Section Rate",
        "Mobilization",
    ]
    assert estimate.components[1].section_label == "SEC2 — Intermediate"
    assert estimate.components[1].phase_label == "PH1 — Drilling"


def test_per_section_rate_outside_the_well_configuration_is_ignored_and_flagged() -> None:
    line = engine.ServiceLine(
        service_id=2,
        service_code="SVC-0002",
        charging_basis=engine.BASIS_PER_SECTION,
        section_rates=(engine.SectionRate(99, None, Decimal("7000")),),
    )
    estimate = engine.estimate_service_line(line, make_well())
    assert estimate.amount == Decimal("0.00")
    assert any("outside the well configuration" in warning for warning in estimate.warnings)


def test_per_service_rate_is_charged_once_for_its_scope() -> None:
    line = engine.ServiceLine(
        service_id=3,
        service_code="SVC-0003",
        charging_basis=engine.BASIS_PER_SERVICE,
        per_service_amount=Decimal("120000"),
        section_id=2,
        phase_id=11,
    )
    estimate = engine.estimate_service_line(line, make_well())
    assert estimate.amount == Decimal("120000.00")
    assert estimate.components[0].description.endswith("SEC2 — Intermediate · PH1 — Drilling")


def test_unknown_scope_is_flagged() -> None:
    line = engine.ServiceLine(
        service_id=3,
        service_code="SVC-0003",
        charging_basis=engine.BASIS_PER_SERVICE,
        per_service_amount=Decimal("100"),
        section_id=42,
    )
    estimate = engine.estimate_service_line(line, make_well())
    assert any("not part of the well configuration" in warning for warning in estimate.warnings)


# ---------------------------------------------------------------------------
# Consumables and tangibles
# ---------------------------------------------------------------------------


def test_consumable_is_priced_per_section_and_phase() -> None:
    line = engine.ConsumableLine(
        item_id=5,
        item_code="MC-0001",
        item_name="Bentonite",
        quantity=Decimal("10"),
        captured_rate=Decimal("120"),
        uom="Sack",
        section_id=1,
        phase_id=11,
    )
    estimate = engine.estimate_consumable_line(line, make_well())
    assert estimate.amount == Decimal("1200.00")
    assert estimate.section_label == "SEC1 — Surface Section"
    assert estimate.phase_label == "PH1 — Drilling"


def test_unscoped_consumable_is_flagged() -> None:
    line = engine.ConsumableLine(item_id=5, item_code="MC-0001", item_name="Bentonite")
    estimate = engine.estimate_consumable_line(line, make_well())
    assert any("not scoped" in warning for warning in estimate.warnings)


def test_tangible_override_rate_wins_over_the_captured_rate() -> None:
    captured = engine.TangibleLine(
        tangible_id=7, tangible_code="TG-0001", tangible_name="BOP", captured_rate=Decimal("500000")
    )
    overridden = engine.TangibleLine(
        tangible_id=7,
        tangible_code="TG-0001",
        tangible_name="BOP",
        captured_rate=Decimal("500000"),
        override_rate=Decimal("450000"),
    )
    assert engine.estimate_tangible_line(captured).amount == Decimal("500000.00")
    override_estimate = engine.estimate_tangible_line(overridden)
    assert override_estimate.amount == Decimal("450000.00")
    assert override_estimate.components[0].category == "Override rate"


def test_tangible_quantity_multiplies_the_rate() -> None:
    line = engine.TangibleLine(
        tangible_id=8,
        tangible_code="TG-0002",
        tangible_name="Casing joint",
        quantity=Decimal("12.5"),
        captured_rate=Decimal("800"),
    )
    assert engine.estimate_tangible_line(line).amount == Decimal("10000.00")


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


def test_compile_totals_every_group_and_rolls_up_by_section() -> None:
    well = make_well()
    services = [
        engine.ServiceLine(
            service_id=1,
            service_code="SVC-0001",
            charging_basis=engine.BASIS_DAILY,
            rates={"Operation": Decimal("1000")},
            section_id=1,
        ),
    ]
    consumables = [
        engine.ConsumableLine(
            item_id=5,
            item_code="MC-0001",
            item_name="Bentonite",
            quantity=Decimal("2"),
            captured_rate=Decimal("100"),
            section_id=2,
            phase_id=11,
        )
    ]
    tangibles = [
        engine.TangibleLine(
            tangible_id=7, tangible_code="TG-0001", tangible_name="BOP", captured_rate=Decimal("50000")
        )
    ]
    estimate = engine.compile_afe_estimate(well, services, consumables, tangibles)

    assert estimate.services.amount == Decimal("8000.00")  # 8 days of SEC1
    assert estimate.consumables.amount == Decimal("200.00")
    assert estimate.tangibles.amount == Decimal("50000.00")
    assert estimate.total == Decimal("58200.00")

    rollup = {row.section_label: row.amount for row in estimate.by_section}
    assert rollup["SEC1 — Surface Section"] == Decimal("8000.00")
    assert rollup["SEC2 — Intermediate"] == Decimal("200.00")
    assert rollup["Well-wide (no section)"] == Decimal("50000.00")


def test_estimate_without_a_configuration_explains_itself() -> None:
    estimate = engine.compile_afe_estimate(engine.WellScope())
    assert estimate.total == Decimal("0.00")
    assert any("no configuration" in warning for warning in estimate.warnings)
