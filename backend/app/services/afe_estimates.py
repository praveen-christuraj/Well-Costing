"""AFE Cost Estimate services.

The AFE Cost Estimates page prices the AFE: every AFE line (service,
chemical, additive, tangible, …) receives a well-scoped unit rate here.
The saved rates are the single source of unit rates for daily cost entry
(where a per-line override is still available and recorded).
"""

from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.models.afe import Afe, AfeLine
from app.models.afe_estimates import AfeCostEstimateLine
from app.schemas.afe_estimates import (
    AfeCostEstimateGroupTotal,
    AfeCostEstimateLineRead,
    AfeCostEstimateRead,
    AfeCostEstimateSaveRequest,
)
from app.services.audit import log_entity_action

CONSUMABLE_ITEM_TYPES = {"mud_chemical", "cement_additive", "material"}

HEADER_FILL = PatternFill("solid", fgColor="0F766E")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14)
LABEL_FONT = Font(bold=True)
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


class AfeEstimateService:
    """Well-scoped pricing of AFE lines."""

    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id

    # ------------------------------------------------------------------ reads
    def get_estimate(self, afe_id: UUID) -> AfeCostEstimateRead:
        afe = self._get_afe(afe_id)
        rate_rows = self._rate_rows(afe_id)
        lines = [
            self._read_line(item, rate_rows.get(item.id)) for item in afe.items if item.is_active
        ]
        return self._build_read(afe, lines)

    def save_rates(self, afe_id: UUID, payload: AfeCostEstimateSaveRequest) -> AfeCostEstimateRead:
        afe = self._get_afe(afe_id)
        line_ids = {item.id for item in afe.items if item.is_active}
        rate_rows = self._rate_rows(afe_id)

        saved = 0
        for entry in payload.rates:
            if entry.afe_line_id not in line_ids:
                raise BusinessValidationError(
                    "A rate referenced an AFE line that does not belong to this AFE. "
                    "Reload the AFE Cost Estimates page and try again."
                )
            row = rate_rows.get(entry.afe_line_id)
            if row is None:
                row = AfeCostEstimateLine(
                    afe_id=afe_id,
                    afe_line_id=entry.afe_line_id,
                    created_by=self.actor_id,
                )
                self.session.add(row)
                rate_rows[entry.afe_line_id] = row
            row.unit_rate = Decimal(str(entry.unit_rate))
            row.vendor_id = entry.vendor_id
            row.remarks = entry.remarks
            row.is_active = True
            row.updated_by = self.actor_id
            saved += 1

        self.session.flush()
        log_entity_action(
            self.session,
            self.actor_id,
            "save_rates",
            "afe_cost_estimate",
            entity_id=afe_id,
            entity_code=afe.code,
            details={"rates_saved": saved},
        )
        self.session.commit()
        return self.get_estimate(afe_id)

    # ----------------------------------------------------------------- export
    def export_workbook(self, afe_id: UUID) -> bytes:
        """Full AFE Cost Estimate as a printable Excel record."""
        estimate = self.get_estimate(afe_id)
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = "AFE Cost Estimate"

        sheet["A1"] = "AFE COST ESTIMATE"
        sheet["A1"].font = TITLE_FONT
        sheet["A2"] = f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')} UTC"

        header_pairs = [
            ("Project", f"{estimate.project_code or ''} — {estimate.project_name or ''}"),
            ("Well", f"{estimate.well_code or ''} — {estimate.well_name or ''}"),
            ("Rig", estimate.rig_name or ""),
            ("AFE", f"{estimate.afe_code} (rev {estimate.revision_number})"),
            ("Title", estimate.afe_title),
            ("Status", estimate.afe_status),
            ("AFE budget", float(estimate.budget_amount)),
            ("Planned days", float(estimate.total_planned_days)),
            ("Estimated total", float(estimate.estimated_total)),
            ("Variance to budget", float(estimate.variance_to_budget)),
        ]
        row_index = 4
        for label, value in header_pairs:
            sheet.cell(row_index, 1, label).font = LABEL_FONT
            sheet.cell(row_index, 2, value)
            row_index += 1

        row_index += 1
        headers = [
            "#",
            "Item code",
            "Item name",
            "Type",
            "Cost code",
            "Hole section",
            "Rate basis",
            "Quantity",
            "Unit",
            "Unit rate",
            "Estimated amount",
            "Vendor",
            "Remarks",
        ]
        for column, header in enumerate(headers, start=1):
            cell = sheet.cell(row_index, column, header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.border = THIN_BORDER
        first_data_row = row_index + 1
        for line in estimate.lines:
            row_index += 1
            values: list[Any] = [
                line.line_number,
                line.catalog_item_code,
                line.catalog_item_name,
                (line.item_type or "").replace("_", " "),
                line.cost_code,
                line.hole_section_code,
                line.rate_basis,
                float(line.quantity),
                line.unit_code,
                float(line.unit_rate),
                float(line.estimated_amount),
                line.vendor_name,
                line.remarks,
            ]
            for column, value in enumerate(values, start=1):
                cell = sheet.cell(row_index, column, value)
                cell.border = THIN_BORDER
        row_index += 1
        total_cell = sheet.cell(row_index, 10, "Estimated total")
        total_cell.font = LABEL_FONT
        amount_cell = sheet.cell(row_index, 11, float(estimate.estimated_total))
        amount_cell.font = LABEL_FONT
        if estimate.lines:
            sheet.freeze_panes = sheet.cell(first_data_row, 1).coordinate
        for column, width in enumerate([6, 16, 34, 14, 12, 14, 12, 12, 8, 14, 16, 20, 24], start=1):
            sheet.column_dimensions[get_column_letter(column)].width = width

        summary = workbook.create_sheet("Summaries")
        self._write_summary_block(summary, 1, "By hole section", estimate.totals_by_section)
        offset = 4 + len(estimate.totals_by_section)
        self._write_summary_block(summary, offset, "By item type", estimate.totals_by_item_type)
        offset += 3 + len(estimate.totals_by_item_type)
        self._write_summary_block(summary, offset, "By cost code", estimate.totals_by_cost_code)
        offset += 3 + len(estimate.totals_by_cost_code)
        self._write_summary_block(summary, offset, "By rate basis", estimate.totals_by_rate_basis)
        summary.column_dimensions["A"].width = 30
        summary.column_dimensions["B"].width = 12
        summary.column_dimensions["C"].width = 18

        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    @staticmethod
    def _write_summary_block(
        sheet: Worksheet,
        start_row: int,
        title: str,
        totals: list[AfeCostEstimateGroupTotal],
    ) -> None:
        sheet.cell(start_row, 1, title).font = TITLE_FONT
        header_row = start_row + 1
        for column, header in enumerate(["Group", "Lines", "Estimated total"], start=1):
            cell = sheet.cell(header_row, column, header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
        for index, total in enumerate(totals, start=1):
            sheet.cell(header_row + index, 1, total.label)
            sheet.cell(header_row + index, 2, total.line_count)
            cell = sheet.cell(header_row + index, 3, float(total.estimated_total))
            cell.alignment = Alignment(horizontal="right")

    # ---------------------------------------------------------------- helpers
    def _get_afe(self, afe_id: UUID) -> Afe:
        afe = self.session.get(Afe, afe_id)
        if afe is None or not afe.is_active:
            raise NotFoundError("AFE not found")
        return afe

    def _rate_rows(self, afe_id: UUID) -> dict[UUID, AfeCostEstimateLine]:
        rows = self.session.scalars(
            select(AfeCostEstimateLine).where(
                AfeCostEstimateLine.afe_id == afe_id,
                AfeCostEstimateLine.is_active.is_(True),
            )
        ).all()
        return {row.afe_line_id: row for row in rows}

    @staticmethod
    def effective_quantity(item: AfeLine) -> Decimal:
        """Planned quantity: the entered/overridden quantity, else the computed one."""
        if item.quantity and item.quantity > 0:
            return Decimal(item.quantity)
        if item.computed_quantity and item.computed_quantity > 0:
            return Decimal(item.computed_quantity)
        return Decimal("0")

    def _read_line(
        self, item: AfeLine, rate: AfeCostEstimateLine | None
    ) -> AfeCostEstimateLineRead:
        quantity = self.effective_quantity(item)
        unit_rate = Decimal(rate.unit_rate) if rate else Decimal("0")
        return AfeCostEstimateLineRead(
            afe_line_id=item.id,
            estimate_line_id=rate.id if rate else None,
            line_number=item.line_number,
            catalog_item_id=item.catalog_item_id,
            catalog_item_code=item.catalog_item.code if item.catalog_item else None,
            catalog_item_name=item.catalog_item.name if item.catalog_item else None,
            item_type=item.catalog_item.item_type if item.catalog_item else None,
            cost_code_id=item.cost_code_id,
            cost_code=item.cost_code.code if item.cost_code else None,
            hole_section_id=item.hole_section_id,
            hole_section_code=item.hole_section.code if item.hole_section else None,
            applies_to_all_sections=item.applies_to_all_sections,
            rate_basis=item.rate_basis,
            quantity=quantity,
            unit_id=item.unit_id,
            unit_code=item.unit.code if item.unit else None,
            unit_rate=unit_rate,
            estimated_amount=quantity * unit_rate,
            vendor_id=rate.vendor_id if rate else None,
            vendor_name=rate.vendor.name if rate and rate.vendor else None,
            remarks=rate.remarks if rate else None,
            notes=item.notes,
            rate_saved_at=rate.updated_at if rate else None,
        )

    def _build_read(self, afe: Afe, lines: list[AfeCostEstimateLineRead]) -> AfeCostEstimateRead:
        estimated_total = sum((line.estimated_amount for line in lines), Decimal("0"))
        services_total = sum(
            (line.estimated_amount for line in lines if line.item_type == "service"),
            Decimal("0"),
        )
        priced = sum(1 for line in lines if line.unit_rate > 0)
        well = afe.well
        return AfeCostEstimateRead(
            afe_id=afe.id,
            afe_code=afe.code,
            afe_title=afe.title,
            afe_status=afe.status,
            revision_number=afe.revision_number,
            project_code=well.project.code if well and well.project else None,
            project_name=well.project.name if well and well.project else None,
            well_id=afe.well_id,
            well_code=well.code if well else None,
            well_name=well.name if well else None,
            rig_name=well.rig_name if well else None,
            budget_amount=Decimal(afe.budget_amount or 0),
            total_planned_days=Decimal(afe.total_planned_days or 0),
            total_planned_depth=Decimal(afe.total_planned_depth or 0),
            depth_unit_code=afe.depth_unit.code if afe.depth_unit else None,
            line_count=len(lines),
            priced_line_count=priced,
            unpriced_line_count=len(lines) - priced,
            estimated_total=estimated_total,
            services_total=services_total,
            consumables_total=estimated_total - services_total,
            variance_to_budget=Decimal(afe.budget_amount or 0) - estimated_total,
            lines=lines,
            totals_by_section=self._group(lines, "section"),
            totals_by_item_type=self._group(lines, "item_type"),
            totals_by_cost_code=self._group(lines, "cost_code"),
            totals_by_rate_basis=self._group(lines, "rate_basis"),
        )

    @staticmethod
    def _group(
        lines: list[AfeCostEstimateLineRead], dimension: str
    ) -> list[AfeCostEstimateGroupTotal]:
        buckets: dict[str, AfeCostEstimateGroupTotal] = {}
        for line in lines:
            if dimension == "section":
                key = "All sections" if line.applies_to_all_sections else (
                    line.hole_section_code or "Unassigned"
                )
            elif dimension == "item_type":
                key = (line.item_type or "other").replace("_", " ").title()
            elif dimension == "cost_code":
                key = line.cost_code or "Unassigned"
            else:
                key = line.rate_basis.replace("_", " ").title()
            bucket = buckets.get(key)
            if bucket is None:
                bucket = AfeCostEstimateGroupTotal(key=key, label=key, line_count=0)
                buckets[key] = bucket
            bucket.line_count += 1
            bucket.estimated_total += line.estimated_amount
        return sorted(buckets.values(), key=lambda b: b.estimated_total, reverse=True)
