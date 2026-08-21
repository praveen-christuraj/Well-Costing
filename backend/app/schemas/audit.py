"""Audit log API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    entity_code: str | None
    details: str | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    updated_at: datetime
