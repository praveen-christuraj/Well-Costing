"""Audit logging service."""

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def log_audit(
    db: Session,
    *,
    user: User | None = None,
    action: str,
    module: str,
    entity_id: str | int | None = None,
    entity_code: str | None = None,
    details: str | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Record an audit log entry for any system action."""
    user_email = user.email if user else "system"
    ip_address = None
    if request and request.client:
        ip_address = request.client.host

    audit = AuditLog(
        user_email=user_email,
        action=action.upper(),
        module=module,
        entity_id=str(entity_id) if entity_id is not None else None,
        entity_code=entity_code,
        details=details,
        ip_address=ip_address,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit
