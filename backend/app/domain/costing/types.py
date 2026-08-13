"""Pure domain input/output contracts for the costing engine."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class RateInput:
    amount: Decimal
    currency_code: str
    unit_code: str
    effective_from: date
    effective_to: date | None = None


@dataclass(frozen=True)
class EstimateLineInput:
    line_id: str
    item_code: str
    item_type: str
    cost_code: str
    cost_category_code: str | None
    quantity: Decimal
    quantity_unit_code: str
    rate: RateInput | None
    vendor_code: str | None


@dataclass(frozen=True)
class AssumptionInput:
    cost_category_code: str | None
    contingency_percent: Decimal | None
    escalation_percent: Decimal | None


@dataclass(frozen=True)
class EstimateInput:
    estimate_id: str
    version_id: str
    currency_code: str
    calculation_date: date
    lines: tuple[EstimateLineInput, ...]
    assumptions: tuple[AssumptionInput, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LineResult:
    line_id: str
    effective_quantity: Decimal
    effective_rate: Decimal
    base_cost: Decimal
    contingency_cost: Decimal
    escalation_cost: Decimal
    total_cost: Decimal


@dataclass(frozen=True)
class CategoryTotal:
    cost_category_code: str
    base_total: Decimal
    contingency_total: Decimal
    escalation_total: Decimal
    grand_total: Decimal


@dataclass(frozen=True)
class EstimateResult:
    lines: tuple[LineResult, ...]
    categories: tuple[CategoryTotal, ...]
    base_total: Decimal
    contingency_total: Decimal
    escalation_total: Decimal
    grand_total: Decimal
    currency_code: str
