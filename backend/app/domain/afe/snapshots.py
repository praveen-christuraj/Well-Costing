"""Baseline AFE snapshot creation boundary."""

from typing import Never

from app.domain.afe.types import BaselineAfeInput


def create_baseline_afe_snapshot(source: BaselineAfeInput) -> Never:
    """Business rule to be confirmed during Excel/business-rule discovery."""

    del source
    raise NotImplementedError("Business rule to be confirmed during Excel/business-rule discovery.")
