"""Pydantic schemas for Master Data modules."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _blank_if_none(value: object) -> object:
    """Coerce NULL legacy columns to empty strings so list endpoints never 500."""

    return "" if value is None else value


def _false_if_none(value: object) -> object:
    return False if value is None else value


BlankStr = Annotated[str, BeforeValidator(_blank_if_none)]
FlagBool = Annotated[bool, BeforeValidator(_false_if_none)]


class UOMBase(BaseModel):
    unit_code: str = Field(..., min_length=1, max_length=50)
    unit_name: str = Field(..., min_length=1, max_length=150)
    unit_symbol: str = Field(..., min_length=1, max_length=50)
    description: str | None = None


class UOMCreate(UOMBase):
    pass


class UOMUpdate(BaseModel):
    unit_code: str | None = Field(None, min_length=1, max_length=50)
    unit_name: str | None = Field(None, min_length=1, max_length=150)
    unit_symbol: str | None = Field(None, min_length=1, max_length=50)
    description: str | None = None


class UOMOut(BaseModel):
    id: int
    unit_code: BlankStr = ""
    unit_name: BlankStr = ""
    unit_symbol: BlankStr = ""
    description: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CurrencyBase(BaseModel):
    currency_code: str = Field(..., min_length=1, max_length=10)
    currency_name: str = Field(..., min_length=1, max_length=100)
    currency_symbol: str = Field(..., min_length=1, max_length=20)
    description: str | None = None


class CurrencyCreate(CurrencyBase):
    pass


class CurrencyUpdate(BaseModel):
    currency_code: str | None = Field(None, min_length=1, max_length=10)
    currency_name: str | None = Field(None, min_length=1, max_length=100)
    currency_symbol: str | None = Field(None, min_length=1, max_length=20)
    description: str | None = None


class CurrencyOut(BaseModel):
    id: int
    currency_code: BlankStr = ""
    currency_name: BlankStr = ""
    currency_symbol: BlankStr = ""
    description: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PhaseBase(BaseModel):
    phase_code: str = Field(..., min_length=1, max_length=50)
    phase_name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None


class PhaseCreate(PhaseBase):
    pass


class PhaseUpdate(BaseModel):
    phase_code: str | None = Field(None, min_length=1, max_length=50)
    phase_name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None


class PhaseOut(BaseModel):
    id: int
    phase_code: BlankStr = ""
    phase_name: BlankStr = ""
    description: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ActivityBase(BaseModel):
    activity_code: str = Field(..., min_length=1, max_length=50)
    activity_name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    activity_code: str | None = Field(None, min_length=1, max_length=50)
    activity_name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None


class ActivityOut(BaseModel):
    id: int
    activity_code: BlankStr = ""
    activity_name: BlankStr = ""
    description: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class HoleSectionBase(BaseModel):
    section_code: str = Field(..., min_length=1, max_length=50)
    section_name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None


class HoleSectionCreate(HoleSectionBase):
    pass


class HoleSectionUpdate(BaseModel):
    section_code: str | None = Field(None, min_length=1, max_length=50)
    section_name: str | None = Field(None, min_length=1, max_length=150)
    description: str | None = None


class HoleSectionOut(BaseModel):
    id: int
    section_code: BlankStr = ""
    section_name: BlankStr = ""
    description: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VendorSupplierBase(BaseModel):
    vendor_code: str = Field(..., min_length=1, max_length=50, description="Vendor/Supplier Code")
    vendor_name: str = Field(..., min_length=1, max_length=200, description="Vendor/Supplier Name")
    contact: str | None = Field(None, max_length=500, description="Contact info")
    description: str | None = None


class VendorSupplierCreate(VendorSupplierBase):
    pass


class VendorSupplierUpdate(BaseModel):
    vendor_code: str | None = Field(None, min_length=1, max_length=50)
    vendor_name: str | None = Field(None, min_length=1, max_length=200)
    contact: str | None = Field(None, max_length=500)
    description: str | None = None


class VendorSupplierOut(BaseModel):
    id: int
    vendor_code: BlankStr = ""
    vendor_name: BlankStr = ""
    contact: str | None = None
    description: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class VendorSupplierDropdownOut(BaseModel):
    id: int
    vendor_code: str
    vendor_name: str
    display_name: str  # code & name combined

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderBase(BaseModel):
    po_type: Literal["PO", "SO", "Callout", "Others"] = Field(..., description="Type")
    vendor_id: int = Field(..., description="Vendor/Supplier ID")
    po_so_number: str = Field(..., min_length=1, max_length=100, description="PO/SO Number")
    effective_date: date | None = None
    value: float | None = Field(None, ge=0, description="Currency value")
    is_amendment: bool = Field(False, description="Amendment checkbox")
    amendment_number: int | None = Field(None, ge=1, le=200, description="Amendment number 1-200")
    remarks: str | None = None


class PurchaseOrderCreate(PurchaseOrderBase):
    pass


class PurchaseOrderUpdate(BaseModel):
    po_type: Literal["PO", "SO", "Callout", "Others"] | None = None
    vendor_id: int | None = None
    po_so_number: str | None = Field(None, min_length=1, max_length=100)
    effective_date: date | None = None
    value: float | None = Field(None, ge=0)
    is_amendment: bool | None = None
    amendment_number: int | None = Field(None, ge=1, le=200)
    remarks: str | None = None


class PurchaseOrderOut(BaseModel):
    id: int
    po_type: BlankStr = ""
    vendor_id: int
    po_so_number: BlankStr = ""
    effective_date: date | None = None
    value: float | None = None
    is_amendment: FlagBool = False
    amendment_number: int | None = None
    remarks: str | None = None
    attachment_path: str | None = None
    attachment_original_name: str | None = None
    attachment_mime_type: str | None = None
    attachment_size: int | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    vendor_code: str | None = None
    vendor_name: str | None = None
    vendor_display: str | None = None

    model_config = ConfigDict(from_attributes=True)


class BulkImportResponse(BaseModel):
    imported_count: int
    error_count: int
    errors: list[str]
    success: bool


class BulkAttachmentUploadResponse(BaseModel):
    uploaded_count: int
    error_count: int
    errors: list[str]
    success: bool
