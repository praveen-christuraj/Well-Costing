"""Pure contracts for shared-dimension cost reporting."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ReportingEntry:
    transaction_id: str
    cost_state: str
    transaction_date: date
    currency_code: str
    amount: Decimal


@dataclass(frozen=True)
class FinancialSummaryInput:
    entries: tuple[ReportingEntry, ...]
    reporting_currency_code: str | None


@dataclass(frozen=True)
class CostStateSummary:
    cost_state: str
    amount: Decimal
    currency_code: str


@dataclass(frozen=True)
class FinancialSummary:
    states: tuple[CostStateSummary, ...]
    variance_to_afe: Decimal
    forecast_at_completion: Decimal
