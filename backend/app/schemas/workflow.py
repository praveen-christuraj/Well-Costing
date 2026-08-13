"""Phase 6 workflow profile, transition audit, and review-comment API contracts."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkflowStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state_key: str
    label: str
    sort_order: int
    is_initial: bool
    is_terminal: bool


class WorkflowTransitionRead(BaseModel):
    id: UUID
    action_key: str
    label: str
    from_state_key: str
    to_state_key: str
    sort_order: int
    requires_comment: bool
    allowed_role_names: list[str]


class WorkflowProfileRead(BaseModel):
    id: UUID
    code: str
    name: str
    record_type: str
    version_number: int
    lifecycle_status: str
    description: str | None
    source_reference: str | None
    effective_from: date | None
    effective_to: date | None
    states: list[WorkflowStateRead]
    transitions: list[WorkflowTransitionRead]
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class WorkflowTransitionAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    estimate_version_id: UUID
    workflow_instance_id: UUID | None
    workflow_profile_id: UUID | None
    requested_action: str
    from_state_key: str | None
    to_state_key: str | None
    status: str
    message: str | None
    context_snapshot: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class EstimateReviewCommentCreate(BaseModel):
    version_id: UUID | None = None
    body: str = Field(min_length=1, max_length=10_000)


class EstimateReviewCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    estimate_version_id: UUID
    body: str
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None


class WorkflowTransitionRequest(BaseModel):
    version_id: UUID | None = None
    action_key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_-]+$")
    comment: str | None = Field(default=None, max_length=10_000)


class EstimateWorkflowStatus(BaseModel):
    estimate_id: UUID
    estimate_version_id: UUID
    version_number: int
    workflow_status: str
    profile: WorkflowProfileRead | None
    current_state_key: str | None
    available_actions: list[WorkflowTransitionRead]
    transition_attempts: list[WorkflowTransitionAttemptRead]
    review_comments: list[EstimateReviewCommentRead]
    pending_requirements: list[str]
