"""Pure Phase 6 state-machine framework tests with synthetic configuration."""

import pytest
from app.domain.workflow.state_machine import evaluate_transition
from app.domain.workflow.types import (
    WorkflowProfileDefinition,
    WorkflowStateDefinition,
    WorkflowTransitionDefinition,
)


def synthetic_profile() -> WorkflowProfileDefinition:
    return WorkflowProfileDefinition(
        code="test-only",
        version_number=1,
        record_type="estimate_version",
        lifecycle_status="published",
        states=(
            WorkflowStateDefinition(key="one", label="One", is_initial=True),
            WorkflowStateDefinition(key="two", label="Two", is_terminal=True),
        ),
        transitions=(
            WorkflowTransitionDefinition(
                action_key="advance",
                label="Advance",
                from_state_key="one",
                to_state_key="two",
                allowed_role_names=frozenset({"test-approver"}),
                requires_comment=True,
            ),
        ),
    )


def test_missing_authoritative_profile_fails_loudly() -> None:
    with pytest.raises(
        NotImplementedError,
        match=r"Business rule to be confirmed during Excel/business-rule discovery\.",
    ):
        evaluate_transition(None, "", "submit", frozenset())


def test_synthetic_profile_structurally_evaluates_role_and_comment() -> None:
    missing_comment = evaluate_transition(
        synthetic_profile(), "one", "advance", frozenset({"test-approver"})
    )
    assert missing_comment.allowed is False
    assert missing_comment.reason_code == "comment_required"

    allowed = evaluate_transition(
        synthetic_profile(),
        "one",
        "advance",
        frozenset({"test-approver"}),
        "Test-only explanation",
    )
    assert allowed.allowed is True
    assert allowed.to_state_key == "two"

    denied = evaluate_transition(
        synthetic_profile(), "one", "advance", frozenset({"test-viewer"}), "Reason"
    )
    assert denied.allowed is False
    assert denied.reason_code == "role_not_mapped"
