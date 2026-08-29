"""Pydantic schemas for AFE Management (AFE + AFE Cost Estimation)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.master_data import BlankStr, FlagBool
from app.schemas.rig_well import WellConfigurationOut

AfeType = Literal["Drilling", "Completion"]
AfeStatus = Literal["draft", "submitted", "approved"]
ChargingBasis = Literal["Daily Rate", "Per Service Rate", "Per Section Rate"]
QuantityUnit = Literal["days", "hours"]


# ---------------------------------------------------------------------------
# AFE
# ---------------------------------------------------------------------------


class AfeIn(BaseModel):
    """Create / update payload for an AFE header."""

    afe_code: str = Field(..., min_length=1, max_length=50)
    afe_name: str = Field(..., min_length=1, max_length=200)
    afe_type: AfeType = "Drilling"
    rig_id: int = Field(..., description="Rig the AFE belongs to")
    well_id: int = Field(..., description="Well the AFE is scoped to")
    remarks: str | None = None


class AfeUpdate(BaseModel):
    afe_code: str | None = Field(None, min_length=1, max_length=50)
    afe_name: str | None = Field(None, min_length=1, max_length=200)
    afe_type: AfeType | None = None
    rig_id: int | None = None
    well_id: int | None = None
    remarks: str | None = None


class AfeOut(BaseModel):
    id: int
    afe_code: BlankStr = ""
    afe_name: BlankStr = ""
    afe_type: BlankStr = "Drilling"
    rig_id: int
    well_id: int
    remarks: str | None = None
    status: BlankStr = "draft"
    status_remarks: str | None = None
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    rig_code: str | None = None
    rig_name: str | None = None
    rig_display: str | None = None
    well_code: str | None = None
    well_name: str | None = None
    well_display: str | None = None
    service_count: int = 0
    consumable_count: int = 0
    tangible_count: int = 0
    estimated_total: Decimal = Decimal("0")

    model_config = ConfigDict(from_attributes=True)


class AfeDropdownOut(BaseModel):
    id: int
    afe_code: str
    afe_name: str
    display_name: str

    model_config = ConfigDict(from_attributes=True)


class AfeStatusIn(BaseModel):
    """Status change — the only place an AFE leaves ``draft``."""

    action: Literal["submit", "approve", "reopen"]
    remarks: str | None = None


# ---------------------------------------------------------------------------
# Cost estimation — inputs
# ---------------------------------------------------------------------------


class ServiceRateIn(BaseModel):
    category: str
    unit_rate: Decimal = Decimal("0")


class ServiceChargeLineIn(BaseModel):
    category: str
    quantity: Decimal = Field(Decimal("0"), ge=0)
    quantity_unit: QuantityUnit = "days"


class ServiceSectionRateIn(BaseModel):
    section_id: int
    phase_id: int | None = None
    amount: Decimal = Decimal("0")


class ServiceLineIn(BaseModel):
    service_id: int
    charging_basis: ChargingBasis = "Daily Rate"
    section_id: int | None = None
    phase_id: int | None = None
    per_service_amount: Decimal = Decimal("0")
    effective_date: date | None = None
    remarks: str | None = None
    rates: list[ServiceRateIn] = Field(default_factory=list)
    charge_lines: list[ServiceChargeLineIn] = Field(default_factory=list)
    section_rates: list[ServiceSectionRateIn] = Field(default_factory=list)


class ConsumableLineIn(BaseModel):
    item_kind: Literal["mud_chemical", "drill_bit", "cement_additive", "fuel"] = "mud_chemical"
    item_id: int | None = None
    item_code: str | None = None
    item_name: str | None = None
    quantity: Decimal = Field(Decimal("1"), ge=0)
    captured_rate: Decimal = Decimal("0")
    override_rate: Decimal | None = Field(None, ge=0)
    uom: str | None = None
    currency: str | None = None
    section_id: int | None = None
    phase_id: int | None = None
    remarks: str | None = None


class TangibleLineIn(BaseModel):
    tangible_id: int
    quantity: Decimal = Field(Decimal("1"), ge=0)
    captured_rate: Decimal = Decimal("0")
    override_rate: Decimal | None = Field(None, ge=0)
    uom: str | None = None
    currency: str | None = None
    remarks: str | None = None


class EstimateIn(BaseModel):
    """The whole estimate of one AFE, saved atomically."""

    services: list[ServiceLineIn] = Field(default_factory=list)
    consumables: list[ConsumableLineIn] = Field(default_factory=list)
    tangibles: list[TangibleLineIn] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cost estimation — computed output
# ---------------------------------------------------------------------------


class CostComponentOut(BaseModel):
    category: str
    description: str
    quantity: Decimal | None = None
    rate: Decimal | None = None
    unit: str | None = None
    amount: Decimal
    section_label: str | None = None
    phase_label: str | None = None


class LineEstimateOut(BaseModel):
    amount: Decimal
    components: list[CostComponentOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class GroupSummaryOut(BaseModel):
    group: str
    amount: Decimal
    line_count: int


class SectionRollupOut(BaseModel):
    section_id: int | None = None
    section_label: str
    planned_days: Decimal
    amount: Decimal


class ServiceLineOut(BaseModel):
    id: int
    service_id: int
    service_code: str | None = None
    service_name: str | None = None
    provider_type: str | None = None
    charging_basis: str
    section_id: int | None = None
    phase_id: int | None = None
    per_service_amount: Decimal = Decimal("0")
    effective_date: date | None = None
    remarks: str | None = None
    rates: list[ServiceRateIn] = Field(default_factory=list)
    charge_lines: list[ServiceChargeLineIn] = Field(default_factory=list)
    section_rates: list[ServiceSectionRateIn] = Field(default_factory=list)
    estimate: LineEstimateOut


class ConsumableLineOut(BaseModel):
    id: int
    item_kind: str
    item_id: int
    item_code: str
    item_name: str
    quantity: Decimal
    captured_rate: Decimal
    override_rate: Decimal | None = None
    uom: str | None = None
    currency: str | None = None
    section_id: int | None = None
    phase_id: int | None = None
    remarks: str | None = None
    estimate: LineEstimateOut


class TangibleLineOut(BaseModel):
    id: int
    tangible_id: int
    tangible_code: str | None = None
    tangible_name: str | None = None
    quantity: Decimal
    captured_rate: Decimal
    override_rate: Decimal | None = None
    uom: str | None = None
    currency: str | None = None
    remarks: str | None = None
    estimate: LineEstimateOut


class AfeEstimateOut(BaseModel):
    """Everything the AFE Cost Estimation tab (and its print sheet) needs."""

    afe: AfeOut
    well_configuration: WellConfigurationOut | None = None
    services: list[ServiceLineOut] = Field(default_factory=list)
    consumables: list[ConsumableLineOut] = Field(default_factory=list)
    tangibles: list[TangibleLineOut] = Field(default_factory=list)
    summary: list[GroupSummaryOut] = Field(default_factory=list)
    by_section: list[SectionRollupOut] = Field(default_factory=list)
    grand_total: Decimal = Decimal("0")
    warnings: list[str] = Field(default_factory=list)
