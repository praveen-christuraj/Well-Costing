"""Audit logging service."""

import logging

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger("app")


def _client_ip(request: Request | None) -> str | None:
    """Best-effort client address, honouring the first X-Forwarded-For hop."""

    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.client:
        return request.client.host
    return None


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
) -> AuditLog | None:
    """Record an audit log entry for any system action.

    Failures are swallowed so a logging problem never turns a successful
    business write (or a sign-in) into a 500 for the caller. Call after the
    business transaction has been committed.
    """

    user_email = user.email if user else "system"
    try:
        audit = AuditLog(
            user_email=user_email,
            action=action.upper(),
            module=module,
            entity_id=str(entity_id) if entity_id is not None else None,
            entity_code=entity_code,
            details=details,
            ip_address=_client_ip(request),
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
    except Exception:
        logger.exception("Failed to persist audit log for %s %s", action, module)
        try:
            db.rollback()
        except Exception:
            logger.exception("Failed to roll back after audit log error")
        return None
