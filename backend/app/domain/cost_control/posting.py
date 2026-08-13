"""Posting boundary for field estimates, commitments, accruals, actuals, and forecasts."""

from typing import Never

from app.domain.cost_control.types import CostPostingInput


def post_cost_batch(batch: CostPostingInput) -> Never:
    """Business rule to be confirmed during Excel/business-rule discovery."""

    del batch
    raise NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")
