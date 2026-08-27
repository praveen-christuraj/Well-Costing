"""Pydantic schemas for Audit Logs."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    id: int
    timestamp: datetime
    user_email: str | None
    action: str
    module: str
    entity_id: str | None
    entity_code: str | None
    details: str | None
    ip_address: str | None

    model_config = ConfigDict(from_attributes=True)
