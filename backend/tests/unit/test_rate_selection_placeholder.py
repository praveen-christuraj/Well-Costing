"""Unconfirmed automatic rate selection remains explicit."""

from uuid import uuid4

import pytest
from app.services.estimates import CostEstimateService
from sqlalchemy.orm import Session


def test_automatic_rate_selection_is_not_guessed(db_session: Session) -> None:
    with pytest.raises(
        NotImplementedError,
        match="Business rule to be confirmed during Excel/business-rule discovery",
    ):
        CostEstimateService(db_session, uuid4()).resolve_default_rate(uuid4())
