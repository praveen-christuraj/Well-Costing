"""Pure structural state-machine evaluation; organization policy remains configuration."""

from app.domain.workflow.types import (
    TransitionEvaluation,
    WorkflowProfileDefinition,
)


def evaluate_transition(
    profile: WorkflowProfileDefinition | None,
    current_state_key: str,
    action_key: str,
    actor_role_names: frozenset[str],
    comment: str | None = None,
) -> TransitionEvaluation:
    """Business rule to be confirmed during Excel/business-rule discovery."""

    if profile is None or profile.lifecycle_status != "published":
        raise NotImplementedError(
            "Business rule to be confirmed during Excel/business-rule discovery."
        )
    transition = next(
        (
            item
            for item in profile.transitions
            if item.from_state_key == current_state_key and item.action_key == action_key
        ),
        None,
    )
    if transition is None:
        return TransitionEvaluation(
            allowed=False,
            reason_code="transition_not_configured",
            from_state_key=current_state_key,
            to_state_key=None,
            action_key=action_key,
        )
    if not transition.allowed_role_names:
        raise NotImplementedError(
            "Business rule to be confirmed during Excel/business-rule discovery."
        )
    if actor_role_names.isdisjoint(transition.allowed_role_names):
        return TransitionEvaluation(
            allowed=False,
            reason_code="role_not_mapped",
            from_state_key=current_state_key,
            to_state_key=transition.to_state_key,
            action_key=action_key,
        )
    if transition.requires_comment and not comment:
        return TransitionEvaluation(
            allowed=False,
            reason_code="comment_required",
            from_state_key=current_state_key,
            to_state_key=transition.to_state_key,
            action_key=action_key,
        )
    return TransitionEvaluation(
        allowed=True,
        reason_code="allowed",
        from_state_key=current_state_key,
        to_state_key=transition.to_state_key,
        action_key=action_key,
    )
