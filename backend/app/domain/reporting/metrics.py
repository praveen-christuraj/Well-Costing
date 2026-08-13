"""Financial reporting metric boundary."""

from typing import Never

from app.domain.reporting.types import FinancialSummaryInput


def build_financial_summary(source: FinancialSummaryInput) -> Never:
    """Business rule to be confirmed during Excel/business-rule discovery."""

    del source
    raise NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")
