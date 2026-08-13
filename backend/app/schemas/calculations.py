"""Calculation audit and result API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CalculationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    estimate_version_id: UUID
    engine_version: str
    rule_set_version: str
    status: str
    message: str | None
    input_snapshot: dict[str, Any] | None
    output_snapshot: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class EstimateCalculationResults(BaseModel):
    estimate_id: UUID
    estimate_version_id: UUID
    version_number: int
    currency_code: str
    base_total: Decimal | None
    contingency_total: Decimal | None
    escalation_total: Decimal | None
    grand_total: Decimal | None
    calculation_status: str
    line_results: list[dict[str, Any]] = Field(default_factory=lambda: list[dict[str, Any]]())
    category_results: list[dict[str, Any]] = Field(default_factory=lambda: list[dict[str, Any]]())
    calculation_runs: list[CalculationRunRead]
    pending_rules: list[str]
