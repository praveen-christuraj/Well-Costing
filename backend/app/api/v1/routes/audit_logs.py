"""Audit logs API routes."""

import csv
import io
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Response
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogOut
from app.services.audit import log_audit

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    module: str | None = None,
    action: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[AuditLog]:
    """List audit logs with optional filtering."""
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if module:
        stmt = stmt.where(AuditLog.module.ilike(f"%{module}%"))
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get("/export")
def export_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    module: str | None = None,
    action: str | None = None,
) -> Response:
    """Export audit logs as Excel or CSV."""
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if module:
        stmt = stmt.where(AuditLog.module.ilike(f"%{module}%"))
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
    logs = db.scalars(stmt).all()

    log_audit(db, user=current_user, action="EXPORT", module="Audit", details=f"Exported {len(logs)} audit logs as {format}")

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Timestamp", "User", "Action", "Module", "Entity ID", "Entity Code", "Details", "IP Address"])
        for l in logs:
            writer.writerow([l.id, l.timestamp.isoformat() if l.timestamp else "", l.user_email, l.action, l.module, l.entity_id or "", l.entity_code or "", l.details or "", l.ip_address or ""])
        content = output.getvalue()
        return Response(content=content, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit_logs.csv"})
    else:
        wb = Workbook()
        ws = wb.active
        ws.title = "Audit Logs"
        ws.append(["ID", "Timestamp", "User", "Action", "Module", "Entity ID", "Entity Code", "Details", "IP Address"])
        for l in logs:
            ws.append([l.id, l.timestamp.isoformat() if l.timestamp else "", l.user_email, l.action, l.module, l.entity_id or "", l.entity_code or "", l.details or "", l.ip_address or ""])
        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        return Response(content=bio.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=audit_logs.xlsx"})
