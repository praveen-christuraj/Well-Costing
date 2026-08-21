"""Project, well, AFE, and AFE-line API schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_active: bool = True


class ProjectUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class ProjectRead(BaseModel):
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


#: A well's lifecycle. The rate book is locked at AFE issue and stays locked for
#: the rest of these states, which is what keeps concurrently drilling rigs on
#: the rates they were planned with.
WellStatus = Literal["planning", "active", "suspended", "completed", "abandoned"]


class WellCreate(BaseModel):
    project_id: UUID
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    rig_name: str | None = Field(default=None, max_length=150)
    status: WellStatus = "planning"
    spud_date: date | None = None
    completion_date: date | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def check_dates(self) -> "WellCreate":
        if (
            self.spud_date is not None
            and self.completion_date is not None
            and self.completion_date < self.spud_date
        ):
            raise ValueError("completion_date must be on or after spud_date")
        return self


class WellUpdate(BaseModel):
    project_id: UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    rig_name: str | None = Field(default=None, max_length=150)
    status: WellStatus | None = None
    spud_date: date | None = None
    completion_date: date | None = None
    is_active: bool | None = None


class WellRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    project_code: str
    code: str
    name: str
    description: str | None
    rig_name: str | None
    status: str
    spud_date: date | None
    completion_date: date | None
    rates_locked_at: datetime | None
    rate_lock_reference: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class AfeCreate(BaseModel):
    well_id: UUID
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None


class AfeUpdate(BaseModel):
    well_id: UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class AfeLineCreate(BaseModel):
    """A planned AFE line.

    ``quantity`` is optional on a ``daily_consumption`` line: leave it out and
    the app multiplies ``daily_consumption`` by ``planned_duration_days``.
    Supply a different quantity and it is kept as an override, but only with a
    ``quantity_override_reason``.
    """

    line_number: int = Field(ge=1)
    catalog_item_id: UUID
    cost_code_id: UUID
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    unit_id: UUID
    hole_section_id: UUID | None = None
    rate_basis: str | None = Field(default=None, max_length=20)
    daily_consumption: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    quantity_override_reason: str | None = Field(default=None, max_length=500)
    planned_duration_days: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=4
    )
    planned_depth_from: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    planned_depth_to: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    depth_unit_id: UUID | None = None
    notes: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_depth(self) -> "AfeLineCreate":
        if (
            self.planned_depth_from is not None
            and self.planned_depth_to is not None
            and self.planned_depth_to < self.planned_depth_from
        ):
            raise ValueError("planned_depth_to must be on or after planned_depth_from")
        if (self.planned_depth_from is not None or self.planned_depth_to is not None) and (
            self.depth_unit_id is None
        ):
            raise ValueError("depth_unit_id is required when a planned depth is supplied")
        return self


class AfeLineUpdate(BaseModel):
    line_number: int | None = Field(default=None, ge=1)
    catalog_item_id: UUID | None = None
    cost_code_id: UUID | None = None
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    unit_id: UUID | None = None
    hole_section_id: UUID | None = None
    rate_basis: str | None = Field(default=None, max_length=20)
    daily_consumption: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    quantity_override_reason: str | None = Field(default=None, max_length=500)
    planned_duration_days: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=4
    )
    planned_depth_from: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    planned_depth_to: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    depth_unit_id: UUID | None = None
    notes: str | None = None
    is_active: bool | None = None


class AfeLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    afe_id: UUID
    line_number: int
    catalog_item_id: UUID
    catalog_item_code: str
    catalog_item_name: str
    item_type: str
    cost_code_id: UUID
    cost_code: str
    quantity: Decimal
    unit_id: UUID
    unit_code: str
    hole_section_id: UUID | None
    hole_section_code: str | None
    hole_section_name: str | None
    rate_basis: str
    daily_consumption: Decimal | None
    computed_quantity: Decimal | None
    quantity_override_reason: str | None
    quantity_source: Literal["entered", "computed", "overridden"]
    planned_duration_days: Decimal | None
    planned_depth_from: Decimal | None
    planned_depth_to: Decimal | None
    depth_unit_id: UUID | None
    depth_unit_code: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class AfeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    well_id: UUID
    well_code: str
    project_id: UUID
    project_code: str
    code: str
    title: str
    description: str | None
    status: Literal["draft", "submitted"]
    revision_number: int
    supersedes_id: UUID | None
    submitted_at: datetime | None
    is_active: bool
    item_count: int = 0
    items: list[AfeLineRead] = Field(default_factory=lambda: list[AfeLineRead]())
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class BulkProjectCreate(BaseModel):
    rows: list[ProjectCreate] = Field(min_length=1, max_length=5000)


class BulkProjectUpdateRow(ProjectUpdate):
    id: UUID


class BulkProjectUpdate(BaseModel):
    rows: list[BulkProjectUpdateRow] = Field(min_length=1, max_length=5000)


class BulkWellCreate(BaseModel):
    rows: list[WellCreate] = Field(min_length=1, max_length=5000)


class BulkWellUpdateRow(WellUpdate):
    id: UUID


class BulkWellUpdate(BaseModel):
    rows: list[BulkWellUpdateRow] = Field(min_length=1, max_length=5000)


class BulkAfeCreate(BaseModel):
    rows: list[AfeCreate] = Field(min_length=1, max_length=5000)


class BulkAfeUpdateRow(AfeUpdate):
    id: UUID


class BulkAfeUpdate(BaseModel):
    rows: list[BulkAfeUpdateRow] = Field(min_length=1, max_length=5000)


class BulkAfeLinesCreate(BaseModel):
    rows: list[AfeLineCreate] = Field(min_length=1, max_length=10_000)


class BulkAfeLineUpdateRow(AfeLineUpdate):
    id: UUID


class BulkAfeLinesUpdate(BaseModel):
    rows: list[BulkAfeLineUpdateRow] = Field(min_length=1, max_length=10_000)
