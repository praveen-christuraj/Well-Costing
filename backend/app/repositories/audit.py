"""Repository for global audit logs."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        actor_id: UUID | None,
        actor_email: str | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None,
        entity_code: str | None = None,
        details: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_code=entity_code,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def list(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        action: str | None,
        entity_type: str | None,
        actor_id: UUID | None,
    ) -> tuple[Sequence[AuditLog], int]:
        statement = select(AuditLog)
        count = select(func.count()).select_from(AuditLog)
        clauses = []
        if search:
            pattern = f"%{search}%"
            clauses.append(
                or_(
                    AuditLog.action.ilike(pattern),
                    AuditLog.entity_type.ilike(pattern),
                    AuditLog.entity_code.ilike(pattern),
                    AuditLog.actor_email.ilike(pattern),
                    AuditLog.details.ilike(pattern),
                )
            )
        if action:
            clauses.append(AuditLog.action == action)
        if entity_type:
            clauses.append(AuditLog.entity_type == entity_type)
        if actor_id:
            clauses.append(AuditLog.actor_id == actor_id)
        if clauses:
            statement = statement.where(*clauses)
            count = count.where(*clauses)
        statement = statement.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        return self.session.scalars(statement).all(), int(self.session.scalar(count) or 0)

    def get(self, log_id: UUID) -> AuditLog | None:
        return self.session.get(AuditLog, log_id)
