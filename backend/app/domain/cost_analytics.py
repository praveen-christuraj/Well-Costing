"""Cost analytics engine: AFE estimate vs daily actuals, forecast and depth/cost.

Framework-free and pure, like the rest of :mod:`app.domain`, so the comparison
rules can be unit-tested without a database. Everything here is *derived* —
nothing is stored — because the AFE estimate and the daily actuals are both
already persisted and must stay the single source of truth.

The reconciliation middle layer
-------------------------------

Actual cost is captured daily but reconciled weekly (or whenever the user
asks), so the comparison this module produces is a *live* one: it reports the
actuals that exist right now and marks how much of them is already covered by
a reconciliation run. ``reconciled_amount`` / ``unreconciled_amount`` split the
actuals, and every entry carries a reconciliation status, so when the
reconciliation module lands it only has to write those stamps — no change to
the comparison maths below.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.domain.afe_costing import (
    GROUP_CONSUMABLES,
    GROUP_SERVICES,
    GROUP_TANGIBLES,
    money,
    to_decimal,
)

__all__ = [
    "COST_GROUPS",
    "CostForecast",
    "DepthCostPoint",
    "GroupComparison",
    "build_depth_cost_series",
    "compare_groups",
    "forecast_completion",
    "percentage",
]

COST_GROUPS: tuple[str, ...] = (GROUP_SERVICES, GROUP_CONSUMABLES, GROUP_TANGIBLES)

QUANTUM_DAY = Decimal("0.0001")


def percentage(part: object, whole: object) -> Decimal | None:
    """``part`` as a percentage of ``whole`` (None when ``whole`` is zero)."""

    denominator = to_decimal(whole)
    if denominator == 0:
        return None
    return (to_decimal(part) * Decimal("100") / denominator).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


# ---------------------------------------------------------------------------
# AFE vs actual
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroupComparison:
    """One cost group: AFE estimate, actual so far and the balance left."""

    group: str
    estimated: Decimal = Decimal("0")
    actual: Decimal = Decimal("0")
    reconciled: Decimal = Decimal("0")

    @property
    def balance(self) -> Decimal:
        """AFE estimate minus actual — negative means the group is over AFE."""

        return money(to_decimal(self.estimated) - to_decimal(self.actual))

    @property
    def unreconciled(self) -> Decimal:
        return money(to_decimal(self.actual) - to_decimal(self.reconciled))

    @property
    def utilisation(self) -> Decimal | None:
        """Actual as a percentage of the AFE estimate."""

        return percentage(self.actual, self.estimated)

    @property
    def is_over(self) -> bool:
        return self.actual > self.estimated


def compare_groups(
    estimated: Mapping[str, object],
    actual: Mapping[str, object],
    reconciled: Mapping[str, object] | None = None,
) -> tuple[GroupComparison, ...]:
    """Build the Services / Consumables / Tangibles comparison rows."""

    reconciled_map: Mapping[str, object] = reconciled or {}
    return tuple(
        GroupComparison(
            group=group,
            estimated=money(estimated.get(group, Decimal("0"))),
            actual=money(actual.get(group, Decimal("0"))),
            reconciled=money(reconciled_map.get(group, Decimal("0"))),
        )
        for group in COST_GROUPS
    )


# ---------------------------------------------------------------------------
# Forecast at the end of the well
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CostForecast:
    """Burn-rate projection of the well's cost at completion.

    The projection is deliberately simple and explainable: the average cost per
    elapsed day (the *burn rate*) applied to the days still planned, added to
    what has already been spent. ``basis`` states the method in words so the
    report can print it next to the number.
    """

    actual_to_date: Decimal = Decimal("0")
    estimated_total: Decimal = Decimal("0")
    planned_days: Decimal = Decimal("0")
    elapsed_days: Decimal = Decimal("0")
    remaining_days: Decimal = Decimal("0")
    burn_rate_per_day: Decimal = Decimal("0")
    forecast_at_completion: Decimal = Decimal("0")
    basis: str = ""

    @property
    def variance(self) -> Decimal:
        """Forecast at completion minus the AFE estimate."""

        return money(to_decimal(self.forecast_at_completion) - to_decimal(self.estimated_total))

    @property
    def variance_pct(self) -> Decimal | None:
        return percentage(self.variance, self.estimated_total)

    @property
    def balance_at_completion(self) -> Decimal:
        return money(to_decimal(self.estimated_total) - to_decimal(self.forecast_at_completion))


def forecast_completion(
    *,
    actual_to_date: object,
    estimated_total: object,
    planned_days: object,
    elapsed_days: object,
) -> CostForecast:
    """Project the cost at the end of the well from the burn rate.

    ``elapsed_days`` is normally the number of days that already have daily
    cost entries (the days actually worked), and ``planned_days`` the sum of
    the well configuration's phase days. With no elapsed days there is no burn
    rate yet, so the projection falls back to what has been spent so far.
    """

    actual = money(actual_to_date)
    estimate = money(estimated_total)
    planned = to_decimal(planned_days).quantize(QUANTUM_DAY, rounding=ROUND_HALF_UP)
    elapsed = to_decimal(elapsed_days).quantize(QUANTUM_DAY, rounding=ROUND_HALF_UP)
    if elapsed < 0:
        elapsed = Decimal("0")
    remaining = planned - elapsed
    if remaining < 0:
        remaining = Decimal("0")

    if elapsed > 0:
        burn = (actual / elapsed).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        projection = money(actual + burn * remaining)
        basis = (
            f"Burn rate {burn}/day over {elapsed.normalize()} day(s) worked, "
            f"projected across {remaining.normalize()} remaining planned day(s)"
        )
    else:
        burn = Decimal("0")
        projection = actual
        basis = (
            "No elapsed days recorded yet — the forecast equals the actual cost to date"
            if actual
            else "No elapsed days and no actual cost recorded yet — nothing to forecast"
        )

    return CostForecast(
        actual_to_date=actual,
        estimated_total=estimate,
        planned_days=planned,
        elapsed_days=elapsed,
        remaining_days=remaining,
        burn_rate_per_day=burn,
        forecast_at_completion=projection,
        basis=basis,
    )


# ---------------------------------------------------------------------------
# Depth vs cost
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DepthCostPoint:
    """One point of the Depth vs Cost curve, at a hole-section boundary."""

    depth: Decimal
    section_id: int | None = None
    section_label: str = ""
    estimated_cumulative: Decimal = Decimal("0")
    actual_cumulative: Decimal = Decimal("0")
    estimated_section: Decimal = Decimal("0")
    actual_section: Decimal = Decimal("0")

    @property
    def variance(self) -> Decimal:
        return money(self.actual_cumulative - self.estimated_cumulative)


@dataclass(frozen=True)
class DepthCostSeries:
    """The Depth vs Cost chart data plus whatever could not be placed on it."""

    points: tuple[DepthCostPoint, ...] = ()
    unattributed_actual: Decimal = Decimal("0")
    total_estimated: Decimal = Decimal("0")
    total_actual: Decimal = Decimal("0")
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DepthSection:
    """One configured hole section: its depth window and planned days."""

    section_id: int
    section_label: str = ""
    from_depth: Decimal = Decimal("0")
    to_depth: Decimal = Decimal("0")
    planned_days: Decimal = Decimal("0")


def build_depth_cost_series(
    sections: Sequence[DepthSection],
    estimated_by_section: Mapping[int, object],
    actual_by_section: Mapping[int, object],
    *,
    unattributed_actual: object = Decimal("0"),
) -> DepthCostSeries:
    """Cumulative estimated vs actual cost against the well's depth axis.

    The depth axis comes from the well configuration (each section's
    ``to_depth``), the estimated cost from the AFE's per-section rollup and the
    actual cost from the daily cost lines' section scope. Actual cost entered
    without a section cannot be placed at a depth, so it is reported
    separately and added to the deepest point rather than silently dropped.
    """

    notes: list[str] = []
    points: list[DepthCostPoint] = []
    estimated_running = Decimal("0")
    actual_running = Decimal("0")
    ordered = sorted(sections, key=lambda section: (to_decimal(section.to_depth), section.section_id))

    if not ordered:
        notes.append("The well has no configuration yet — depth cannot be plotted.")

    for section in ordered:
        section_estimated = money(estimated_by_section.get(section.section_id, Decimal("0")))
        section_actual = money(actual_by_section.get(section.section_id, Decimal("0")))
        estimated_running = money(estimated_running + section_estimated)
        actual_running = money(actual_running + section_actual)
        points.append(
            DepthCostPoint(
                depth=to_decimal(section.to_depth),
                section_id=section.section_id,
                section_label=section.section_label,
                estimated_cumulative=estimated_running,
                actual_cumulative=actual_running,
                estimated_section=section_estimated,
                actual_section=section_actual,
            )
        )

    orphan_actual = money(unattributed_actual)
    if orphan_actual:
        notes.append(
            "Some actual cost has no section scope; it is added to the deepest point of the curve."
        )
        if points:
            last = points[-1]
            points[-1] = DepthCostPoint(
                depth=last.depth,
                section_id=last.section_id,
                section_label=last.section_label,
                estimated_cumulative=last.estimated_cumulative,
                actual_cumulative=money(last.actual_cumulative + orphan_actual),
                estimated_section=last.estimated_section,
                actual_section=last.actual_section,
            )

    total_estimated = money(sum((to_decimal(value) for value in estimated_by_section.values()), Decimal("0")))
    total_actual = money(
        sum((to_decimal(value) for value in actual_by_section.values()), Decimal("0")) + orphan_actual
    )
    return DepthCostSeries(
        points=tuple(points),
        unattributed_actual=orphan_actual,
        total_estimated=total_estimated,
        total_actual=total_actual,
        notes=tuple(notes),
    )
