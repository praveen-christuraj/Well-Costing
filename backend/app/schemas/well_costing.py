"""API schemas for the well rate book and the out-of-AFE register."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

RateBasis = Literal["daily", "per_service", "per_section", "fixed"]
RateOrigin = Literal["well_planning", "unplanned"]
RateStatus = Literal["draft", "locked"]
UnplannedKind = Literal["service", "tangible", "other"]
UnplannedReason = Literal[
    "emergency",
    "operational_necessity",
    "scope_change",
    "afe_omission",
    "rate_revision",
    "other",
]

Money = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
OptionalMoney = Field(default=None, ge=0, max_digits=18, decimal_places=4)


class _AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


# --------------------------------------------------------------------- services
class WellServiceRateCreate(BaseModel):
    """Add a master service to a well at the rate negotiated for this well."""

    model_config = ConfigDict(extra="forbid")

    service_id: UUID
    currency_id: UUID
    unit_id: UUID
    vendor_id: UUID | None = None
    hole_section_id: UUID | None = None
    rate_basis: RateBasis = "daily"
    operating_rate: Decimal = Money
    standby_rate: Decimal = Money
    mobilisation_rate: Decimal = Money
    demobilisation_rate: Decimal = Money
    personnel_operating_rate: Decimal = Money
    personnel_standby_rate: Decimal = Money
    other_rate: Decimal = Money
    contract_reference: str | None = Field(default=None, max_length=150)
    notes: str | None = None

    @model_validator(mode="after")
    def check(self) -> "WellServiceRateCreate":
        if self.rate_basis == "per_section" and self.hole_section_id is None:
            raise ValueError("hole_section_id is required for per-section rates")
        return self


class WellServiceRateUpdate(BaseModel):
    """Revise a well service rate. A reason is required for financial changes."""

    model_config = ConfigDict(extra="forbid")

    vendor_id: UUID | None = None
    currency_id: UUID | None = None
    unit_id: UUID | None = None
    hole_section_id: UUID | None = None
    rate_basis: RateBasis | None = None
    operating_rate: Decimal | None = OptionalMoney
    standby_rate: Decimal | None = OptionalMoney
    mobilisation_rate: Decimal | None = OptionalMoney
    demobilisation_rate: Decimal | None = OptionalMoney
    personnel_operating_rate: Decimal | None = OptionalMoney
    personnel_standby_rate: Decimal | None = OptionalMoney
    other_rate: Decimal | None = OptionalMoney
    contract_reference: str | None = Field(default=None, max_length=150)
    notes: str | None = None
    is_active: bool | None = None
    change_reason: str | None = None


class WellServiceRateRead(_AuditRead):
    well_id: UUID
    service_id: UUID
    vendor_id: UUID | None
    currency_id: UUID
    unit_id: UUID
    hole_section_id: UUID | None
    rate_basis: str
    operating_rate: Decimal
    standby_rate: Decimal
    mobilisation_rate: Decimal
    demobilisation_rate: Decimal
    personnel_operating_rate: Decimal
    personnel_standby_rate: Decimal
    other_rate: Decimal
    origin: str
    status: str
    locked_at: datetime | None
    revision_number: int
    contract_reference: str | None
    notes: str | None
    is_active: bool
    service_code: str | None = None
    service_name: str | None = None
    vendor_code: str | None = None
    vendor_name: str | None = None
    currency_code: str | None = None
    unit_code: str | None = None
    hole_section_code: str | None = None


# -------------------------------------------------------------------- tangibles
class WellTangibleRateCreate(BaseModel):
    """Add a master tangible to a well, copying or overriding the master rate."""

    model_config = ConfigDict(extra="forbid")

    tangible_id: UUID
    currency_id: UUID | None = None
    unit_id: UUID | None = None
    vendor_id: UUID | None = None
    unit_rate: Decimal | None = OptionalMoney
    override_reason: str | None = None
    contract_reference: str | None = Field(default=None, max_length=150)
    notes: str | None = None


class WellTangibleRateUpdate(BaseModel):
    """Revise a well tangible rate. A reason is required for financial changes."""

    model_config = ConfigDict(extra="forbid")

    vendor_id: UUID | None = None
    currency_id: UUID | None = None
    unit_id: UUID | None = None
    unit_rate: Decimal | None = OptionalMoney
    override_reason: str | None = None
    contract_reference: str | None = Field(default=None, max_length=150)
    notes: str | None = None
    is_active: bool | None = None
    change_reason: str | None = None


class WellTangibleRateRead(_AuditRead):
    well_id: UUID
    tangible_id: UUID
    vendor_id: UUID | None
    currency_id: UUID
    unit_id: UUID
    unit_rate: Decimal
    master_price_id: UUID | None
    master_unit_rate: Decimal | None
    master_effective_from: date | None
    is_overridden: bool
    override_reason: str | None
    origin: str
    status: str
    locked_at: datetime | None
    revision_number: int
    contract_reference: str | None
    notes: str | None
    is_active: bool
    tangible_code: str | None = None
    tangible_name: str | None = None
    vendor_code: str | None = None
    vendor_name: str | None = None
    currency_code: str | None = None
    unit_code: str | None = None
    variance_to_master: Decimal | None = None


# --------------------------------------------------------------------- catalogue
class AvailableServiceRead(BaseModel):
    """A master service that can still be added to this well."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    cost_code_id: UUID | None = None
    cost_code: str | None = None
    default_unit_id: UUID | None = None
    default_unit_code: str | None = None
    in_rate_book: bool = False


class AvailableTangibleRead(AvailableServiceRead):
    """A master tangible plus the master rate that would be copied in."""

    master_price_id: UUID | None = None
    master_unit_rate: Decimal | None = None
    master_currency_id: UUID | None = None
    master_currency_code: str | None = None
    master_unit_id: UUID | None = None
    master_unit_code: str | None = None
    master_vendor_id: UUID | None = None
    master_effective_from: date | None = None


# --------------------------------------------------------------------- revisions
class WellRateRevisionRead(_AuditRead):
    well_id: UUID
    scope: str
    well_service_rate_id: UUID | None
    well_tangible_rate_id: UUID | None
    item_code: str
    item_name: str
    change_type: str
    revision_number: int
    previous_rates: dict[str, object] | None
    new_rates: dict[str, object] | None
    reason: str | None
    effective_from: date | None


class RateBookLockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: str | None = Field(default=None, max_length=150)
    reason: str | None = None


class RateBookLockResult(BaseModel):
    well_id: UUID
    locked_at: datetime
    reference: str | None
    locked_services: int
    locked_tangibles: int


# ------------------------------------------------------------- unplanned register
class WellUnplannedItemCreate(BaseModel):
    """Record a service or tangible used outside the approved AFE."""

    model_config = ConfigDict(extra="forbid")

    item_kind: UnplannedKind
    currency_id: UUID
    quantity: Decimal = Money
    unit_rate: Decimal = Money
    reason_code: UnplannedReason
    justification: str = Field(min_length=1)
    incurred_on: date
    catalog_item_id: UUID | None = None
    item_description: str | None = Field(default=None, max_length=255)
    afe_snapshot_id: UUID | None = None
    cost_code_id: UUID | None = None
    vendor_id: UUID | None = None
    unit_id: UUID | None = None
    source_document_reference: str | None = Field(default=None, max_length=150)
    reference: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def check(self) -> "WellUnplannedItemCreate":
        if self.catalog_item_id is None and not (self.item_description or "").strip():
            raise ValueError("item_description is required when the item is not in master data")
        return self


class WellUnplannedItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_kind: UnplannedKind | None = None
    catalog_item_id: UUID | None = None
    item_description: str | None = Field(default=None, max_length=255)
    afe_snapshot_id: UUID | None = None
    cost_code_id: UUID | None = None
    vendor_id: UUID | None = None
    currency_id: UUID | None = None
    unit_id: UUID | None = None
    quantity: Decimal | None = OptionalMoney
    unit_rate: Decimal | None = OptionalMoney
    reason_code: UnplannedReason | None = None
    justification: str | None = None
    incurred_on: date | None = None
    source_document_reference: str | None = Field(default=None, max_length=150)


class WellUnplannedDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_note: str | None = None
    #: Approving a catalogue-backed entry adds the rate to the well rate book so
    #: the rest of the operation reuses it. Set false to keep it as a one-off.
    add_to_rate_book: bool = True


class WellUnplannedItemRead(_AuditRead):
    well_id: UUID
    reference: str
    afe_snapshot_id: UUID | None
    item_kind: str
    catalog_item_id: UUID | None
    item_description: str
    well_service_rate_id: UUID | None
    well_tangible_rate_id: UUID | None
    cost_code_id: UUID | None
    vendor_id: UUID | None
    currency_id: UUID
    unit_id: UUID | None
    quantity: Decimal
    unit_rate: Decimal
    amount: Decimal
    reason_code: str
    justification: str
    incurred_on: date
    source_document_reference: str | None
    status: str
    submitted_at: datetime | None
    submitted_by: UUID | None
    decided_at: datetime | None
    decided_by: UUID | None
    decision_note: str | None
    is_active: bool
    catalog_item_code: str | None = None
    vendor_code: str | None = None
    currency_code: str | None = None
    unit_code: str | None = None
    cost_code: str | None = None


class WellCostExposureRead(BaseModel):
    """Approved AFE versus out-of-AFE spend for one well."""

    well_id: UUID
    well_code: str
    well_name: str
    rig_name: str | None
    well_status: str
    rates_locked_at: datetime | None
    currency_code: str | None
    afe_number: str | None
    afe_total: Decimal
    approved_unplanned_total: Decimal
    pending_unplanned_total: Decimal
    committed_total: Decimal
    variance_amount: Decimal
    variance_percent: Decimal | None
    approved_unplanned_count: int
    pending_unplanned_count: int
    rate_book_services: int
    rate_book_tangibles: int
