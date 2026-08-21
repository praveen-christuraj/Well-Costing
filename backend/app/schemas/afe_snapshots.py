"""Phase 7 immutable baseline AFE snapshot API contracts."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AfeSnapshotCreateRequest(BaseModel):
    version_id: UUID | None = None
    requested_reference: str | None = Field(default=None, max_length=100)


class AfeSnapshotAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    estimate_version_id: UUID
    resulting_snapshot_id: UUID | None
    requested_reference: str | None
    status: str
    message: str | None
    eligibility_snapshot: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class AfeSnapshotLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_estimate_item_id: UUID
    line_number: int
    item_code: str
    item_description: str
    item_type: str
    cost_code: str
    cost_category_code: str | None
    vendor_code: str | None
    quantity: Decimal
    unit_code: str
    rate_amount: Decimal | None
    rate_currency_code: str | None
    base_cost: Decimal
    contingency_cost: Decimal
    escalation_cost: Decimal
    total_cost: Decimal


class AfeSnapshotRead(BaseModel):
    id: UUID
    afe_number: str
    snapshot_type: str
    estimate_version_id: UUID
    calculation_run_id: UUID
    issue_date: date
    estimate_code: str
    estimate_title: str
    afe_code: str
    project_code: str
    well_code: str
    currency_code: str
    engine_version: str
    rule_set_version: str
    base_total: Decimal
    contingency_total: Decimal
    escalation_total: Decimal
    grand_total: Decimal
    source_snapshot: dict[str, Any]
    lines: list[AfeSnapshotLineRead]
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class EstimateAfeStatus(BaseModel):
    estimate_id: UUID
    estimate_version_id: UUID
    version_number: int
    afe_status: str
    baseline_snapshot: AfeSnapshotRead | None
    creation_attempts: list[AfeSnapshotAttemptRead]
    pending_requirements: list[str]
