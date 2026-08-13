"""Deterministic tests for the pure Phase 5 calculation contract."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.domain.costing.calculations import calculate_estimate
from app.domain.costing.types import EstimateInput, EstimateLineInput


def test_full_chain_contract_is_typed_but_rule_execution_is_blocked() -> None:
    model = EstimateInput(
        estimate_id=str(uuid4()),
        version_id=str(uuid4()),
        currency_code="USD",
        calculation_date=date(2026, 8, 13),
        lines=(
            EstimateLineInput(
                line_id=str(uuid4()),
                item_code="SVC-001",
                item_type="service",
                cost_code="1000",
                cost_category_code=None,
                quantity=Decimal("2.0000"),
                quantity_unit_code="DAY",
                rate=None,
                vendor_code=None,
            ),
        ),
        assumptions=(),
    )

    with pytest.raises(
        NotImplementedError,
        match=r"Business rule to be confirmed during Excel/business-rule discovery\.",
    ):
        calculate_estimate(model)
