"""Schemas for service orders, purchase orders, and master item rates.

Master rates exist for tangibles and consumables only. Services are priced per
well (see ``app.schemas.well_costing``) so that a central revision cannot move
the cost basis of a well that is already drilling.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SERVICE_ORDER_STATUSES = ("draft", "active", "expired", "cancelled")
PURCHASE_ORDER_STATUSES = ("draft", "open", "partially_received", "closed", "cancelled")


class _AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class ServiceOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_number: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    vendor_id: UUID
    currency_id: UUID | None = None
    valid_from: date
    valid_to: date | None = None
    contract_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    status: str = "draft"
    description: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def check(self) -> "ServiceOrderCreate":
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        if self.status not in SERVICE_ORDER_STATUSES:
            raise ValueError(f"status must be one of {', '.join(SERVICE_ORDER_STATUSES)}")
        return self


class ServiceOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_number: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    vendor_id: UUID | None = None
    currency_id: UUID | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    contract_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    status: str | None = None
    description: str | None = None
    is_active: bool | None = None


class ServiceOrderRead(_AuditRead):
    order_number: str
    title: str
    vendor_id: UUID
    currency_id: UUID | None
    valid_from: date
    valid_to: date | None
    contract_value: Decimal | None
    status: str
    description: str | None
    is_active: bool
    vendor_code: str | None = None
    vendor_name: str | None = None
    currency_code: str | None = None


class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_number: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    vendor_id: UUID
    currency_id: UUID | None = None
    order_date: date
    expected_delivery_date: date | None = None
    order_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    status: str = "draft"
    description: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def check(self) -> "PurchaseOrderCreate":
        if (
            self.expected_delivery_date is not None
            and self.expected_delivery_date < self.order_date
        ):
            raise ValueError("expected_delivery_date must be on or after order_date")
        if self.status not in PURCHASE_ORDER_STATUSES:
            raise ValueError(f"status must be one of {', '.join(PURCHASE_ORDER_STATUSES)}")
        return self


class PurchaseOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_number: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    vendor_id: UUID | None = None
    currency_id: UUID | None = None
    order_date: date | None = None
    expected_delivery_date: date | None = None
    order_value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    status: str | None = None
    description: str | None = None
    is_active: bool | None = None


class PurchaseOrderRead(_AuditRead):
    order_number: str
    title: str
    vendor_id: UUID
    currency_id: UUID | None
    order_date: date
    expected_delivery_date: date | None
    order_value: Decimal | None
    status: str
    description: str | None
    is_active: bool
    vendor_code: str | None = None
    vendor_name: str | None = None
    currency_code: str | None = None


class ItemPriceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID
    vendor_id: UUID | None = None
    purchase_order_id: UUID | None = None
    currency_id: UUID
    unit_id: UUID
    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    effective_from: date
    effective_to: date | None = None
    description: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def check(self) -> "ItemPriceCreate":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class ItemPriceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: UUID | None = None
    vendor_id: UUID | None = None
    purchase_order_id: UUID | None = None
    currency_id: UUID | None = None
    unit_id: UUID | None = None
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    effective_from: date | None = None
    effective_to: date | None = None
    description: str | None = None
    is_active: bool | None = None


class ItemPriceRead(_AuditRead):
    item_id: UUID
    vendor_id: UUID | None
    purchase_order_id: UUID | None
    currency_id: UUID
    unit_id: UUID
    unit_price: Decimal
    effective_from: date
    effective_to: date | None
    revision_number: int = 1
    supersedes_id: UUID | None = None
    change_reason: str | None = None
    superseded_at: datetime | None = None
    description: str | None
    is_active: bool
    item_code: str | None = None
    item_name: str | None = None
    item_type: str | None = None
    vendor_code: str | None = None
    vendor_name: str | None = None
    purchase_order_number: str | None = None
    currency_code: str | None = None
    unit_code: str | None = None


class ServiceOrderBulkCreateRequest(BaseModel):
    rows: list[ServiceOrderCreate] = Field(min_length=1, max_length=5000)


class ServiceOrderBulkUpdateRow(ServiceOrderUpdate):
    id: UUID


class ServiceOrderBulkUpdateRequest(BaseModel):
    rows: list[ServiceOrderBulkUpdateRow] = Field(min_length=1, max_length=5000)


class PurchaseOrderBulkCreateRequest(BaseModel):
    rows: list[PurchaseOrderCreate] = Field(min_length=1, max_length=5000)


class PurchaseOrderBulkUpdateRow(PurchaseOrderUpdate):
    id: UUID


class PurchaseOrderBulkUpdateRequest(BaseModel):
    rows: list[PurchaseOrderBulkUpdateRow] = Field(min_length=1, max_length=5000)


class ItemPriceBulkCreateRequest(BaseModel):
    rows: list[ItemPriceCreate] = Field(min_length=1, max_length=5000)


class ItemPriceBulkUpdateRow(ItemPriceUpdate):
    id: UUID


class ItemPriceBulkUpdateRequest(BaseModel):
    rows: list[ItemPriceBulkUpdateRow] = Field(min_length=1, max_length=5000)


class ItemPriceReviseRequest(BaseModel):
    """Supersede a master rate with the next revision.

    The superseded row is closed automatically the day before
    ``effective_from``, so the history stays gap-free and every past date still
    resolves to exactly one rate.
    """

    model_config = ConfigDict(extra="forbid")

    unit_price: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    effective_from: date
    effective_to: date | None = None
    change_reason: str = Field(min_length=1)
    vendor_id: UUID | None = None
    purchase_order_id: UUID | None = None
    currency_id: UUID | None = None
    unit_id: UUID | None = None
    description: str | None = None

    @model_validator(mode="after")
    def check(self) -> "ItemPriceReviseRequest":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError("effective_to must be on or after effective_from")
        return self


class RateRevisionRead(_AuditRead):
    """One entry in the master rate change log."""

    scope: str
    item_id: UUID
    item_price_id: UUID | None
    previous_price_id: UUID | None
    vendor_id: UUID | None
    currency_id: UUID | None
    unit_id: UUID | None
    change_type: str
    revision_number: int
    previous_amount: Decimal | None
    new_amount: Decimal | None
    effective_from: date | None
    reason: str | None
    item_code: str | None = None
    item_name: str | None = None
    item_type: str | None = None
    vendor_code: str | None = None
    currency_code: str | None = None
    unit_code: str | None = None
    delta_amount: Decimal | None = None
