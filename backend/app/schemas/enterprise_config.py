"""Enterprise configuration administration API contracts."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NodeTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    level_order: int = Field(ge=0)
    description: str | None = None


class NodeTypeRead(NodeTypeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    created_by: UUID | None


class HierarchyRuleCreate(BaseModel):
    parent_type_id: UUID
    child_type_id: UUID


class HierarchyRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    parent_type_id: UUID
    child_type_id: UUID
    is_active: bool
    created_at: datetime
    created_by: UUID | None


class EnterpriseNodeCreate(BaseModel):
    node_type_id: UUID
    parent_id: UUID | None = None
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class EnterpriseNodeRead(EnterpriseNodeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    created_at: datetime
    created_by: UUID | None


class VersionedConfigCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    version_number: int = Field(default=1, ge=1)
    description: str | None = None


class VersionedConfigRead(VersionedConfigCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    lifecycle_status: str
    created_at: datetime
    created_by: UUID | None


class CostBreakdownNodeCreate(BaseModel):
    parent_id: UUID | None = None
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    sort_order: int = Field(default=0, ge=0)
    cost_category_id: UUID | None = None
    cost_code_id: UUID | None = None


class RateBookCreate(VersionedConfigCreate):
    effective_from: date | None = None
    effective_to: date | None = None


class RateBookRead(VersionedConfigRead):
    effective_from: date | None
    effective_to: date | None


class RateBookEntryCreate(BaseModel):
    rate_id: UUID


class EstimateTemplateLineCreate(BaseModel):
    line_number: int = Field(ge=1)
    catalog_item_id: UUID
    cost_code_id: UUID
    unit_id: UUID
    default_quantity: Decimal | None = Field(default=None, ge=0)
    is_required: bool = False


class ReportingMappingCreate(BaseModel):
    target_system: str = Field(min_length=1, max_length=100)
    source_dimension: str = Field(min_length=1, max_length=100)
    source_value: str = Field(min_length=1, max_length=200)
    target_value: str = Field(min_length=1, max_length=200)
    version_number: int = Field(default=1, ge=1)
    description: str | None = None


class ReportingMappingRead(ReportingMappingCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    lifecycle_status: str
    created_at: datetime
    created_by: UUID | None


class EnterpriseConfigSummary(BaseModel):
    node_types: list[NodeTypeRead]
    hierarchy_rules: list[HierarchyRuleRead]
    nodes: list[EnterpriseNodeRead]
    cost_structures: list[VersionedConfigRead]
    rate_books: list[RateBookRead]
    estimate_templates: list[VersionedConfigRead]
    reporting_mappings: list[ReportingMappingRead]
    workflow_profile_count: int
