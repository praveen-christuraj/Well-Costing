"""Reports generated from the active well-costing workflow."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.reporting import GeneratedReport, ReportFilters, ReportingContractRead
from app.services.reporting import ReportingService

router = APIRouter(prefix="/reports", tags=["reporting"])
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/contracts/v1", response_model=ReportingContractRead)
def reporting_contract_v1(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> ReportingContractRead:
    del current_user, session
    return ReportingService.contract()


@router.get("/generate", response_model=GeneratedReport)
def generate_report(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    filters: Annotated[ReportFilters, Depends()],
) -> GeneratedReport:
    return ReportingService(session, current_user).generate(filters)


@router.get("/export")
def export_report(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    filters: Annotated[ReportFilters, Depends()],
) -> Response:
    content = ReportingService(session, current_user).export(filters)
    filename = filters.report_type.replace("_", "-")
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )
