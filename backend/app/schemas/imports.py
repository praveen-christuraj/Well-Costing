"""Excel import/export API schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.master_data import BulkRowError


class ImportPreviewResponse(BaseModel):
    batch_id: UUID
    entity_type: str
    status: str
    mapping_profile: str
    mapping_version: str
    detected_columns: list[str]
    applied_mapping: dict[str, str]
    total_rows: int
    valid_rows: int
    error_rows: int
    errors: list[BulkRowError]
    sample: list[dict[str, Any]]


class ImportCommitRequest(BaseModel):
    batch_id: UUID


class ImportCommitResponse(BaseModel):
    batch_id: UUID
    status: str
    imported_rows: int


class ImportErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    row_number: int
    column_name: str | None
    error_code: str
    message: str
    raw_value: Any | None


class ImportBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entity_type: str
    filename: str
    file_sha256: str
    mapping_profile: str
    mapping_version: str
    status: str
    total_rows: int
    valid_rows: int
    error_rows: int
    imported_rows: int
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    errors: list[ImportErrorRead] = Field(default_factory=lambda: list[ImportErrorRead]())


class MappingOverride(BaseModel):
    source_to_target: dict[str, str] = Field(default_factory=dict)
