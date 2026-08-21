"""Global audit logging service."""

import json
import logging
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.repositories.audit import AuditRepository
from app.schemas.master_data import PageResponse
from app.schemas.audit import AuditLogRead

logger = logging.getLogger("app.audit")


class AuditService:
    def __init__(self, session: Session, actor_id: UUID | None = None, actor_email: str | None = None) -> None:
        self.session = session
        self.actor_id = actor_id
        self.actor_email = actor_email
        self.repository = AuditRepository(session)

    def log(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        entity_code: str | None = None,
        details: dict[str, Any] | str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        commit: bool = False,
    ) -> AuditLog:
        details_str: str | None = None
        if isinstance(details, dict):
            try:
                details_str = json.dumps(details, default=str)
            except Exception:
                details_str = str(details)
        elif isinstance(details, str):
            details_str = details

        # JSON logger for observability
        logger.info(
            action,
            extra={
                "actor_id": str(self.actor_id) if self.actor_id else None,
                "actor_email": self.actor_email,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id else None,
                "entity_code": entity_code,
                "details": details_str,
            },
        )

        entry = self.repository.create(
            actor_id=self.actor_id,
            actor_email=self.actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_code=entity_code,
            details=details_str,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        if commit:
            self.session.commit()
            self.session.refresh(entry)
        else:
            self.session.flush()
        return entry

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        action: str | None,
        entity_type: str | None,
        actor_id: UUID | None,
    ) -> PageResponse:
        records, total = self.repository.list(
            page=page,
            page_size=page_size,
            search=search,
            action=action,
            entity_type=entity_type,
            actor_id=actor_id,
        )
        return PageResponse(
            items=[AuditLogRead.model_validate(r) for r in records],
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )

    def get(self, log_id: UUID) -> AuditLogRead:
        from app.core.exceptions import NotFoundError

        record = self.repository.get(log_id)
        if record is None:
            raise NotFoundError("Audit log not found")
        return AuditLogRead.model_validate(record)
