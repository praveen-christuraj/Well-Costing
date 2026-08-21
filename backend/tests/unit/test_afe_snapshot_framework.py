"""Pure Phase 7 baseline AFE snapshot contract tests."""

from decimal import Decimal

import pytest
from app.domain.afe.snapshots import create_baseline_afe_snapshot
from app.domain.afe.types import AfeLineInput, BaselineAfeInput


def test_unconfirmed_baseline_afe_policy_fails_loudly() -> None:
    source = BaselineAfeInput(
        estimate_id="estimate-1",
        estimate_version_id="version-1",
        estimate_code="EST-001",
        estimate_title="Test estimate",
        afe_code="REQ-001",
        project_code="PRJ-001",
        well_code="WELL-001",
        currency_code="USD",
        calculation_run_id=None,
        engine_version=None,
        rule_set_version=None,
        base_total=None,
        contingency_total=None,
        escalation_total=None,
        grand_total=None,
        lines=(
            AfeLineInput(
                estimate_item_id="line-1",
                line_number=1,
                item_code="SVC-001",
                item_description="Test service",
                item_type="service",
                cost_code="1000",
                cost_category_code=None,
                vendor_code=None,
                quantity=Decimal("1.0000"),
                unit_code="DAY",
                rate_amount=None,
                rate_currency_code=None,
                base_cost=None,
                contingency_cost=None,
                escalation_cost=None,
                total_cost=None,
            ),
        ),
    )

    with pytest.raises(
        NotImplementedError,
        match=r"Business rule to be confirmed during Excel/business-rule discovery\.",
    ):
        create_baseline_afe_snapshot(source)
