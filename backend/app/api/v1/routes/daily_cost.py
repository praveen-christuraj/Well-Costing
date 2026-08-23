"""Daily cost operational routes: services hours, chemical usage, and AFE analytics."""

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.daily_cost import (
    DailyCostAnalyticsRead,
    DailyCostComparisonRead,
    DailyCostEntryCreate,
    DailyCostEntryRead,
)
from app.services.daily_cost import DailyCostService

router = APIRouter(prefix="/wells/{well_id}/daily-cost", tags=["Daily Cost"])
DbSession = Annotated[Session, Depends(get_db)]

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("", response_model=list[DailyCostEntryRead])
def list_daily_cost_entries(
    well_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> list[DailyCostEntryRead]:
    return DailyCostService(session, current_user.id).list_entries(well_id)


@router.get("/entry", response_model=DailyCostEntryRead | None)
def get_daily_cost_entry(
    well_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    entry_date: Annotated[date, Query()],
) -> DailyCostEntryRead | None:
    return DailyCostService(session, current_user.id).get_entry(well_id, entry_date)


@router.post("", response_model=DailyCostEntryRead, status_code=201)
def save_daily_cost_entry(
    well_id: UUID,
    payload: DailyCostEntryCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> DailyCostEntryRead:
    return DailyCostService(session, current_user.id).save_entry(well_id, payload)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_daily_cost_entry(
    well_id: UUID,
    entry_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    DailyCostService(session, current_user.id).delete_entry(well_id, entry_id)
    return Response(status_code=204)


@router.post("/{entry_id}/recover", response_model=DailyCostEntryRead)
def recover_daily_cost_entry(
    well_id: UUID,
    entry_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> DailyCostEntryRead:
    """Recover a deleted daily cost entry."""
    return DailyCostService(session, current_user.id).recover_entry(well_id, entry_id)


@router.get("/analytics", response_model=DailyCostAnalyticsRead)
def get_daily_cost_analytics(
    well_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> DailyCostAnalyticsRead:
    return DailyCostService(session, current_user.id).get_analytics(well_id)


@router.get("/reference-rates")
def get_daily_cost_reference_rates(
    well_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> dict[str, Any]:
    """Unit rates for daily entry, sourced from the AFE Cost Estimates only."""
    return DailyCostService(session, current_user.id).get_reference_rates(well_id)


@router.get("/comparison", response_model=DailyCostComparisonRead)
def get_daily_cost_comparison(
    well_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> DailyCostComparisonRead:
    """Planned vs actual comparison by section, activity, phase, date, week, and month."""
    return DailyCostService(session, current_user.id).get_comparison(well_id)


@router.get("/comparison/export")
def export_daily_cost_comparison(
    well_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    content = DailyCostService(session, current_user.id).export_comparison_workbook(well_id)
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="cost-comparison.xlsx"'},
    )


@router.get("/report")
def export_daily_cost_day_report(
    well_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    entry_date: Annotated[date, Query()],
) -> Response:
    """Printable daily cost report for one operational day."""
    content = DailyCostService(session, current_user.id).export_day_report(well_id, entry_date)
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="daily-cost-report-{entry_date}.xlsx"'
        },
    )


@router.get("/export")
def export_daily_cost_register(
    well_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> Response:
    """The full daily cost register for the well."""
    content = DailyCostService(session, current_user.id).export_entries_workbook(well_id)
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="daily-cost-register.xlsx"'},
    )
