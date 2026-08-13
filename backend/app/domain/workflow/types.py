"""Pure contracts for versioned workflow profiles and transition evaluation."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowStateDefinition:
    key: str
    label: str
    is_initial: bool = False
    is_terminal: bool = False


@dataclass(frozen=True)
class WorkflowTransitionDefinition:
    action_key: str
    label: str
    from_state_key: str
    to_state_key: str
    allowed_role_names: frozenset[str] = field(default_factory=lambda: frozenset[str]())
    requires_comment: bool = False


@dataclass(frozen=True)
class WorkflowProfileDefinition:
    code: str
    version_number: int
    record_type: str
    lifecycle_status: str
    states: tuple[WorkflowStateDefinition, ...]
    transitions: tuple[WorkflowTransitionDefinition, ...]


@dataclass(frozen=True)
class TransitionEvaluation:
    allowed: bool
    reason_code: str
    from_state_key: str
    to_state_key: str | None
    action_key: str
