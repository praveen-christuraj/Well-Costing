"""Pydantic schemas for the Services / Consumables / Tangibles catalogue."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.master_data import BlankStr, FlagBool

# ---------------------------------------------------------------------------
# Configurable dropdown lists
# ---------------------------------------------------------------------------


class CatalogueConfigOut(BaseModel):
    id: int
    config_type: str
    value: str
    parent_value: str | None = None
    sort_order: int = 0
    is_active: FlagBool = True
    system_seeded: FlagBool = False
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ConsumableSubcategoryOut(BaseModel):
    id: int
    subcategory_code: str
    subcategory_name: str
    sort_order: int = 0
    entry_enabled: FlagBool = True
    description: str | None = None
    is_deleted: FlagBool = False

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


class ServiceOut(BaseModel):
    id: int
    service_code: BlankStr = ""
    service_name: BlankStr = ""
    service_type: BlankStr = "Service"
    provider_type: BlankStr = ""
    vendor_id: int | None = None
    vendor_code: str | None = None
    vendor_name: str | None = None
    vendor_display: str | None = None
    description: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Mud Chemicals
# ---------------------------------------------------------------------------


class MudChemicalRateOut(BaseModel):
    id: int
    chemical_id: int | None = None
    bit_id: int | None = None
    tangible_id: int | None = None
    item_kind: str | None = None
    item_code: str | None = None
    item_name: str | None = None
    unit_rate: Decimal | None = None
    unit_rate_po: Decimal | None = None
    previous_rate: Decimal | None = None
    cost_uplift: Decimal | None = None
    final_cost: Decimal | None = None
    currency: str | None = None
    uom: str | None = None
    effective_date: date | None = None
    revision_number: int = 1
    po_number: str | None = None
    remarks: str | None = None
    is_deleted: FlagBool = False
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MudChemicalOut(BaseModel):
    id: int
    chemical_code: BlankStr = ""
    part_number: str | None = None
    chemical_name: BlankStr = ""
    uom: str | None = None
    currency: str | None = None
    current_rate: Decimal = Decimal("0")
    previous_rate: Decimal = Decimal("0")
    effective_date: date | None = None
    description: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    rates: list[MudChemicalRateOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Drill Bits
# ---------------------------------------------------------------------------


class DrillBitOut(BaseModel):
    id: int
    bit_code: BlankStr = ""
    bit_name: BlankStr = ""
    bit_type: BlankStr = ""
    model_no: BlankStr = ""
    size: BlankStr = ""
    manufacturer: BlankStr = ""
    po_number: str | None = None
    serial_number: str | None = None
    currency: str | None = None
    unit_rate_po: Decimal = Decimal("0")
    cost_uplift: Decimal = Decimal("100")
    final_cost: Decimal = Decimal("0")
    previous_final_cost: Decimal = Decimal("0")
    effective_date: date | None = None
    description: str | None = None
    remarks: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    rates: list[MudChemicalRateOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Tangibles
# ---------------------------------------------------------------------------


class TangibleOut(BaseModel):
    id: int
    tangible_code: BlankStr = ""
    tangible_scope: BlankStr = ""
    category: BlankStr = ""
    subcategory: BlankStr = ""
    manufacturer: BlankStr = ""
    po_number: str | None = None
    tangible_name: BlankStr = ""
    uom: str | None = None
    currency: str | None = None
    unit_rate_po: Decimal = Decimal("0")
    cost_uplift: Decimal = Decimal("100")
    final_cost: Decimal = Decimal("0")
    previous_final_cost: Decimal = Decimal("0")
    effective_date: date | None = None
    description: str | None = None
    remarks: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    rates: list[MudChemicalRateOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
