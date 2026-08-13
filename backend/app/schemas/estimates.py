"""Phase 4 bulk cost-build schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EstimateGenerateRequest(BaseModel):
    requirement_id: UUID
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    currency_id: UUID


class EstimateItemRead(BaseModel):
    id: UUID
    estimate_version_id: UUID
    line_number: int
    requirement_item_id: UUID | None
    catalog_item_id: UUID
    catalog_item_code: str
    catalog_item_name: str
    item_type: str
    cost_code_id: UUID
    cost_code: str
    vendor_id: UUID | None
    vendor_code: str | None
    rate_id: UUID | None
    rate_amount: Decimal | None
    rate_currency_code: str | None
    quantity: Decimal
    unit_id: UUID
    unit_code: str
    notes: str | None
    base_cost: Decimal | None
    contingency_cost: Decimal | None
    escalation_cost: Decimal | None
    total_cost: Decimal | None
    created_at: datetime
    updated_at: datetime


class EstimateAssumptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    estimate_version_id: UUID
    cost_category_id: UUID | None
    contingency_percent: Decimal | None
    escalation_percent: Decimal | None
    notes: str | None


class EstimateVersionRead(BaseModel):
    id: UUID
    estimate_id: UUID
    version_number: int
    status: str
    notes: str | None
    base_total: Decimal | None = None
    contingency_total: Decimal | None = None
    escalation_total: Decimal | None = None
    grand_total: Decimal | None = None
    items: list[EstimateItemRead]
    assumptions: list[EstimateAssumptionRead]
    created_at: datetime
    created_by: UUID | None


class EstimateRead(BaseModel):
    id: UUID
    requirement_id: UUID
    requirement_code: str
    well_id: UUID
    well_code: str
    project_code: str
    code: str
    title: str
    currency_id: UUID
    currency_code: str
    current_version_number: int
    versions: list[EstimateVersionRead]
    created_at: datetime
    created_by: UUID | None


class EstimateItemUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    unit_id: UUID | None = None
    vendor_id: UUID | None = None
    rate_id: UUID | None = None
    notes: str | None = None


class BulkEstimateItemUpdateRow(EstimateItemUpdate):
    id: UUID


class BulkEstimateItemUpdate(BaseModel):
    rows: list[BulkEstimateItemUpdateRow] = Field(min_length=1, max_length=10_000)


class BulkAssignRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=10_000)
    vendor_id: UUID | None = None
    rate_id: UUID | None = None


class DuplicateItemsRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=1000)


class AssumptionUpsert(BaseModel):
    cost_category_id: UUID | None = None
    contingency_percent: Decimal | None = Field(default=None, ge=0, max_digits=9, decimal_places=4)
    escalation_percent: Decimal | None = Field(default=None, ge=0, max_digits=9, decimal_places=4)
    notes: str | None = None


class DuplicateVersionRequest(BaseModel):
    notes: str | None = None
