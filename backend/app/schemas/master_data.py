"""Cost-library API schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MasterDataCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True
    symbol: str | None = Field(default=None, max_length=30)
    parent_id: UUID | None = None
    cost_category_id: UUID | None = None
    cost_code_id: UUID | None = None
    default_unit_id: UUID | None = None
    item_category_id: UUID | None = None
    sub_category_id: UUID | None = None
    rate_basis: str | None = Field(default=None, max_length=20)
    material_number: str | None = Field(default=None, max_length=100)
    specification: str | None = Field(default=None, max_length=255)
    manufacturer: str | None = Field(default=None, max_length=150)
    applies_to: str | None = Field(default=None, max_length=30)
    vendor_type: str | None = Field(default=None, max_length=20)
    contact_person: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)


class MasterDataUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    symbol: str | None = Field(default=None, max_length=30)
    parent_id: UUID | None = None
    cost_category_id: UUID | None = None
    cost_code_id: UUID | None = None
    default_unit_id: UUID | None = None
    item_category_id: UUID | None = None
    sub_category_id: UUID | None = None
    rate_basis: str | None = Field(default=None, max_length=20)
    material_number: str | None = Field(default=None, max_length=100)
    specification: str | None = Field(default=None, max_length=255)
    manufacturer: str | None = Field(default=None, max_length=150)
    applies_to: str | None = Field(default=None, max_length=30)
    vendor_type: str | None = Field(default=None, max_length=20)
    contact_person: str | None = Field(default=None, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    country: str | None = Field(default=None, max_length=100)


class MasterDataRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None
    symbol: str | None = None
    parent_id: UUID | None = None
    cost_category_id: UUID | None = None
    cost_code_id: UUID | None = None
    default_unit_id: UUID | None = None
    item_category_id: UUID | None = None
    sub_category_id: UUID | None = None
    rate_basis: str | None = None
    material_number: str | None = None
    specification: str | None = None
    manufacturer: str | None = None
    applies_to: str | None = None
    vendor_type: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    country: str | None = None
    item_type: str | None = None
    parent_code: str | None = None
    cost_category_code: str | None = None
    cost_code: str | None = None
    default_unit_code: str | None = None
    item_category_code: str | None = None
    item_category_name: str | None = None
    sub_category_code: str | None = None
    sub_category_name: str | None = None


class RateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID
    vendor_id: UUID
    currency_id: UUID
    unit_id: UUID
    amount: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    effective_from: date
    effective_to: date | None = None
    description: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_date_range(self) -> "RateCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class RateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID | None = None
    vendor_id: UUID | None = None
    currency_id: UUID | None = None
    unit_id: UUID | None = None
    amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    effective_from: date | None = None
    effective_to: date | None = None
    description: str | None = None
    is_active: bool | None = None


class RateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID
    vendor_id: UUID
    currency_id: UUID
    unit_id: UUID
    amount: Decimal
    effective_from: date
    effective_to: date | None
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None
    item_code: str | None = None
    item_type: str | None = None
    vendor_code: str | None = None
    currency_code: str | None = None
    unit_code: str | None = None


class BulkRowError(BaseModel):
    row_index: int
    column: str | None = None
    code: str
    message: str


class BulkValidationResult(BaseModel):
    valid: bool
    total_rows: int
    valid_rows: int
    errors: list[BulkRowError]


class BulkCreateRequest(BaseModel):
    rows: list[MasterDataCreate] = Field(min_length=1, max_length=5000)


class BulkUpdateRow(MasterDataUpdate):
    id: UUID


class BulkUpdateRequest(BaseModel):
    rows: list[BulkUpdateRow] = Field(min_length=1, max_length=5000)


class RateBulkCreateRequest(BaseModel):
    rows: list[RateCreate] = Field(min_length=1, max_length=5000)


class RateBulkUpdateRow(RateUpdate):
    id: UUID


class RateBulkUpdateRequest(BaseModel):
    rows: list[RateBulkUpdateRow] = Field(min_length=1, max_length=5000)


class PageResponse(BaseModel):
    items: list[Any]
    page: int
    page_size: int
    total: int
    pages: int
