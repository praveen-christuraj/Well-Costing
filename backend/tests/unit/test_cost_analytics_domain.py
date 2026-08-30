"""Unit tests for the cost analytics engine (AFE vs actual, forecast, depth)."""

from decimal import Decimal

from app.domain import cost_analytics as analytics
from app.domain.afe_costing import GROUP_CONSUMABLES, GROUP_SERVICES, GROUP_TANGIBLES


def test_compare_groups_reports_balance_and_utilisation() -> None:
    rows = analytics.compare_groups(
        {GROUP_SERVICES: Decimal("1000"), GROUP_CONSUMABLES: Decimal("500"), GROUP_TANGIBLES: Decimal("200")},
        {GROUP_SERVICES: Decimal("800"), GROUP_CONSUMABLES: Decimal("600"), GROUP_TANGIBLES: Decimal("0")},
        {GROUP_SERVICES: Decimal("700"), GROUP_CONSUMABLES: Decimal("0"), GROUP_TANGIBLES: Decimal("0")},
    )
    by_group = {row.group: row for row in rows}
    assert by_group[GROUP_SERVICES].balance == Decimal("200.00")
    assert by_group[GROUP_SERVICES].utilisation == Decimal("80.00")
    assert by_group[GROUP_SERVICES].unreconciled == Decimal("100.00")
    assert by_group[GROUP_SERVICES].is_over is False
    # Consumables are over AFE: the balance goes negative and the flag is set.
    assert by_group[GROUP_CONSUMABLES].balance == Decimal("-100.00")
    assert by_group[GROUP_CONSUMABLES].is_over is True
    assert by_group[GROUP_TANGIBLES].balance == Decimal("200.00")
    assert by_group[GROUP_TANGIBLES].utilisation == Decimal("0.00")


def test_utilisation_is_none_without_an_afe_estimate() -> None:
    row = analytics.compare_groups({}, {GROUP_SERVICES: Decimal("100")})[0]
    assert row.utilisation is None
    assert row.balance == Decimal("-100.00")


def test_forecast_projects_the_burn_rate_over_the_remaining_days() -> None:
    """500k spent over 10 of 30 planned days → 1.5M at completion."""

    projection = analytics.forecast_completion(
        actual_to_date=Decimal("500000"),
        estimated_total=Decimal("1200000"),
        planned_days=Decimal("30"),
        elapsed_days=Decimal("10"),
    )
    assert projection.burn_rate_per_day == Decimal("50000.00")
    assert projection.remaining_days == Decimal("20.0000")
    assert projection.forecast_at_completion == Decimal("1500000.00")
    assert projection.variance == Decimal("300000.00")
    assert projection.variance_pct == Decimal("25.00")
    assert projection.balance_at_completion == Decimal("-300000.00")
    assert "Burn rate" in projection.basis


def test_forecast_without_elapsed_days_falls_back_to_the_actual() -> None:
    projection = analytics.forecast_completion(
        actual_to_date=Decimal("1000"),
        estimated_total=Decimal("9000"),
        planned_days=Decimal("20"),
        elapsed_days=Decimal("0"),
    )
    assert projection.burn_rate_per_day == Decimal("0")
    assert projection.forecast_at_completion == Decimal("1000.00")
    assert "No elapsed days" in projection.basis


def test_forecast_never_projects_negative_remaining_days() -> None:
    projection = analytics.forecast_completion(
        actual_to_date=Decimal("1000"),
        estimated_total=Decimal("900"),
        planned_days=Decimal("5"),
        elapsed_days=Decimal("8"),
    )
    assert projection.remaining_days == Decimal("0.0000")
    assert projection.forecast_at_completion == Decimal("1000.00")


def test_depth_series_is_cumulative_against_the_section_depths() -> None:
    series = analytics.build_depth_cost_series(
        [
            analytics.DepthSection(section_id=1, section_label="SEC1", to_depth=Decimal("500")),
            analytics.DepthSection(section_id=2, section_label="SEC2", to_depth=Decimal("1500")),
            analytics.DepthSection(section_id=3, section_label="SEC3", to_depth=Decimal("3000")),
        ],
        {1: Decimal("100"), 2: Decimal("300"), 3: Decimal("600")},
        {1: Decimal("120"), 2: Decimal("250")},
    )
    assert [point.depth for point in series.points] == [Decimal("500"), Decimal("1500"), Decimal("3000")]
    assert [point.estimated_cumulative for point in series.points] == [
        Decimal("100.00"),
        Decimal("400.00"),
        Decimal("1000.00"),
    ]
    assert [point.actual_cumulative for point in series.points] == [
        Decimal("120.00"),
        Decimal("370.00"),
        Decimal("370.00"),
    ]
    assert series.total_estimated == Decimal("1000.00")
    assert series.total_actual == Decimal("370.00")
    assert series.unattributed_actual == Decimal("0.00")


def test_depth_series_adds_unattributed_actual_to_the_deepest_point() -> None:
    """Tangibles carry no section, so they land on the last point with a note."""

    series = analytics.build_depth_cost_series(
        [analytics.DepthSection(section_id=1, section_label="SEC1", to_depth=Decimal("500"))],
        {1: Decimal("100")},
        {},
        unattributed_actual=Decimal("250"),
    )
    assert series.points[0].actual_cumulative == Decimal("250.00")
    assert series.unattributed_actual == Decimal("250.00")
    assert any("no section scope" in note for note in series.notes)


def test_depth_series_without_a_configuration_says_so() -> None:
    series = analytics.build_depth_cost_series([], {}, {})
    assert series.points == ()
    assert any("no configuration" in note for note in series.notes)


def test_percentage_handles_a_zero_denominator() -> None:
    assert analytics.percentage(Decimal("10"), Decimal("0")) is None
    assert analytics.percentage(Decimal("10"), Decimal("40")) == Decimal("25.00")
