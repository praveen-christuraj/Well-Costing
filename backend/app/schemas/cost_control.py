"""Phase 8 bulk staging, posting audit, and immutable cost-state schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

CostStateValue = Literal["field_estimate", "commitment", "accrual", "actual", "forecast"]
CorrectionKindValue = Literal["original", "reversal", "adjustment"]


class CostControlLineInput(BaseModel):
    transaction_date: date
    source_document_type: str = Field(min_length=1, max_length=50)
    source_document_reference: str = Field(min_length=1, max_length=150)
    external_transaction_id: str | None = Field(default=None, max_length=150)
    cost_code: str = Field(min_length=1, max_length=100)
    vendor_code: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal | None = Field(default=None, max_digits=18, decimal_places=4)
    unit_code: str | None = Field(default=None, max_length=50)
    currency_code: str = Field(min_length=3, max_length=3)
    amount: Decimal = Field(max_digits=18, decimal_places=4)
    correction_kind: CorrectionKindValue = "original"
    reverses_transaction_id: UUID | None = None

    @model_validator(mode="after")
    def validate_reversal_lineage(self) -> "CostControlLineInput":
        if self.correction_kind == "reversal" and self.reverses_transaction_id is None:
            raise ValueError("reversal rows require reverses_transaction_id")
        if self.correction_kind == "original" and self.reverses_transaction_id is not None:
            raise ValueError("original rows cannot reference a reversed transaction")
        return self


class CostControlBatchCreate(BaseModel):
    estimate_version_id: UUID
    cost_state: CostStateValue
    rows: list[CostControlLineInput] = Field(min_length=1, max_length=10_000)


class CostControlStagedLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    row_number: int
    transaction_date: date
    source_document_type: str
    source_document_reference: str
    external_transaction_id: str | None
    cost_code: str
    vendor_code: str | None
    description: str
    quantity: Decimal | None
    unit_code: str | None
    currency_code: str
    amount: Decimal
    correction_kind: str
    reverses_transaction_id: UUID | None
    raw_snapshot: dict[str, Any]


class CostControlBatchErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    row_number: int
    column_name: str | None
    error_code: str
    message: str
    raw_value: Any | None


class CostControlPostAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    message: str | None
    policy_snapshot: dict[str, Any]
    created_at: datetime
    created_by: UUID | None


class CostControlBatchRead(BaseModel):
    id: UUID
    estimate_version_id: UUID
    afe_snapshot_id: UUID | None
    cost_state: str
    source_type: str
    filename: str | None
    mapping_profile: str
    mapping_version: str
    status: str
    total_rows: int
    valid_rows: int
    error_rows: int
    posted_rows: int
    staged_lines: list[CostControlStagedLineRead]
    errors: list[CostControlBatchErrorRead]
    post_attempts: list[CostControlPostAttemptRead]
    created_at: datetime
    created_by: UUID | None


class CostControlBatchPage(BaseModel):
    items: list[CostControlBatchRead]
    total: int


class CostControlImportPreview(BaseModel):
    batch: CostControlBatchRead
    detected_columns: list[str]
    applied_mapping: dict[str, str]
