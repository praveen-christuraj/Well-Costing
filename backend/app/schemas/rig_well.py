"""Pydantic schemas for Rig & Well Management."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.master_data import BlankStr, FlagBool

# ---------------------------------------------------------------------------
# Rigs
# ---------------------------------------------------------------------------


class RigBase(BaseModel):
    rig_code: str = Field(..., min_length=1, max_length=50)
    rig_name: str = Field(..., min_length=1, max_length=200)
    remarks: str | None = None


class RigCreate(RigBase):
    pass


class RigUpdate(BaseModel):
    rig_code: str | None = Field(None, min_length=1, max_length=50)
    rig_name: str | None = Field(None, min_length=1, max_length=200)
    remarks: str | None = None


class RigOut(BaseModel):
    id: int
    rig_code: BlankStr = ""
    rig_name: BlankStr = ""
    remarks: str | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    well_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class RigDropdownOut(BaseModel):
    id: int
    rig_code: str
    rig_name: str
    display_name: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Wells
# ---------------------------------------------------------------------------


class WellBase(BaseModel):
    rig_id: int = Field(..., description="Rig the well belongs to")
    well_code: str = Field(..., min_length=1, max_length=50)
    well_name: str = Field(..., min_length=1, max_length=200)
    well_location: str = Field(..., min_length=1, max_length=300)
    block: str = Field(..., min_length=1, max_length=200)
    objective: str = Field(..., min_length=1)
    remarks: str | None = None


class WellCreate(WellBase):
    pass


class WellUpdate(BaseModel):
    rig_id: int | None = None
    well_code: str | None = Field(None, min_length=1, max_length=50)
    well_name: str | None = Field(None, min_length=1, max_length=200)
    well_location: str | None = Field(None, min_length=1, max_length=300)
    block: str | None = Field(None, min_length=1, max_length=200)
    objective: str | None = None
    remarks: str | None = None


class WellOut(BaseModel):
    id: int
    rig_id: int
    well_code: BlankStr = ""
    well_name: BlankStr = ""
    well_location: BlankStr = ""
    block: BlankStr = ""
    objective: BlankStr = ""
    remarks: str | None = None
    status: BlankStr = "active"
    config_status: BlankStr = "draft"
    depth_unit: BlankStr = "m"
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    rig_code: str | None = None
    rig_name: str | None = None
    rig_display: str | None = None
    total_depth: Decimal | None = None
    total_days: Decimal | None = None
    section_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Well configuration (sections + phases)
# ---------------------------------------------------------------------------


class PhaseIn(BaseModel):
    id: int | None = None
    phase_id: int
    days: Decimal = Field(..., ge=0)
    remarks: str | None = None


class SectionIn(BaseModel):
    id: int | None = None
    section_id: int
    from_depth: Decimal = Field(..., ge=0)
    to_depth: Decimal = Field(..., ge=0)
    remarks: str | None = None
    phases: list[PhaseIn] = Field(default_factory=list)


class WellConfigurationIn(BaseModel):
    depth_unit: Literal["m", "ft"] = "m"
    sections: list[SectionIn] = Field(default_factory=list)


class PhaseOut(BaseModel):
    id: int
    phase_id: int
    phase_code: str | None = None
    phase_name: str | None = None
    days: Decimal
    remarks: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SectionOut(BaseModel):
    id: int
    section_id: int
    section_code: str | None = None
    section_name: str | None = None
    from_depth: Decimal
    to_depth: Decimal
    remarks: str | None = None
    total_days: Decimal = Decimal("0")
    phases: list[PhaseOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class WellConfigurationOut(BaseModel):
    well_id: int
    well_code: str
    well_name: str
    rig_code: str | None = None
    rig_name: str | None = None
    status: str
    config_status: str
    depth_unit: str
    total_depth: Decimal | None = None
    total_days: Decimal = Decimal("0")
    sections: list[SectionOut] = Field(default_factory=list)


class MarkWellIn(BaseModel):
    action: Literal["configure", "draft", "complete", "activate"]
    remarks: str | None = None
