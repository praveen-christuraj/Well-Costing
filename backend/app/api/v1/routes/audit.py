"""Audit log routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.audit import AuditLogRead
from app.schemas.master_data import PageResponse
from app.services.audit import AuditService

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=PageResponse)
def list_audit_logs(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    search: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    actor_id: UUID | None = None,
) -> PageResponse:
    _ = request  # for future IP/user-agent logging if needed
    return AuditService(session, current_user.id, current_user.email).list_page(
        page=page,
        page_size=page_size,
        search=search,
        action=action,
        entity_type=entity_type,
        actor_id=actor_id,
    )


@router.get("/export")
def export_audit_logs(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    actor_id: UUID | None = None,
) -> Response:
    content = AuditService(session, current_user.id, current_user.email).export_workbook(
        search=search,
        action=action,
        entity_type=entity_type,
        actor_id=actor_id,
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="audit-log.xlsx"'},
    )


@router.get("/{log_id}", response_model=AuditLogRead)
def get_audit_log(
    log_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> AuditLogRead:
    return AuditService(session, current_user.id, current_user.email).get(log_id)
