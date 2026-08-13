"""Pure contracts for separate cost states and immutable source lineage."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

CostState = Literal["field_estimate", "commitment", "accrual", "actual", "forecast"]
CorrectionKind = Literal["original", "reversal", "adjustment"]


@dataclass(frozen=True)
class CostEntryInput:
    staged_line_id: str
    row_number: int
    cost_state: CostState
    transaction_date: date
    source_document_type: str
    source_document_reference: str
    external_transaction_id: str | None
    cost_code: str
    vendor_code: str | None
    description: str
    quantity: Decimal | None
    unit_code: str | None
    currency_code: str
    amount: Decimal
    correction_kind: CorrectionKind
    reverses_transaction_id: str | None


@dataclass(frozen=True)
class CostPostingInput:
    batch_id: str
    estimate_version_id: str
    afe_snapshot_id: str | None
    cost_state: CostState
    entries: tuple[CostEntryInput, ...]


@dataclass(frozen=True)
class PostedCostEntry:
    staged_line_id: str
    posting_reference: str
    amount: Decimal


@dataclass(frozen=True)
class CostPostingResult:
    entries: tuple[PostedCostEntry, ...]
