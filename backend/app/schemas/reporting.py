"""Operational report contracts sourced from the active well-costing workflow."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ReportType = Literal[
    "afe_register",
    "afe_cost_estimate",
    "daily_cost",
    "cost_performance",
    "well_activities",
]
ReportCell = str | int | float | Decimal | date | datetime | None


class ReportFilters(BaseModel):
    report_type: ReportType = "afe_register"
    project_id: UUID | None = None
    well_id: UUID | None = None
    afe_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None


class ReportColumn(BaseModel):
    key: str
    label: str
    format: Literal["text", "number", "money", "date", "status"] = "text"


class ReportSummary(BaseModel):
    key: str
    label: str
    value: ReportCell
    format: Literal["text", "number", "money"] = "text"


class GeneratedReport(BaseModel):
    report_type: ReportType
    title: str
    description: str
    generated_at: datetime
    filters: ReportFilters
    columns: list[ReportColumn] = Field(default_factory=lambda: list[ReportColumn]())
    rows: list[dict[str, ReportCell]] = Field(default_factory=lambda: list[dict[str, ReportCell]]())
    summaries: list[ReportSummary] = Field(default_factory=lambda: list[ReportSummary]())


class ReportingContractView(BaseModel):
    name: str
    kind: str
    description: str


class ReportingContractRead(BaseModel):
    contract_version: str
    contract_status: str
    schema_name: str
    direct_grants_status: str
    transactional_schema_public: bool
    views: list[ReportingContractView]
    pending_metrics: list[str] = Field(default_factory=lambda: list[str]())
