"""Phase 9 reporting filters, pending summaries, and shared-dimension drill-through."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

CostStateFilter = Literal["field_estimate", "commitment", "accrual", "actual", "forecast"]


class CostReportFilters(BaseModel):
    project_code: str | None = None
    well_code: str | None = None
    afe_code: str | None = None
    estimate_code: str | None = None
    afe_number: str | None = None
    cost_state: CostStateFilter | None = None
    date_from: date | None = None
    date_to: date | None = None
    cost_code: str | None = None
    cost_category_code: str | None = None
    item_nature: str | None = None
    vendor_code: str | None = None
    currency_code: str | None = None
    source_document_reference: str | None = None


class ReportingDimension(BaseModel):
    key: str
    label: str
    available: bool


class PendingStateSummary(BaseModel):
    cost_state: str
    transaction_count: int
    amount: Decimal | None
    currency_code: str | None


class CostDrillThroughRow(BaseModel):
    transaction_id: UUID
    posting_reference: str
    project_code: str
    well_code: str
    afe_code: str
    estimate_code: str
    estimate_version_number: int
    afe_number: str
    cost_state: str
    transaction_date: date
    cost_category_code: str | None
    cost_code: str
    item_nature: str | None
    vendor_code: str | None
    currency_code: str
    amount: Decimal
    source_document_type: str
    source_document_reference: str
    external_transaction_id: str | None
    correction_kind: str
    reverses_transaction_id: UUID | None


class CostOverviewReport(BaseModel):
    report_code: str
    policy_version: str
    metric_status: str
    filters: CostReportFilters
    dimensions: list[ReportingDimension]
    state_summaries: list[PendingStateSummary]
    variance_to_afe: Decimal | None
    forecast_at_completion: Decimal | None
    drill_through: list[CostDrillThroughRow]
    pending_metrics: list[str]


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
    pending_metrics: list[str]
