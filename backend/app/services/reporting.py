"""Shared-dimension reporting read model and deterministic pending-policy export."""

import hashlib
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cost_control import CostTransaction
from app.models.master_data import CostCode
from app.models.reporting import ReportExportAttempt
from app.models.user import User
from app.schemas.reporting import (
    CostDrillThroughRow,
    CostOverviewReport,
    CostReportFilters,
    PendingStateSummary,
    ReportingContractRead,
    ReportingContractView,
    ReportingDimension,
)

REPORT_CODE = "shared-cost-overview"
REPORTING_POLICY_VERSION = "pending-shared-cost-reporting"
COST_STATES = ["field_estimate", "commitment", "accrual", "actual", "forecast"]
PENDING_METRICS = [
    "reporting currency and exchange-rate basis",
    "AFE budget aggregation and included snapshot family",
    "field estimate, commitment, accrual, and actual overlap treatment",
    "variance-to-AFE formula and sign convention",
    "forecast and estimate-at-completion methodology",
    "rounding, period cut-off, reversals, and zero-budget category behavior",
]
DIMENSIONS = [
    ("project_code", "Project"),
    ("well_code", "Well"),
    ("requirement_code", "Requirement"),
    ("estimate_code", "Estimate/version"),
    ("afe_number", "AFE"),
    ("cost_state", "Cost state"),
    ("transaction_date", "Date"),
    ("cost_category_code", "Cost category"),
    ("cost_code", "Cost code"),
    ("item_nature", "Item nature"),
    ("vendor_code", "Vendor"),
    ("currency_code", "Currency"),
    ("source_document_reference", "Source document"),
]


class ReportingService:
    def __init__(self, session: Session, actor: User) -> None:
        self.session, self.actor = session, actor

    @staticmethod
    def contract() -> ReportingContractRead:
        views = [
            ("v1_cost_transaction_fact", "fact", "Immutable posted source transactions"),
            ("v1_dim_project", "dimension", "Project reference"),
            ("v1_dim_well", "dimension", "Well and project reference"),
            ("v1_dim_cost_code", "dimension", "Cost code and category reference"),
            ("v1_dim_vendor", "dimension", "Vendor reference"),
            ("v1_dim_currency", "dimension", "Currency reference"),
            ("v1_dim_afe", "dimension", "Immutable AFE baseline reference"),
            ("v1_reporting_policy", "metadata", "Pending financial metric policy"),
            ("v1_contract_metadata", "metadata", "Contract version and security status"),
        ]
        return ReportingContractRead(
            contract_version="1.0",
            contract_status="framework",
            schema_name="reporting",
            direct_grants_status="not_applied",
            transactional_schema_public=False,
            views=[
                ReportingContractView(name=name, kind=kind, description=description)
                for name, kind, description in views
            ],
            pending_metrics=PENDING_METRICS,
        )

    def overview(self, filters: CostReportFilters) -> CostOverviewReport:
        rows = self._rows(filters)
        return CostOverviewReport(
            report_code=REPORT_CODE,
            policy_version=REPORTING_POLICY_VERSION,
            metric_status="policy_pending",
            filters=filters,
            dimensions=[
                ReportingDimension(key=key, label=label, available=True)
                for key, label in DIMENSIONS
            ],
            state_summaries=[
                PendingStateSummary(
                    cost_state=state,
                    transaction_count=sum(row.cost_state == state for row in rows),
                    amount=None,
                    currency_code=filters.currency_code,
                )
                for state in COST_STATES
            ],
            variance_to_afe=None,
            forecast_at_completion=None,
            drill_through=rows,
            pending_metrics=PENDING_METRICS,
        )

    def export(self, filters: CostReportFilters) -> bytes:
        report = self.overview(filters)
        workbook = Workbook()
        summary = workbook.active
        if summary is None:
            raise RuntimeError("Workbook did not create a worksheet")
        summary.title = "State Summary"
        summary.append(["cost_state", "transaction_count", "amount", "currency", "metric_status"])
        for state in report.state_summaries:
            summary.append(
                [
                    state.cost_state,
                    state.transaction_count,
                    None,
                    state.currency_code,
                    report.metric_status,
                ]
            )
        detail = workbook.create_sheet("Drill Through")
        detail_headers = list(CostDrillThroughRow.model_fields)
        detail.append(detail_headers)
        for row in report.drill_through:
            values = row.model_dump(mode="json")
            detail.append([values.get(header) for header in detail_headers])
        policy = workbook.create_sheet("Pending Metrics")
        policy.append(["policy_version", REPORTING_POLICY_VERSION])
        policy.append([])
        policy.append(["pending_metric"])
        for item in PENDING_METRICS:
            policy.append([item])
        stream = BytesIO()
        workbook.save(stream)
        content = stream.getvalue()
        attempt = ReportExportAttempt(
            report_code=REPORT_CODE,
            policy_version=REPORTING_POLICY_VERSION,
            status="completed_shell",
            filters_snapshot=filters.model_dump(mode="json"),
            row_count=len(report.drill_through),
            file_sha256=hashlib.sha256(content).hexdigest(),
            message=(
                "Export contains source drill-through and null financial metrics pending policy"
            ),
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )
        self.session.add(attempt)
        self.session.commit()
        return content

    def _rows(self, filters: CostReportFilters) -> list[CostDrillThroughRow]:
        transactions = list(self.session.scalars(select(CostTransaction)).unique().all())
        code_map = {
            code.code: code.cost_category.code if code.cost_category else None
            for code in self.session.scalars(select(CostCode)).all()
        }
        rows: list[CostDrillThroughRow] = []
        for transaction in transactions:
            afe = transaction.afe_snapshot
            version = afe.estimate_version
            estimate = version.estimate
            requirement = estimate.requirement
            row = CostDrillThroughRow(
                transaction_id=transaction.id,
                posting_reference=transaction.posting_reference,
                project_code=requirement.well.project.code,
                well_code=requirement.well.code,
                requirement_code=requirement.code,
                estimate_code=estimate.code,
                estimate_version_number=version.version_number,
                afe_number=afe.afe_number,
                cost_state=transaction.cost_state,
                transaction_date=transaction.transaction_date,
                cost_category_code=code_map.get(transaction.cost_code),
                cost_code=transaction.cost_code,
                item_nature=None,
                vendor_code=transaction.vendor_code,
                currency_code=transaction.currency_code,
                amount=transaction.amount,
                source_document_type=transaction.source_document_type,
                source_document_reference=transaction.source_document_reference,
                external_transaction_id=transaction.external_transaction_id,
                correction_kind=transaction.correction_kind,
                reverses_transaction_id=transaction.reverses_transaction_id,
            )
            if self._matches(row, filters):
                rows.append(row)
        return rows

    @staticmethod
    def _matches(row: CostDrillThroughRow, filters: CostReportFilters) -> bool:
        checks: list[tuple[Any, Any]] = [
            (filters.project_code, row.project_code),
            (filters.well_code, row.well_code),
            (filters.requirement_code, row.requirement_code),
            (filters.estimate_code, row.estimate_code),
            (filters.afe_number, row.afe_number),
            (filters.cost_state, row.cost_state),
            (filters.cost_code, row.cost_code),
            (filters.cost_category_code, row.cost_category_code),
            (filters.item_nature, row.item_nature),
            (filters.vendor_code, row.vendor_code),
            (filters.currency_code, row.currency_code),
            (filters.source_document_reference, row.source_document_reference),
        ]
        if any(expected is not None and expected != actual for expected, actual in checks):
            return False
        if filters.date_from and row.transaction_date < filters.date_from:
            return False
        return not (filters.date_to and row.transaction_date > filters.date_to)
