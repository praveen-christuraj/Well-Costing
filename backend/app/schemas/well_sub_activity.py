"""Pydantic schemas for Well Sub Activities."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.master_data import BlankStr, FlagBool


class WellSubActivityIn(BaseModel):
    """Create payload — every data entry field is mandatory."""

    well_id: int = Field(..., description="Well the sub activity is scoped to")
    sub_activity_code: str = Field(..., min_length=1, max_length=50)
    sub_activity_name: str = Field(..., min_length=1, max_length=150)
    activity_id: int = Field(..., description="Main Activity from Master Data")
    responsible_party: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, description="Description / remarks (mandatory)")


class WellSubActivityUpdate(BaseModel):
    """Update payload — all fields optional; the well scope never changes."""

    sub_activity_code: str | None = Field(None, min_length=1, max_length=50)
    sub_activity_name: str | None = Field(None, min_length=1, max_length=150)
    activity_id: int | None = Field(None, description="Main Activity from Master Data")
    responsible_party: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1)


class WellSubActivityOut(BaseModel):
    id: int
    well_id: int
    sub_activity_code: BlankStr = ""
    sub_activity_name: BlankStr = ""
    activity_id: int | None = None
    responsible_party: BlankStr = ""
    description: BlankStr = ""
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Denormalised labels so the grid / prints never need extra lookups.
    well_code: str | None = None
    well_name: str | None = None
    rig_id: int | None = None
    rig_code: str | None = None
    rig_name: str | None = None
    activity_code: str | None = None
    activity_name: str | None = None
    activity_display: str | None = None

    model_config = ConfigDict(from_attributes=True)
