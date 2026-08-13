"""Costing orchestration placeholder."""

from typing import Never

from app.domain.costing.types import EstimateInput


def calculate_estimate(estimate: EstimateInput) -> Never:
    """Business rule to be confirmed during Excel/business-rule discovery."""

    del estimate
    raise NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")
