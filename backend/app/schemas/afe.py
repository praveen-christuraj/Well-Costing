"""Project, well, AFE, AFE section breakdown, and AFE-line API schemas."""

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


# ----------------------------------------------------------- Drilling phases
class DrillingPhaseCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    sequence: int = Field(default=1, ge=1)
    is_active: bool = True


class DrillingPhaseUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    sequence: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class DrillingPhaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    sequence: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------- AFE Sections
class AfeSectionCreate(BaseModel):
    sequence: int = Field(default=1, ge=1)
    hole_section_id: UUID | None = None
    phase: str = Field(default="Drilling", min_length=1, max_length=100)
    planned_days: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=4)
    planned_depth_from: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    planned_depth_to: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    depth_unit_id: UUID | None = None
    notes: str | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_depths(self) -> "AfeSectionCreate":
        if (
            self.planned_depth_from is not None
            and self.planned_depth_to is not None
            and self.planned_depth_to < self.planned_depth_from
        ):
            raise ValueError("planned_depth_to must be greater than or equal to planned_depth_from")
        return self


class AfeSectionUpdate(BaseModel):
    sequence: int | None = Field(default=None, ge=1)
    hole_section_id: UUID | None = None
    phase: str | None = Field(default=None, min_length=1, max_length=100)
    planned_days: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=4)
    planned_depth_from: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    planned_depth_to: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    depth_unit_id: UUID | None = None
    notes: str | None = None
    is_active: bool | None = None


class AfeSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    afe_id: UUID
    sequence: int
    hole_section_id: UUID | None
    hole_section_code: str | None = None
    hole_section_name: str | None = None
    phase: str
    planned_days: Decimal
    planned_depth_from: Decimal | None
    planned_depth_to: Decimal | None
    depth_unit_id: UUID | None
    depth_unit_code: str | None = None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AfeAuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    afe_id: UUID
    action: str
    previous_status: str | None
    new_status: str
    remarks: str | None
    actor_id: UUID | None
    created_at: datetime


class AfeReopenRequest(BaseModel):
    remarks: str = Field(min_length=1, max_length=2000, description="Mandatory remarks for reopening submitted AFE")


class AfeCreate(BaseModel):
    well_id: UUID
    code: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    budget_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    total_planned_days: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=4)
    total_planned_depth: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=4)
    depth_unit_id: UUID | None = None
    sections: list[AfeSectionCreate] = Field(default_factory=list)


class AfeUpdate(BaseModel):
    well_id: UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    budget_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    total_planned_days: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=4)
    total_planned_depth: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    depth_unit_id: UUID | None = None
    sections: list[AfeSectionCreate] | None = None
    is_active: bool | None = None


class AfeLineCreate(BaseModel):
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
    catalog_item_code: str | None = None
    catalog_item_name: str | None = None
    item_type: str | None = None
    cost_code_id: UUID
    cost_code: str | None = None
    quantity: Decimal
    unit_id: UUID
    unit_code: str | None = None
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
    budget_amount: Decimal = Decimal("0")
    total_planned_days: Decimal = Decimal("0")
    total_planned_depth: Decimal = Decimal("0")
    depth_unit_id: UUID | None = None
    depth_unit_code: str | None = None
    reopen_remarks: str | None = None
    reopened_at: datetime | None = None
    reopened_by: UUID | None = None
    supersedes_id: UUID | None = None
    submitted_at: datetime | None = None
    is_active: bool
    item_count: int = 0
    sections: list[AfeSectionRead] = Field(default_factory=lambda: list[AfeSectionRead]())
    items: list[AfeLineRead] = Field(default_factory=lambda: list[AfeLineRead]())
    audit_logs: list[AfeAuditLogRead] = Field(default_factory=lambda: list[AfeAuditLogRead]())
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
