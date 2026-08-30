"""Cost analytics + reporting service.

One place answers "what did we estimate, what did we actually spend, and what
will the well cost at the end": it reads the **AFE** estimates and the **daily
cost** actuals of a well, compares them per cost group, projects the cost at
completion and rolls the actuals up by every drill-through the Reports page
offers (date, section, phase, activity, sub activity, service, charge category,
consumable category, tangible).

Reconciliation sits in the middle of that comparison and is *reported*, not
performed, here: the entries already carry ``reconciliation_status`` /
``reconciled_at`` / ``reconciliation_ref``, so the analytics can always say how
much of the actual cost is reconciled and how much is still pending. When the
reconciliation module lands it stamps those fields and these numbers start
moving on their own — nothing in this module has to change.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import cost_analytics as analytics
from app.domain.afe_costing import (
    GROUP_CONSUMABLES,
    GROUP_SERVICES,
    GROUP_TANGIBLES,
    WellScope,
    money,
    scope_label,
    to_decimal,
)
from app.domain.daily_costing import (
    CONSUMABLE_CATEGORY_LABELS,
    RECONCILIATION_RECONCILED,
)
from app.models.afe import Afe
from app.models.daily_cost import DailyCostEntry
from app.models.rig_well import Well
from app.schemas.daily_cost import (
    CostForecastOut,
    DepthCostPointOut,
    GroupComparisonOut,
    ReportOut,
    ReportRowOut,
    WellAnalyticsOut,
    WellAnalyticsSummaryOut,
)
from app.services.afe_estimation import build_well_scope, compile_estimate
from app.services.daily_cost import entry_totals

UNASSIGNED = "__unassigned__"
UNASSIGNED_LABEL = "Not assigned"

DIMENSION_TITLES: dict[str, str] = {
    "date": "Cost by Date",
    "section": "Cost by Hole Section",
    "phase": "Cost by Phase",
    "activity": "Cost by Well Activity",
    "sub_activity": "Cost by Well Sub Activity",
    "service": "Cost by Service",
    "charge_category": "Cost by Charge Category",
    "consumable_category": "Cost by Consumable Category",
    "tangible": "Cost by Tangible",
    "well": "Overall Well Cost",
}

#: Drill-throughs the Reports page offers (``well`` is the overall summary).
REPORT_DIMENSIONS: tuple[str, ...] = tuple(DIMENSION_TITLES)


# ---------------------------------------------------------------------------
# Well-scoped reads
# ---------------------------------------------------------------------------


def list_entries(
    db: Session,
    *,
    well_id: int | None = None,
    rig_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
    deleted: bool = False,
) -> list[DailyCostEntry]:
    """Every day sheet matching the filters (newest day first)."""

    stmt = select(DailyCostEntry).where(DailyCostEntry.is_deleted == deleted)
    if well_id is not None:
        stmt = stmt.where(DailyCostEntry.well_id == well_id)
    if rig_id is not None:
        stmt = stmt.where(DailyCostEntry.rig_id == rig_id)
    if from_date is not None:
        stmt = stmt.where(DailyCostEntry.cost_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(DailyCostEntry.cost_date <= to_date)
    if not include_draft:
        stmt = stmt.where(DailyCostEntry.status != "draft")
    return list(db.scalars(stmt.order_by(DailyCostEntry.cost_date.desc(), DailyCostEntry.id.desc())).all())


def list_well_afes(db: Session, well: Well) -> list[Afe]:
    """Every (non-deleted) AFE of a well — the well's budget is their sum."""

    return list(
        db.scalars(
            select(Afe).where(Afe.well_id == well.id, Afe.is_deleted == False).order_by(Afe.id)
        ).all()
    )


def afe_totals(afes: list[Afe]) -> dict[str, Decimal]:
    """Sum the estimates of every AFE of the well per cost group."""

    totals = {GROUP_SERVICES: Decimal("0"), GROUP_CONSUMABLES: Decimal("0"), GROUP_TANGIBLES: Decimal("0")}
    for afe in afes:
        estimate = compile_estimate(afe)
        totals[GROUP_SERVICES] += estimate.services.amount
        totals[GROUP_CONSUMABLES] += estimate.consumables.amount
        totals[GROUP_TANGIBLES] += estimate.tangibles.amount
    return {group: money(amount) for group, amount in totals.items()}


def afe_section_totals(afes: list[Afe]) -> dict[int, Decimal]:
    """Sum the per-section AFE rollups of every AFE of the well."""

    totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for afe in afes:
        estimate = compile_estimate(afe)
        for row in estimate.by_section:
            if row.section_id is None:
                continue
            totals[row.section_id] += to_decimal(row.amount)
    return {section_id: money(amount) for section_id, amount in totals.items()}


# ---------------------------------------------------------------------------
# Flat lines — one dict per cost line, scope labels already resolved
# ---------------------------------------------------------------------------


def _line_rate(line: Any) -> Decimal:
    """The rate that actually priced the line (the override wins)."""

    if line.override_rate is not None:
        return to_decimal(line.override_rate)
    return to_decimal(line.captured_rate)


def _scope_labels(scope: WellScope | None, section_id: int | None, phase_id: int | None) -> tuple[str, str]:
    if scope is None:
        return ("", "")
    section = scope.find_section(section_id) if section_id is not None else None
    section_label = section.label if section else ""
    phase_label = ""
    if phase_id is not None:
        code, name = scope.phase_code_and_name(phase_id)
        phase_label = scope_label(code, name) if (code or name) else ""
    return (section_label, phase_label)


def flat_lines(entry: DailyCostEntry, scope: WellScope | None) -> list[dict[str, Any]]:
    """Every line of one day as a flat dict, with its resolved scope labels."""

    well = entry.well
    well_label = f"{well.well_code} - {well.well_name}" if well else str(entry.well_id)

    def base(**extra: Any) -> dict[str, Any]:
        row: dict[str, Any] = {
            "cost_date": entry.cost_date,
            "daily_cost_code": entry.daily_cost_code,
            "well_id": entry.well_id,
            "rig_id": entry.rig_id,
            "well_label": well_label,
            "status": entry.status,
            "reconciliation_status": entry.reconciliation_status,
            "section_id": None,
            "section_label": "",
            "phase_id": None,
            "phase_label": "",
            "sub_activity_id": None,
            "sub_activity": "",
            "activity_id": None,
            "activity": "",
            "remarks": "",
        }
        row.update(extra)
        return row

    def scope_of(sub: Any, section_id: int | None, phase_id: int | None) -> dict[str, Any]:
        section_label, phase_label = _scope_labels(scope, section_id, phase_id)
        return {
            "section_id": section_id,
            "section_label": section_label,
            "phase_id": phase_id,
            "phase_label": phase_label,
            "sub_activity_id": sub.id if sub else None,
            "sub_activity": f"{sub.sub_activity_code} - {sub.sub_activity_name}" if sub else "",
            "activity_id": sub.activity_id if sub else None,
            "activity": (
                f"{sub.activity.activity_code} - {sub.activity.activity_name}"
                if sub and sub.activity
                else ""
            ),
        }

    lines: list[dict[str, Any]] = []
    for line in entry.service_lines:
        lines.append(
            base(
                group=GROUP_SERVICES,
                category=line.charge_category,
                code=line.service.service_code if line.service else "",
                name=line.service.service_name if line.service else "",
                charging_basis=line.charging_basis,
                quantity=to_decimal(line.quantity),
                unit=line.quantity_unit or "hours",
                rate=_line_rate(line),
                amount=to_decimal(line.amount),
                remarks=line.remarks or "",
                **scope_of(line.sub_activity, line.section_id, line.phase_id),
            )
        )
    for line in entry.consumable_lines:
        lines.append(
            base(
                group=GROUP_CONSUMABLES,
                category=CONSUMABLE_CATEGORY_LABELS.get(line.category, line.category),
                code=line.item_code,
                name=line.item_name,
                charging_basis=line.category,
                quantity=to_decimal(line.quantity),
                unit=line.uom or "",
                rate=_line_rate(line),
                amount=to_decimal(line.amount),
                remarks=line.remarks or "",
                **scope_of(line.sub_activity, line.section_id, line.phase_id),
            )
        )
    for line in entry.tangible_lines:
        lines.append(
            base(
                group=GROUP_TANGIBLES,
                category="Tangible",
                code=line.tangible.tangible_code if line.tangible else "",
                name=line.tangible.tangible_name if line.tangible else "",
                charging_basis="",
                quantity=to_decimal(line.quantity),
                unit=line.uom or "",
                rate=_line_rate(line),
                amount=to_decimal(line.amount),
                remarks=line.remarks or "",
            )
        )
    return lines


def flatten_entries(entries: list[DailyCostEntry], scopes: dict[int, WellScope]) -> list[dict[str, Any]]:
    """Flat lines of many days (the scopes come from each entry's well)."""

    lines: list[dict[str, Any]] = []
    for entry in entries:
        lines.extend(flat_lines(entry, scopes.get(entry.well_id)))
    return lines


def scopes_for(entries: list[DailyCostEntry]) -> dict[int, WellScope]:
    """One well-configuration snapshot per well the entries belong to."""

    scopes: dict[int, WellScope] = {}
    for entry in entries:
        # `well_id` is not nullable, so the entry always carries its well.
        if entry.well_id not in scopes:
            scopes[entry.well_id] = build_well_scope(entry.well)
    return scopes


# ---------------------------------------------------------------------------
# Actuals rollup
# ---------------------------------------------------------------------------


class ActualRollup:
    """Everything the actuals of a well roll up to, in one pass over the days."""

    def __init__(self) -> None:
        self.groups: dict[str, Decimal] = {
            GROUP_SERVICES: Decimal("0"),
            GROUP_CONSUMABLES: Decimal("0"),
            GROUP_TANGIBLES: Decimal("0"),
        }
        self.reconciled: dict[str, Decimal] = {
            GROUP_SERVICES: Decimal("0"),
            GROUP_CONSUMABLES: Decimal("0"),
            GROUP_TANGIBLES: Decimal("0"),
        }
        self.unreconciled_amount = Decimal("0")
        self.by_section: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        self.by_phase: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        self.by_sub_activity: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        self.by_date: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
        self.unattributed_section_amount = Decimal("0")
        self.days_with_cost = 0
        self.first_cost_date: date | None = None
        self.last_cost_date: date | None = None
        self.lines: list[dict[str, Any]] = []

    @property
    def total(self) -> Decimal:
        return money(sum(self.groups.values(), Decimal("0")))

    @property
    def reconciled_total(self) -> Decimal:
        return money(sum(self.reconciled.values(), Decimal("0")))


def rollup_actuals(entries: list[DailyCostEntry], scopes: dict[int, WellScope]) -> ActualRollup:
    """One pass over the days, bucketing every line amount by its scope."""

    rollup = ActualRollup()
    dates: set[date] = set()
    for entry in entries:
        services, consumables, tangibles = entry_totals(entry)
        day_total = money(services + consumables + tangibles)
        rollup.groups[GROUP_SERVICES] += services
        rollup.groups[GROUP_CONSUMABLES] += consumables
        rollup.groups[GROUP_TANGIBLES] += tangibles
        rollup.by_date[entry.cost_date] += day_total
        if day_total:
            dates.add(entry.cost_date)
            rollup.first_cost_date = (
                entry.cost_date
                if rollup.first_cost_date is None
                else min(rollup.first_cost_date, entry.cost_date)
            )
            rollup.last_cost_date = (
                entry.cost_date
                if rollup.last_cost_date is None
                else max(rollup.last_cost_date, entry.cost_date)
            )
        if entry.reconciliation_status == RECONCILIATION_RECONCILED:
            rollup.reconciled[GROUP_SERVICES] += services
            rollup.reconciled[GROUP_CONSUMABLES] += consumables
            rollup.reconciled[GROUP_TANGIBLES] += tangibles
        else:
            rollup.unreconciled_amount += day_total

        for line in flat_lines(entry, scopes.get(entry.well_id)):
            rollup.lines.append(line)
            amount = to_decimal(line["amount"])
            if line["section_id"] is not None:
                rollup.by_section[line["section_id"]] += amount
            else:
                rollup.unattributed_section_amount += amount
            if line["phase_id"] is not None:
                rollup.by_phase[line["phase_id"]] += amount
            if line["sub_activity_id"] is not None:
                rollup.by_sub_activity[line["sub_activity_id"]] += amount

    rollup.days_with_cost = len(dates)
    rollup.groups = {group: money(amount) for group, amount in rollup.groups.items()}
    rollup.reconciled = {group: money(amount) for group, amount in rollup.reconciled.items()}
    return rollup


# ---------------------------------------------------------------------------
# Drill-through buckets
# ---------------------------------------------------------------------------


def _dimension_key(line: dict[str, Any], dimension: str) -> tuple[str, str]:
    """The (key, label) a line belongs to for one drill-through dimension."""

    if dimension == "date":
        day = line["cost_date"]
        return (day.isoformat(), day.strftime("%d-%b-%Y"))
    if dimension == "section":
        if line["section_id"] is None:
            return (UNASSIGNED, UNASSIGNED_LABEL)
        return (str(line["section_id"]), line["section_label"] or f"Section {line['section_id']}")
    if dimension == "phase":
        if line["phase_id"] is None:
            return (UNASSIGNED, UNASSIGNED_LABEL)
        return (str(line["phase_id"]), line["phase_label"] or f"Phase {line['phase_id']}")
    if dimension == "activity":
        if not line["activity_id"]:
            return (UNASSIGNED, UNASSIGNED_LABEL)
        return (str(line["activity_id"]), line["activity"])
    if dimension == "sub_activity":
        if not line["sub_activity_id"]:
            return (UNASSIGNED, UNASSIGNED_LABEL)
        return (str(line["sub_activity_id"]), line["sub_activity"])
    if dimension == "service":
        if line["group"] != GROUP_SERVICES:
            return (UNASSIGNED, "Not a service")
        return (f"service:{line['code']}", f"{line['code']} - {line['name']}")
    if dimension == "charge_category":
        if line["group"] != GROUP_SERVICES:
            return (UNASSIGNED, "Not a service")
        return (str(line["category"]), str(line["category"]))
    if dimension == "consumable_category":
        if line["group"] != GROUP_CONSUMABLES:
            return (UNASSIGNED, "Not a consumable")
        return (str(line["charging_basis"]), str(line["category"]))
    if dimension == "tangible":
        if line["group"] != GROUP_TANGIBLES:
            return (UNASSIGNED, "Not a tangible")
        return (f"tangible:{line['code']}", f"{line['code']} - {line['name']}")
    return ("well", "All costs")


def bucket_lines(lines: list[dict[str, Any]], dimension: str) -> dict[tuple[str, str], dict[str, Decimal]]:
    """Group flat lines per (key, label) with the three cost groups split."""

    buckets: dict[tuple[str, str], dict[str, Decimal]] = {}
    for line in lines:
        key = _dimension_key(line, dimension)
        bucket = buckets.setdefault(
            key,
            {GROUP_SERVICES: Decimal("0"), GROUP_CONSUMABLES: Decimal("0"), GROUP_TANGIBLES: Decimal("0")},
        )
        bucket[line["group"]] += to_decimal(line["amount"])
    return buckets


def build_report_rows(
    lines: list[dict[str, Any]],
    dimension: str,
    estimated_by_key: dict[str, Decimal] | None = None,
) -> list[ReportRowOut]:
    """Report rows of one dimension, biggest first."""

    estimated_by_key = estimated_by_key or {}
    rows = [
        ReportRowOut(
            key=key,
            label=label,
            services=money(amounts[GROUP_SERVICES]),
            consumables=money(amounts[GROUP_CONSUMABLES]),
            tangibles=money(amounts[GROUP_TANGIBLES]),
            total=money(sum(amounts.values(), Decimal("0"))),
            estimated=money(estimated_by_key.get(key, Decimal("0"))),
            balance=money(estimated_by_key.get(key, Decimal("0")) - sum(amounts.values(), Decimal("0"))),
        )
        for (key, label), amounts in bucket_lines(lines, dimension).items()
    ]
    rows.sort(key=lambda row: (-row.total, row.label))
    return rows


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


def build_summary(
    well: Well,
    afes: list[Afe],
    rollup: ActualRollup,
    planned_days: Decimal,
) -> WellAnalyticsSummaryOut:
    """One row of the Cost Analytics table."""

    estimated = afe_totals(afes)
    estimated_total = money(sum(estimated.values(), Decimal("0")))
    actual_total = rollup.total
    elapsed = Decimal(rollup.days_with_cost)
    projection = analytics.forecast_completion(
        actual_to_date=actual_total,
        estimated_total=estimated_total,
        planned_days=planned_days,
        elapsed_days=elapsed,
    )
    rig = well.rig
    return WellAnalyticsSummaryOut(
        well_id=well.id,
        well_code=well.well_code or "",
        well_name=well.well_name or "",
        rig_id=well.rig_id,
        rig_code=rig.rig_code if rig else None,
        rig_name=rig.rig_name if rig else None,
        well_status=well.status or "",
        depth_unit=well.depth_unit or "m",
        afe_count=len(afes),
        estimated_total=estimated_total,
        estimated_services=estimated[GROUP_SERVICES],
        estimated_consumables=estimated[GROUP_CONSUMABLES],
        estimated_tangibles=estimated[GROUP_TANGIBLES],
        actual_total=actual_total,
        actual_services=rollup.groups[GROUP_SERVICES],
        actual_consumables=rollup.groups[GROUP_CONSUMABLES],
        actual_tangibles=rollup.groups[GROUP_TANGIBLES],
        balance=money(estimated_total - actual_total),
        utilisation=analytics.percentage(actual_total, estimated_total),
        reconciled_total=rollup.reconciled_total,
        unreconciled_total=money(actual_total - rollup.reconciled_total),
        planned_days=to_decimal(planned_days),
        elapsed_days=elapsed,
        days_with_cost=rollup.days_with_cost,
        first_cost_date=rollup.first_cost_date,
        last_cost_date=rollup.last_cost_date,
        forecast_at_completion=projection.forecast_at_completion,
        forecast_variance=projection.variance,
    )


def build_well_analytics(
    db: Session,
    well: Well,
    *,
    include_draft: bool = True,
    from_date: date | None = None,
    to_date: date | None = None,
) -> WellAnalyticsOut:
    """The Cost Analytics detail of one well."""

    afes = list_well_afes(db, well)
    entries = list_entries(
        db,
        well_id=well.id,
        from_date=from_date,
        to_date=to_date,
        include_draft=include_draft,
    )
    scope = build_well_scope(well)
    rollup = rollup_actuals(entries, {well.id: scope})
    planned_days = scope.total_days
    summary = build_summary(well, afes, rollup, planned_days)
    estimated = afe_totals(afes)
    estimated_total = money(sum(estimated.values(), Decimal("0")))

    comparisons = analytics.compare_groups(estimated, rollup.groups, rollup.reconciled)
    projection = analytics.forecast_completion(
        actual_to_date=rollup.total,
        estimated_total=estimated_total,
        planned_days=planned_days,
        elapsed_days=Decimal(rollup.days_with_cost),
    )

    estimated_sections = afe_section_totals(afes)
    depth = analytics.build_depth_cost_series(
        [
            analytics.DepthSection(
                section_id=section.section_id,
                section_label=section.label,
                from_depth=section.from_depth,
                to_depth=section.to_depth,
                planned_days=section.total_days,
            )
            for section in scope.sections
        ],
        estimated_sections,
        rollup.by_section,
        unattributed_actual=rollup.unattributed_section_amount,
    )

    lines = rollup.lines
    dimensions: dict[str, list[dict[str, Any]]] = {}
    for dimension in (
        "section",
        "phase",
        "activity",
        "sub_activity",
        "service",
        "charge_category",
        "consumable_category",
        "tangible",
    ):
        estimated_by_key = (
            {str(section_id): amount for section_id, amount in estimated_sections.items()}
            if dimension == "section"
            else None
        )
        dimensions[dimension] = [
            {
                "key": row.key,
                "label": row.label,
                "services": row.services,
                "consumables": row.consumables,
                "tangibles": row.tangibles,
                "total": row.total,
                "estimated": row.estimated,
                "balance": row.balance,
            }
            for row in build_report_rows(lines, dimension, estimated_by_key)
        ]

    daily_trend: list[dict[str, Any]] = []
    running = Decimal("0")
    for day, amount in sorted(rollup.by_date.items()):
        running = money(running + to_decimal(amount))
        daily_trend.append(
            {"cost_date": day.isoformat(), "amount": money(amount), "cumulative": running}
        )

    warnings: list[str] = []
    if not afes:
        warnings.append("This well has no AFE yet — create one in AFE Management to compare against.")
    if not entries:
        warnings.append("No daily cost entries recorded for this well yet.")
    if rollup.unattributed_section_amount:
        warnings.append(
            "Some actual cost has no section scope (tangibles are well-wide), so it is not "
            "attributed to a hole section."
        )
    if rollup.unreconciled_amount:
        warnings.append(
            f"{money(rollup.unreconciled_amount)} of the actual cost is not reconciled yet — "
            "reconciliation runs between the daily entries and this comparison."
        )
    warnings.extend(depth.notes)

    return WellAnalyticsOut(
        well=summary,
        afe_id=afes[-1].id if afes else None,
        afes=[
            {
                "id": afe.id,
                "afe_code": afe.afe_code,
                "afe_name": afe.afe_name,
                "afe_type": afe.afe_type,
                "status": afe.status,
                "estimated_total": compile_estimate(afe).total,
            }
            for afe in afes
        ],
        comparisons=[
            GroupComparisonOut(
                group=row.group,
                estimated=row.estimated,
                actual=row.actual,
                reconciled=row.reconciled,
                unreconciled=row.unreconciled,
                balance=row.balance,
                utilisation=row.utilisation,
            )
            for row in comparisons
        ],
        forecast=CostForecastOut(
            actual_to_date=projection.actual_to_date,
            estimated_total=projection.estimated_total,
            planned_days=projection.planned_days,
            elapsed_days=projection.elapsed_days,
            remaining_days=projection.remaining_days,
            burn_rate_per_day=projection.burn_rate_per_day,
            forecast_at_completion=projection.forecast_at_completion,
            variance=projection.variance,
            variance_pct=projection.variance_pct,
            balance_at_completion=projection.balance_at_completion,
            basis=projection.basis,
        ),
        depth_series=[
            DepthCostPointOut(
                depth=point.depth,
                section_id=point.section_id,
                section_label=point.section_label,
                estimated_cumulative=point.estimated_cumulative,
                actual_cumulative=point.actual_cumulative,
                estimated_section=point.estimated_section,
                actual_section=point.actual_section,
                variance=point.variance,
            )
            for point in depth.points
        ],
        depth_notes=list(depth.notes),
        unattributed_actual=money(depth.unattributed_actual),
        dimensions=dimensions,
        daily_trend=daily_trend,
        warnings=list(dict.fromkeys(warnings)),
    )


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _report_entries(
    db: Session,
    *,
    rig_id: int | None,
    well_id: int | None,
    from_date: date | None,
    to_date: date | None,
    include_draft: bool,
) -> list[DailyCostEntry]:
    stmt = select(DailyCostEntry).where(DailyCostEntry.is_deleted == False)
    if well_id is not None:
        stmt = stmt.where(DailyCostEntry.well_id == well_id)
    if rig_id is not None:
        stmt = stmt.where(DailyCostEntry.rig_id == rig_id)
    if from_date is not None:
        stmt = stmt.where(DailyCostEntry.cost_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(DailyCostEntry.cost_date <= to_date)
    if not include_draft:
        stmt = stmt.where(DailyCostEntry.status != "draft")
    return list(db.scalars(stmt.order_by(DailyCostEntry.cost_date, DailyCostEntry.id)).all())


def build_report(
    db: Session,
    dimension: str,
    *,
    rig_id: int | None = None,
    well_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
) -> ReportOut:
    """Build one drill-through report across the selected wells and dates."""

    if dimension not in DIMENSION_TITLES:
        raise ValueError(f"Unknown report dimension '{dimension}'")

    entries = _report_entries(
        db,
        rig_id=rig_id,
        well_id=well_id,
        from_date=from_date,
        to_date=to_date,
        include_draft=include_draft,
    )
    lines = flatten_entries(entries, scopes_for(entries))

    estimated_by_key: dict[str, Decimal] | None = None
    estimated_total = Decimal("0")
    if dimension == "section" or dimension == "well":
        if well_id is not None:
            well = db.get(Well, well_id)
            if well is not None and not well.is_deleted:
                afes = list_well_afes(db, well)
                estimated_by_key = {
                    str(section_id): amount for section_id, amount in afe_section_totals(afes).items()
                }
                estimated_total = money(sum(afe_totals(afes).values(), Decimal("0")))
                if dimension == "well":
                    estimated_by_key = {"well": estimated_total}
    elif well_id is not None:
        well = db.get(Well, well_id)
        if well is not None and not well.is_deleted:
            estimated_total = money(sum(afe_totals(list_well_afes(db, well)).values(), Decimal("0")))

    rows = build_report_rows(lines, dimension, estimated_by_key)
    totals = {
        "services": money(sum((row.services for row in rows), Decimal("0"))),
        "consumables": money(sum((row.consumables for row in rows), Decimal("0"))),
        "tangibles": money(sum((row.tangibles for row in rows), Decimal("0"))),
        "total": money(sum((row.total for row in rows), Decimal("0"))),
        "estimated": estimated_total,
    }
    totals["balance"] = money(estimated_total - totals["total"]) if estimated_total else Decimal("0")

    return ReportOut(
        dimension=dimension,
        title=DIMENSION_TITLES[dimension],
        filters={
            "rig_id": rig_id,
            "well_id": well_id,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "include_draft": include_draft,
        },
        rows=rows,
        totals=totals,
        generated_at=datetime.now(UTC),
    )


def build_report_lines(
    db: Session,
    dimension: str,
    key: str | None = None,
    *,
    rig_id: int | None = None,
    well_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
) -> list[dict[str, Any]]:
    """The detail rows behind one report row — the drill-through itself."""

    if dimension not in DIMENSION_TITLES:
        raise ValueError(f"Unknown report dimension '{dimension}'")
    entries = _report_entries(
        db,
        rig_id=rig_id,
        well_id=well_id,
        from_date=from_date,
        to_date=to_date,
        include_draft=include_draft,
    )
    detail: list[dict[str, Any]] = []
    for line in flatten_entries(entries, scopes_for(entries)):
        line_key, _ = _dimension_key(line, dimension)
        if key is not None and line_key != key:
            continue
        detail.append(
            {
                "cost_date": line["cost_date"].isoformat(),
                "daily_cost_code": line["daily_cost_code"],
                "well": line["well_label"],
                "cost_group": line["group"],
                "category": line["category"],
                "code": line["code"],
                "name": line["name"],
                "section": line["section_label"] or UNASSIGNED_LABEL,
                "phase": line["phase_label"] or "",
                "activity": line["activity"] or "",
                "sub_activity": line["sub_activity"] or "",
                "quantity": str(line["quantity"]),
                "unit": line["unit"],
                "rate": str(line["rate"]),
                "amount": str(line["amount"]),
                "remarks": line["remarks"],
                "status": line["status"],
            }
        )
    return detail


REPORT_LINE_HEADERS = [
    "cost_date",
    "daily_cost_code",
    "well",
    "cost_group",
    "category",
    "code",
    "name",
    "section",
    "phase",
    "activity",
    "sub_activity",
    "quantity",
    "unit",
    "rate",
    "amount",
    "remarks",
    "status",
]

REPORT_EXPORT_HEADERS = [
    "key",
    "label",
    "services",
    "consumables",
    "tangibles",
    "total",
    "estimated",
    "balance",
]

ANALYTICS_EXPORT_HEADERS = [
    "well_code",
    "well_name",
    "rig_code",
    "rig_name",
    "afe_count",
    "afe_estimated",
    "actual_cost",
    "balance",
    "utilisation_pct",
    "reconciled",
    "unreconciled",
    "planned_days",
    "days_with_cost",
    "first_cost_date",
    "last_cost_date",
    "forecast_at_completion",
    "forecast_variance",
]
