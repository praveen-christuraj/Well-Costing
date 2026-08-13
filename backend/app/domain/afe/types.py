"""Pure input and immutable output contracts for baseline AFE snapshots."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class AfeLineInput:
    estimate_item_id: str
    line_number: int
    item_code: str
    item_description: str
    item_type: str
    cost_code: str
    cost_category_code: str | None
    vendor_code: str | None
    quantity: Decimal
    unit_code: str
    rate_amount: Decimal | None
    rate_currency_code: str | None
    base_cost: Decimal | None
    contingency_cost: Decimal | None
    escalation_cost: Decimal | None
    total_cost: Decimal | None


@dataclass(frozen=True)
class BaselineAfeInput:
    estimate_id: str
    estimate_version_id: str
    estimate_code: str
    estimate_title: str
    requirement_code: str
    project_code: str
    well_code: str
    currency_code: str
    calculation_run_id: str | None
    engine_version: str | None
    rule_set_version: str | None
    base_total: Decimal | None
    contingency_total: Decimal | None
    escalation_total: Decimal | None
    grand_total: Decimal | None
    lines: tuple[AfeLineInput, ...]


@dataclass(frozen=True)
class AfeLineSnapshot:
    source_estimate_item_id: str
    line_number: int
    item_code: str
    item_description: str
    item_type: str
    cost_code: str
    cost_category_code: str | None
    vendor_code: str | None
    quantity: Decimal
    unit_code: str
    rate_amount: Decimal | None
    rate_currency_code: str | None
    base_cost: Decimal
    contingency_cost: Decimal
    escalation_cost: Decimal
    total_cost: Decimal


@dataclass(frozen=True)
class BaselineAfeSnapshot:
    afe_number: str
    issue_date: date
    estimate_id: str
    estimate_version_id: str
    calculation_run_id: str
    currency_code: str
    base_total: Decimal
    contingency_total: Decimal
    escalation_total: Decimal
    grand_total: Decimal
    lines: tuple[AfeLineSnapshot, ...]
