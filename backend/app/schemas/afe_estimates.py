"""AFE Cost Estimate schemas — well-scoped rates priced against configured AFE lines.

The estimate exposes the classification selected by the user on the AFE line.
It deliberately does not expose or infer a hard-coded service/tangible/other
"type". Calculation behaviour comes from the line's explicit rate basis.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AfeCostEstimateRateInput(BaseModel):
    """One unit rate keyed to an AFE line."""

    model_config = ConfigDict(extra="forbid")

    afe_line_id: UUID
    unit_rate: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
    vendor_id: UUID | None = None
    remarks: str | None = None


class AfeCostEstimateSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rates: list[AfeCostEstimateRateInput] = Field(
        default_factory=lambda: list[AfeCostEstimateRateInput]()
    )


class AfeCostEstimateLineRead(BaseModel):
    """An AFE line joined with its saved well-scoped unit rate."""

    model_config = ConfigDict(from_attributes=True)

    afe_line_id: UUID
    estimate_line_id: UUID | None = None
    line_number: int
    # Retained for historical lines created from a catalogue item. New lines are
    # identified by their configured classification below.
    catalog_item_id: UUID | None = None
    catalog_item_code: str | None = None
    catalog_item_name: str | None = None
    primary_category_id: UUID | None = None
    primary_category_code: str | None = None
    primary_category_name: str | None = None
    secondary_category_id: UUID | None = None
    secondary_category_code: str | None = None
    secondary_category_name: str | None = None
    cost_code_id: UUID
    cost_code: str | None = None
    hole_section_id: UUID | None = None
    hole_section_code: str | None = None
    applies_to_all_sections: bool = False
    rate_basis: str
    quantity: Decimal
    unit_id: UUID
    unit_code: str | None = None
    unit_rate: Decimal = Decimal("0")
    estimated_amount: Decimal = Decimal("0")
    vendor_id: UUID | None = None
    vendor_name: str | None = None
    remarks: str | None = None
    notes: str | None = None
    rate_saved_at: datetime | None = None


class AfeCostEstimateGroupTotal(BaseModel):
    key: str
    label: str
    line_count: int
    estimated_total: Decimal = Decimal("0")


class AfeCostEstimateRead(BaseModel):
    """The full priced AFE: header, priced lines, and user-configured roll-ups."""

    afe_id: UUID
    afe_code: str
    afe_title: str
    afe_status: str
    revision_number: int
    project_code: str | None = None
    project_name: str | None = None
    well_id: UUID
    well_code: str | None = None
    well_name: str | None = None
    rig_name: str | None = None
    budget_amount: Decimal = Decimal("0")
    total_planned_days: Decimal = Decimal("0")
    total_planned_depth: Decimal = Decimal("0")
    depth_unit_code: str | None = None
    line_count: int = 0
    priced_line_count: int = 0
    unpriced_line_count: int = 0
    estimated_total: Decimal = Decimal("0")
    variance_to_budget: Decimal = Decimal("0")
    lines: list[AfeCostEstimateLineRead] = Field(
        default_factory=lambda: list[AfeCostEstimateLineRead]()
    )
    totals_by_section: list[AfeCostEstimateGroupTotal] = Field(
        default_factory=lambda: list[AfeCostEstimateGroupTotal]()
    )
    totals_by_primary_category: list[AfeCostEstimateGroupTotal] = Field(
        default_factory=lambda: list[AfeCostEstimateGroupTotal]()
    )
    totals_by_secondary_category: list[AfeCostEstimateGroupTotal] = Field(
        default_factory=lambda: list[AfeCostEstimateGroupTotal]()
    )
    totals_by_cost_code: list[AfeCostEstimateGroupTotal] = Field(
        default_factory=lambda: list[AfeCostEstimateGroupTotal]()
    )
    totals_by_rate_basis: list[AfeCostEstimateGroupTotal] = Field(
        default_factory=lambda: list[AfeCostEstimateGroupTotal]()
    )
