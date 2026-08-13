"""Pure Phase 8 posting boundary tests."""

from datetime import date
from decimal import Decimal

import pytest
from app.domain.cost_control.posting import post_cost_batch
from app.domain.cost_control.types import CostEntryInput, CostPostingInput


def test_unconfirmed_cost_state_posting_policy_fails_loudly() -> None:
    source = CostPostingInput(
        batch_id="batch-1",
        estimate_version_id="version-1",
        afe_snapshot_id=None,
        cost_state="actual",
        entries=(
            CostEntryInput(
                staged_line_id="line-1",
                row_number=1,
                cost_state="actual",
                transaction_date=date(2026, 8, 13),
                source_document_type="invoice",
                source_document_reference="INV-001",
                external_transaction_id=None,
                cost_code="CC-001",
                vendor_code=None,
                description="Test actual",
                quantity=None,
                unit_code=None,
                currency_code="USD",
                amount=Decimal("100.0000"),
                correction_kind="original",
                reverses_transaction_id=None,
            ),
        ),
    )
    with pytest.raises(
        NotImplementedError,
        match=r"Business rule to be confirmed during Excel/business-rule discovery\.",
    ):
        post_cost_batch(source)
