"""Daily cost tracking and AFE operational comparison schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Money = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=4)
OptionalMoney = Field(default=None, ge=0, max_digits=18, decimal_places=4)


class DailyCostServiceLineInput(BaseModel):
    service_id: UUID
    cost_code_id: UUID
    vendor_id: UUID | None = None
    hole_section_id: UUID | None = None
    sub_activity_id: UUID | None = None
    service_type: str = "operation"
    service_hours: Decimal = Field(
        default=Decimal("24.0"), ge=0, le=24, max_digits=8, decimal_places=2
    )
    rate_basis: Literal["daily", "per_service", "per_section", "fixed"] = "daily"
    unit_rate: Decimal = Money
    override_rate: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    remarks: str | None = None


class DailyCostServiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    daily_cost_entry_id: UUID
    service_id: UUID
    service_code: str | None = None
    service_name: str | None = None
    cost_code_id: UUID
    cost_code: str | None = None
    vendor_id: UUID | None = None
    vendor_name: str | None = None
    hole_section_id: UUID | None = None
    hole_section_code: str | None = None
    sub_activity_id: UUID | None = None
    sub_activity_name: str | None = None
    service_type: str = "operation"
    service_hours: Decimal
    operating_days: Decimal
    rate_basis: str
    unit_rate: Decimal
    override_rate: Decimal | None = None
    amount: Decimal
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class DailyCostConsumableLineInput(BaseModel):
    consumable_id: UUID
    cost_code_id: UUID
    vendor_id: UUID | None = None
    sub_activity_id: UUID | None = None
    quantity: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    unit_id: UUID
    unit_rate: Decimal = Money
    override_rate: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    remarks: str | None = None


class DailyCostConsumableLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    daily_cost_entry_id: UUID
    consumable_id: UUID
    consumable_code: str | None = None
    consumable_name: str | None = None
    cost_code_id: UUID
    cost_code: str | None = None
    vendor_id: UUID | None = None
    vendor_name: str | None = None
    sub_activity_id: UUID | None = None
    sub_activity_name: str | None = None
    quantity: Decimal
    unit_id: UUID
    unit_code: str | None = None
    unit_rate: Decimal
    override_rate: Decimal | None = None
    amount: Decimal
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class DailyCostEntryCreate(BaseModel):
    well_id: UUID
    afe_id: UUID | None = None
    entry_date: date
    hole_section_id: UUID | None = None
    phase: str | None = None
    sub_activity_id: UUID | None = None
    current_depth: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    daily_progress: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    operational_summary: str | None = None
    services: list[DailyCostServiceLineInput] = Field(default_factory=lambda: [])
    consumables: list[DailyCostConsumableLineInput] = Field(default_factory=lambda: [])


class DailyCostEntryUpdate(BaseModel):
    hole_section_id: UUID | None = None
    phase: str | None = None
    sub_activity_id: UUID | None = None
    current_depth: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    daily_progress: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    operational_summary: str | None = None
    services: list[DailyCostServiceLineInput] | None = None
    consumables: list[DailyCostConsumableLineInput] | None = None


class DailyCostEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    well_id: UUID
    well_code: str | None = None
    afe_id: UUID | None = None
    afe_code: str | None = None
    entry_date: date
    hole_section_id: UUID | None = None
    hole_section_code: str | None = None
    phase: str | None = None
    sub_activity_id: UUID | None = None
    sub_activity_name: str | None = None
    current_depth: Decimal | None = None
    daily_progress: Decimal | None = None
    operational_summary: str | None = None
    total_services_cost: Decimal
    total_consumables_cost: Decimal
    total_daily_cost: Decimal
    cumulative_cost: Decimal
    is_active: bool
    services: list[DailyCostServiceLineRead] = Field(default_factory=lambda: [])
    consumables: list[DailyCostConsumableLineRead] = Field(default_factory=lambda: [])
    created_at: datetime
    updated_at: datetime


class DailyTrendPoint(BaseModel):
    entry_date: date
    daily_cost: Decimal
    cumulative_cost: Decimal
    services_cost: Decimal
    consumables_cost: Decimal
    phase: str | None = None
    current_depth: Decimal | None = None


class ServiceBreakdownItem(BaseModel):
    service_id: UUID
    service_code: str
    service_name: str
    total_hours: Decimal
    total_days: Decimal
    total_cost: Decimal
    percentage: Decimal


class ConsumableBreakdownItem(BaseModel):
    consumable_id: UUID
    consumable_code: str
    consumable_name: str
    unit_code: str
    total_quantity: Decimal
    total_cost: Decimal
    percentage: Decimal


class DailyCostAnalyticsRead(BaseModel):
    well_id: UUID
    well_code: str
    afe_id: UUID | None = None
    afe_code: str | None = None
    afe_budget: Decimal
    total_planned_days: Decimal
    cumulative_actual_cost: Decimal
    balance_amount: Decimal
    days_elapsed: int
    burn_rate_daily_avg: Decimal
    remaining_planned_days: Decimal
    forecast_at_end_of_well: Decimal
    variance_to_afe: Decimal
    trend_last_5_days: list[DailyTrendPoint]
    trend_last_7_days: list[DailyTrendPoint]
    trend_all_days: list[DailyTrendPoint]
    services_breakdown: list[ServiceBreakdownItem]
    consumables_breakdown: list[ConsumableBreakdownItem]


class ReferenceServiceRate(BaseModel):
    service_id: UUID
    service_code: str
    service_name: str
    cost_code_id: UUID | None = None
    cost_code: str
    vendor_id: UUID | None = None
    vendor_name: str | None = None
    rate_basis: str
    operating_rate: Decimal
    unit_code: str


class ReferenceConsumableRate(BaseModel):
    consumable_id: UUID
    consumable_code: str
    consumable_name: str
    item_type: str
    cost_code_id: UUID | None = None
    cost_code: str
    unit_id: UUID | None = None
    unit_code: str
    unit_rate: Decimal


class ComparisonBucket(BaseModel):
    """One row of a planned-versus-actual grouping (section, activity, phase, …)."""

    key: str
    label: str
    entry_count: int = 0
    services_cost: Decimal = Decimal("0")
    consumables_cost: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
    planned_cost: Decimal | None = None
    variance: Decimal | None = None
    planned_days: Decimal | None = None
    actual_days: Decimal | None = None
    activity_code: str | None = None
    activity_name: str | None = None
    responsible_party: str | None = None


class DateComparisonPoint(BaseModel):
    entry_date: date
    day_number: int
    phase: str | None = None
    hole_section_code: str | None = None
    activity_name: str | None = None
    services_cost: Decimal = Decimal("0")
    consumables_cost: Decimal = Decimal("0")
    daily_cost: Decimal = Decimal("0")
    cumulative_cost: Decimal = Decimal("0")
    planned_cumulative: Decimal | None = None
    current_depth: Decimal | None = None
    daily_progress: Decimal | None = None


class DailyCostComparisonRead(BaseModel):
    """Well-scoped cost comparison across every reporting dimension."""

    well_id: UUID
    well_code: str | None = None
    well_name: str | None = None
    afe_id: UUID | None = None
    afe_code: str | None = None
    afe_title: str | None = None
    afe_budget: Decimal = Decimal("0")
    estimate_total: Decimal = Decimal("0")
    cumulative_actual_cost: Decimal = Decimal("0")
    variance_to_budget: Decimal = Decimal("0")
    variance_to_estimate: Decimal = Decimal("0")
    total_planned_days: Decimal = Decimal("0")
    days_elapsed: int = 0
    by_date: list[DateComparisonPoint] = Field(default_factory=lambda: [])
    by_week: list[ComparisonBucket] = Field(default_factory=lambda: [])
    by_month: list[ComparisonBucket] = Field(default_factory=lambda: [])
    by_section: list[ComparisonBucket] = Field(default_factory=lambda: [])
    by_phase: list[ComparisonBucket] = Field(default_factory=lambda: [])
    by_activity: list[ComparisonBucket] = Field(default_factory=lambda: [])
    by_sub_activity: list[ComparisonBucket] = Field(default_factory=lambda: [])
