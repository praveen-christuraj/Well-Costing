"""Cost Analytics + Reports API routes.

Both pages read from the two places the money is already recorded — the **AFE**
estimates and the **daily cost** actuals — and never store anything themselves:

* **Cost Analytics** (``/cost-analytics``) compares AFE vs actual per cost
  group, shows the balance left, the reconciled / unreconciled split and the
  forecast at the end of the well, plus the Depth vs Cost curve built from the
  well configuration (depth), the AFE rollup (estimated) and the daily cost
  scope (actual).
* **Reports** (``/cost-reports``) produces the drill-throughs: by date, hole
  section, phase, well activity, well sub activity, service, charge category,
  consumable category and tangible, each with an export and the detail lines
  behind a row.

Every export is audit-logged. Reconciliation is *reported* here (how much of
the actual cost is already reconciled) and performed later by its own module.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.rig_well import Well
from app.models.user import User
from app.schemas.daily_cost import ReportOut, WellAnalyticsOut, WellAnalyticsSummaryOut
from app.services import cost_reporting
from app.services.audit import log_audit
from app.services.import_helpers import spreadsheet_response

analytics_router = APIRouter(prefix="/cost-analytics", tags=["cost-analytics"])
reports_router = APIRouter(prefix="/cost-reports", tags=["cost-reports"])

MODULE_ANALYTICS = "Cost Analytics"
MODULE_REPORTS = "Cost Reports"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _wells(db: Session, rig_id: int | None, search: str | None) -> list[Well]:
    stmt = select(Well).where(Well.is_deleted == False)
    if rig_id is not None:
        stmt = stmt.where(Well.rig_id == rig_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Well.well_code.ilike(like) | Well.well_name.ilike(like))
    return list(db.scalars(stmt.order_by(Well.well_code)).all())


def _get_well(db: Session, well_id: int) -> Well:
    well = db.get(Well, well_id)
    if not well or well.is_deleted:
        raise HTTPException(status_code=404, detail="Well not found or deleted")
    return well


def _parse_dimension(dimension: str) -> str:
    if dimension not in cost_reporting.DIMENSION_TITLES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown report dimension '{dimension}' — use one of "
                f"{', '.join(cost_reporting.REPORT_DIMENSIONS)}"
            ),
        )
    return dimension


# ---------------------------------------------------------------------------
# Cost Analytics
# ---------------------------------------------------------------------------


@analytics_router.get("/wells", response_model=list[WellAnalyticsSummaryOut])
def list_well_analytics(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    rig_id: int | None = None,
    search: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
) -> list[WellAnalyticsSummaryOut]:
    """AFE vs actual, balance and forecast for every well (the analytics table)."""

    rows: list[WellAnalyticsSummaryOut] = []
    for well in _wells(db, rig_id, search):
        analytics = cost_reporting.build_well_analytics(
            db,
            well,
            include_draft=include_draft,
            from_date=from_date,
            to_date=to_date,
        )
        rows.append(analytics.well)
    return rows


@analytics_router.get("/wells/export")
def export_well_analytics(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    rig_id: int | None = None,
    search: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    """The Cost Analytics table as XLSX/CSV."""

    summaries = list_well_analytics(
        db, current_user, rig_id, search, from_date, to_date, include_draft
    )
    rows = [
        [
            summary.well_code,
            summary.well_name,
            summary.rig_code or "",
            summary.rig_name or "",
            summary.afe_count,
            str(summary.estimated_total),
            str(summary.actual_total),
            str(summary.balance),
            "" if summary.utilisation is None else str(summary.utilisation),
            str(summary.reconciled_total),
            str(summary.unreconciled_total),
            str(summary.planned_days),
            summary.days_with_cost,
            summary.first_cost_date.isoformat() if summary.first_cost_date else "",
            summary.last_cost_date.isoformat() if summary.last_cost_date else "",
            str(summary.forecast_at_completion),
            str(summary.forecast_variance),
        ]
        for summary in summaries
    ]
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE_ANALYTICS,
        details=f"Exported cost analytics for {len(rows)} well(s) as {format}", request=request,
    )
    return spreadsheet_response(
        rows, cost_reporting.ANALYTICS_EXPORT_HEADERS, "cost_analytics", format
    )


@analytics_router.get("/well/{well_id}", response_model=WellAnalyticsOut)
def get_well_analytics(
    well_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
) -> WellAnalyticsOut:
    """The full analytics of one well: comparison, forecast, depth vs cost and
    every drill-through rollup."""

    well = _get_well(db, well_id)
    return cost_reporting.build_well_analytics(
        db, well, include_draft=include_draft, from_date=from_date, to_date=to_date
    )


@analytics_router.get("/well/{well_id}/depth-cost")
def get_depth_cost(
    well_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
) -> dict[str, Any]:
    """Just the Depth vs Cost series (the chart's own endpoint)."""

    analytics = cost_reporting.build_well_analytics(
        db, _get_well(db, well_id), include_draft=include_draft, from_date=from_date, to_date=to_date
    )
    return {
        "well_id": well_id,
        "well_code": analytics.well.well_code,
        "well_name": analytics.well.well_name,
        "depth_unit": analytics.well.depth_unit,
        "points": [point.model_dump() for point in analytics.depth_series],
        "unattributed_actual": analytics.unattributed_actual,
        "total_estimated": analytics.well.estimated_total,
        "total_actual": analytics.well.actual_total,
        "notes": analytics.depth_notes,
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@reports_router.get("/dimensions")
def list_dimensions(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[dict[str, str]]:
    """The drill-throughs the Reports page offers."""

    return [{"dimension": key, "title": title} for key, title in cost_reporting.DIMENSION_TITLES.items()]


@reports_router.get("", response_model=ReportOut)
def get_report(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dimension: str = "well",
    rig_id: int | None = None,
    well_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
) -> ReportOut:
    """One drill-through report across the selected rig / well / date range."""

    try:
        return cost_reporting.build_report(
            db,
            _parse_dimension(dimension),
            rig_id=rig_id,
            well_id=well_id,
            from_date=from_date,
            to_date=to_date,
            include_draft=include_draft,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@reports_router.get("/lines")
def get_report_lines(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    dimension: str = "well",
    key: str | None = None,
    rig_id: int | None = None,
    well_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
) -> dict[str, Any]:
    """The cost lines behind one report row — the drill-through itself."""

    try:
        rows = cost_reporting.build_report_lines(
            db,
            _parse_dimension(dimension),
            key,
            rig_id=rig_id,
            well_id=well_id,
            from_date=from_date,
            to_date=to_date,
            include_draft=include_draft,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "dimension": dimension,
        "key": key,
        "line_count": len(rows),
        "total": sum(float(row["amount"]) for row in rows),
        "lines": rows,
    }


@reports_router.get("/export")
def export_report(
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    dimension: str = "well",
    detail: bool = False,
    rig_id: int | None = None,
    well_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    include_draft: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: Request = None,
) -> Response:
    """Export a report — the rollup rows, or (``detail=true``) its cost lines."""

    resolved = _parse_dimension(dimension)
    if detail:
        rows = cost_reporting.build_report_lines(
            db,
            resolved,
            None,
            rig_id=rig_id,
            well_id=well_id,
            from_date=from_date,
            to_date=to_date,
            include_draft=include_draft,
        )
        data = [[row[header] for header in cost_reporting.REPORT_LINE_HEADERS] for row in rows]
        headers = cost_reporting.REPORT_LINE_HEADERS
        filename = f"cost_report_{resolved}_detail"
        log_audit(
            db, user=current_user, action="EXPORT", module=MODULE_REPORTS,
            details=f"Exported {len(rows)} detail line(s) of the '{resolved}' report as {format}",
            request=request,
        )
        return spreadsheet_response(data, headers, filename, format)

    report = cost_reporting.build_report(
        db,
        resolved,
        rig_id=rig_id,
        well_id=well_id,
        from_date=from_date,
        to_date=to_date,
        include_draft=include_draft,
    )
    data = [
        [row.key, row.label, str(row.services), str(row.consumables), str(row.tangibles),
         str(row.total), str(row.estimated), str(row.balance)]
        for row in report.rows
    ]
    data.append([
        "TOTAL", "", str(report.totals["services"]), str(report.totals["consumables"]),
        str(report.totals["tangibles"]), str(report.totals["total"]),
        str(report.totals["estimated"]), str(report.totals["balance"]),
    ])
    log_audit(
        db, user=current_user, action="EXPORT", module=MODULE_REPORTS,
        details=f"Exported the '{resolved}' report ({len(report.rows)} rows) as {format}",
        request=request,
    )
    return spreadsheet_response(
        data, cost_reporting.REPORT_EXPORT_HEADERS, f"cost_report_{resolved}", format
    )
