"""Pydantic schemas for Master Data modules."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


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


class UOMOut(UOMBase):
    id: int
    is_deleted: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

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


class CurrencyOut(CurrencyBase):
    id: int
    is_deleted: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

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


class PhaseOut(PhaseBase):
    id: int
    is_deleted: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

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


class ActivityOut(ActivityBase):
    id: int
    is_deleted: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

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


class HoleSectionOut(HoleSectionBase):
    id: int
    is_deleted: bool
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BulkImportResponse(BaseModel):
    imported_count: int
    error_count: int
    errors: list[str]
    success: bool
