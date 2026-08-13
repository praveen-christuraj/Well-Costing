"""Pure Phase 9 financial metric boundary tests."""

import pytest
from app.domain.reporting.metrics import build_financial_summary
from app.domain.reporting.types import FinancialSummaryInput


def test_unconfirmed_reporting_metrics_fail_loudly() -> None:
    with pytest.raises(
        NotImplementedError,
        match=r"Business rule to be confirmed during Excel/business-rule discovery\.",
    ):
        build_financial_summary(FinancialSummaryInput(entries=(), reporting_currency_code=None))
