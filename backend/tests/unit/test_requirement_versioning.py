"""Unconfirmed requirement revision behavior must fail loudly."""

from uuid import uuid4

import pytest
from app.services.requirements import RequirementService
from sqlalchemy.orm import Session


def test_requirement_revision_rule_is_not_guessed(db_session: Session) -> None:
    service = RequirementService(db_session, uuid4())
    with pytest.raises(
        NotImplementedError,
        match="Business rule to be confirmed during Excel/business-rule discovery",
    ):
        service.create_revision(uuid4())
