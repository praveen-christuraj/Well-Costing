"""Pydantic schemas for Daily Costs (and the Cost Analytics / Reports pages)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.master_data import BlankStr, FlagBool
from app.schemas.rig_well import WellConfigurationOut

DailyCostStatus = Literal["draft", "submitted"]
ChargingBasis = Literal["Daily Rate", "Per Service Rate", "Per Section Rate"]
QuantityUnit = Literal["days", "hours"]
ConsumableCategory = Literal["mud_chemical", "fuel", "cement_additive", "drill_bit"]
CostGroup = Literal["Services", "Consumables", "Tangibles"]
ReportDimension = Literal[
    "date",
    "section",
    "phase",
    "activity",
    "sub_activity",
    "service",
    "charge_category",
    "consumable_category",
    "tangible",
    "well",
]


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class DailyCostEntryIn(BaseModel):
    """Create the day sheet for one rig + well + date."""

    well_id: int = Field(..., description="Well the day belongs to (the rig follows the well)")
    cost_date: date
    afe_id: int | None = Field(None, description="AFE that supplies the rate card")
    remarks: str | None = None


class DailyCostEntryUpdate(BaseModel):
    cost_date: date | None = None
    afe_id: int | None = None
    remarks: str | None = None


class DailyServiceLineIn(BaseModel):
    """One service line of the day.

    ``charging_basis`` and ``captured_rate`` are optional on purpose: when the
    service exists on the day's AFE the server takes both from that AFE line
    (the AFE owns the rate card), so the browser never decides money. They are
    only honoured when the service is not on the AFE and the user typed the
    rate by hand.
    """

    service_id: int
    charging_basis: ChargingBasis | None = None
    charge_category: str | None = None
    afe_line_id: int | None = None
    section_id: int | None = None
    phase_id: int | None = None
    sub_activity_id: int | None = None
    quantity: Decimal = Field(Decimal("0"), ge=0)
    quantity_unit: QuantityUnit = "hours"
    captured_rate: Decimal | None = None
    override_rate: Decimal | None = Field(None, ge=0)
    remarks: str | None = None


class DailyConsumableLineIn(BaseModel):
    category: ConsumableCategory = "mud_chemical"
    item_id: int | None = None
    item_code: str | None = None
    item_name: str | None = None
    quantity: Decimal = Field(Decimal("0"), ge=0)
    uom: str | None = None
    currency: str | None = None
    captured_rate: Decimal | None = None
    override_rate: Decimal | None = Field(None, ge=0)
    #: Cement additives: the total consumption cost for the chosen scope.
    manual_amount: Decimal | None = Field(None, ge=0)
    section_id: int | None = None
    phase_id: int | None = None
    sub_activity_id: int | None = None
    remarks: str | None = None


class DailyTangibleLineIn(BaseModel):
    tangible_id: int
    quantity: Decimal = Field(Decimal("1"), ge=0)
    uom: str | None = None
    currency: str | None = None
    captured_rate: Decimal | None = None
    override_rate: Decimal | None = Field(None, ge=0)
    remarks: str | None = None


class DailyCostSaveIn(BaseModel):
    """The whole day, saved atomically."""

    services: list[DailyServiceLineIn] = Field(default_factory=list)
    consumables: list[DailyConsumableLineIn] = Field(default_factory=list)
    tangibles: list[DailyTangibleLineIn] = Field(default_factory=list)
    remarks: str | None = None


class DailyCostPreviewIn(DailyCostSaveIn):
    """Preview payload — priced before the day exists."""

    well_id: int
    afe_id: int | None = None


class DailyStatusIn(BaseModel):
    action: Literal["submit", "reopen"]
    remarks: str | None = None


# ---------------------------------------------------------------------------
# Rate card (what the AFE says about each service)
# ---------------------------------------------------------------------------


class RateCardServiceOut(BaseModel):
    """One service of the AFE rate card, as the daily page needs it."""

    service_id: int
    afe_line_id: int | None = None
    service_code: str = ""
    service_name: str = ""
    provider_type: str = ""
    charging_basis: str = "Daily Rate"
    per_service_amount: Decimal = Decimal("0")
    section_id: int | None = None
    phase_id: int | None = None
    rates: list[dict[str, object]] = Field(default_factory=list)
    section_rates: list[dict[str, object]] = Field(default_factory=list)


class DailyCostContextOut(BaseModel):
    """Everything the daily page needs once the rig/well/date are picked."""

    well_id: int
    well_code: str = ""
    well_name: str = ""
    rig_id: int | None = None
    rig_code: str | None = None
    rig_name: str | None = None
    depth_unit: str = "m"
    well_configuration: WellConfigurationOut | None = None
    afes: list[dict[str, object]] = Field(default_factory=list)
    sub_activities: list[dict[str, object]] = Field(default_factory=list)
    rate_card: list[RateCardServiceOut] = Field(default_factory=list)
    afe_id: int | None = None
    #: Fuel unit rate captured on the selected AFE — the only consumable the
    #: daily page reads its rate from the AFE for.
    fuel_rate: Decimal = Decimal("0")
    #: The selected AFE's estimated total, so the sheet can show what is left.
    afe_estimated_total: Decimal = Decimal("0")
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


class DailyLineWarningOut(BaseModel):
    line_id: int | None = None
    message: str


class DailyServiceLineOut(BaseModel):
    id: int
    service_id: int
    service_code: str | None = None
    service_name: str | None = None
    provider_type: str | None = None
    afe_line_id: int | None = None
    charging_basis: str
    charge_category: str
    section_id: int | None = None
    phase_id: int | None = None
    sub_activity_id: int | None = None
    sub_activity_display: str | None = None
    quantity: Decimal = Decimal("0")
    quantity_unit: str = "hours"
    captured_rate: Decimal = Decimal("0")
    override_rate: Decimal | None = None
    amount: Decimal = Decimal("0")
    remarks: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DailyConsumableLineOut(BaseModel):
    id: int
    category: str
    item_id: int | None = None
    item_code: str
    item_name: str
    quantity: Decimal = Decimal("0")
    uom: str | None = None
    currency: str | None = None
    captured_rate: Decimal = Decimal("0")
    override_rate: Decimal | None = None
    manual_amount: Decimal | None = None
    amount: Decimal = Decimal("0")
    section_id: int | None = None
    phase_id: int | None = None
    sub_activity_id: int | None = None
    sub_activity_display: str | None = None
    remarks: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DailyTangibleLineOut(BaseModel):
    id: int
    tangible_id: int
    tangible_code: str | None = None
    tangible_name: str | None = None
    quantity: Decimal = Decimal("1")
    uom: str | None = None
    currency: str | None = None
    captured_rate: Decimal = Decimal("0")
    override_rate: Decimal | None = None
    amount: Decimal = Decimal("0")
    remarks: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DailyCostEntryOut(BaseModel):
    """The day's header with its three group totals — the list read model."""

    id: int
    daily_cost_code: BlankStr = ""
    rig_id: int
    well_id: int
    cost_date: date
    afe_id: int | None = None
    afe_code: str | None = None
    remarks: str | None = None
    status: BlankStr = "draft"
    submitted_at: datetime | None = None
    reconciliation_status: BlankStr = "pending"
    reconciliation_ref: str | None = None
    reconciled_at: datetime | None = None
    is_deleted: FlagBool = False
    deleted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    rig_code: str | None = None
    rig_name: str | None = None
    rig_display: str | None = None
    well_code: str | None = None
    well_name: str | None = None
    well_display: str | None = None
    service_count: int = 0
    consumable_count: int = 0
    tangible_count: int = 0
    service_total: Decimal = Decimal("0")
    consumable_total: Decimal = Decimal("0")
    tangible_total: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")

    model_config = ConfigDict(from_attributes=True)


class DailyCostDayOut(BaseModel):
    """The full day: header, configuration, lines, totals and warnings."""

    entry: DailyCostEntryOut
    well_configuration: WellConfigurationOut | None = None
    services: list[DailyServiceLineOut] = Field(default_factory=list)
    consumables: list[DailyConsumableLineOut] = Field(default_factory=list)
    tangibles: list[DailyTangibleLineOut] = Field(default_factory=list)
    summary: list[dict[str, object]] = Field(default_factory=list)
    grand_total: Decimal = Decimal("0")
    warnings: list[str] = Field(default_factory=list)


class DailyCostPreviewOut(BaseModel):
    """Live totals for the rows on screen — the same engine that saves them."""

    services: list[dict[str, object]] = Field(default_factory=list)
    consumables: list[dict[str, object]] = Field(default_factory=list)
    tangibles: list[dict[str, object]] = Field(default_factory=list)
    summary: list[dict[str, object]] = Field(default_factory=list)
    grand_total: Decimal = Decimal("0")
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Analytics / reports
# ---------------------------------------------------------------------------


class GroupComparisonOut(BaseModel):
    group: str
    estimated: Decimal = Decimal("0")
    actual: Decimal = Decimal("0")
    reconciled: Decimal = Decimal("0")
    unreconciled: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    utilisation: Decimal | None = None


class CostForecastOut(BaseModel):
    actual_to_date: Decimal = Decimal("0")
    estimated_total: Decimal = Decimal("0")
    planned_days: Decimal = Decimal("0")
    elapsed_days: Decimal = Decimal("0")
    remaining_days: Decimal = Decimal("0")
    burn_rate_per_day: Decimal = Decimal("0")
    forecast_at_completion: Decimal = Decimal("0")
    variance: Decimal = Decimal("0")
    variance_pct: Decimal | None = None
    balance_at_completion: Decimal = Decimal("0")
    basis: str = ""


class DepthCostPointOut(BaseModel):
    depth: Decimal
    section_id: int | None = None
    section_label: str = ""
    estimated_cumulative: Decimal = Decimal("0")
    actual_cumulative: Decimal = Decimal("0")
    estimated_section: Decimal = Decimal("0")
    actual_section: Decimal = Decimal("0")
    variance: Decimal = Decimal("0")


class WellAnalyticsSummaryOut(BaseModel):
    """One row of the Cost Analytics table."""

    well_id: int
    well_code: str = ""
    well_name: str = ""
    rig_id: int | None = None
    rig_code: str | None = None
    rig_name: str | None = None
    well_status: str = ""
    depth_unit: str = "m"
    afe_count: int = 0
    estimated_total: Decimal = Decimal("0")
    estimated_services: Decimal = Decimal("0")
    estimated_consumables: Decimal = Decimal("0")
    estimated_tangibles: Decimal = Decimal("0")
    actual_total: Decimal = Decimal("0")
    actual_services: Decimal = Decimal("0")
    actual_consumables: Decimal = Decimal("0")
    actual_tangibles: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    utilisation: Decimal | None = None
    reconciled_total: Decimal = Decimal("0")
    unreconciled_total: Decimal = Decimal("0")
    planned_days: Decimal = Decimal("0")
    elapsed_days: Decimal = Decimal("0")
    days_with_cost: int = 0
    first_cost_date: date | None = None
    last_cost_date: date | None = None
    forecast_at_completion: Decimal = Decimal("0")
    forecast_variance: Decimal = Decimal("0")


class WellAnalyticsOut(BaseModel):
    """The Cost Analytics detail for one well."""

    well: WellAnalyticsSummaryOut
    afe_id: int | None = None
    afes: list[dict[str, object]] = Field(default_factory=list)
    comparisons: list[GroupComparisonOut] = Field(default_factory=list)
    forecast: CostForecastOut
    depth_series: list[DepthCostPointOut] = Field(default_factory=list)
    depth_notes: list[str] = Field(default_factory=list)
    unattributed_actual: Decimal = Decimal("0")
    dimensions: dict[str, list[dict[str, object]]] = Field(default_factory=dict)
    daily_trend: list[dict[str, object]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReportRowOut(BaseModel):
    """One drill-through row of the Reports page."""

    key: str
    label: str
    services: Decimal = Decimal("0")
    consumables: Decimal = Decimal("0")
    tangibles: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    estimated: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")
    extra: dict[str, object] = Field(default_factory=dict)


class ReportOut(BaseModel):
    dimension: str
    title: str
    filters: dict[str, object] = Field(default_factory=dict)
    rows: list[ReportRowOut] = Field(default_factory=list)
    totals: dict[str, Decimal] = Field(default_factory=dict)
    generated_at: datetime | None = None
