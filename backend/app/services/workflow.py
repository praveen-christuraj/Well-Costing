"""Estimate review workflow orchestration with pending-policy safeguards."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthorizationError,
    BusinessValidationError,
    NotFoundError,
    WorkflowProfilePendingError,
)
from app.domain.workflow.state_machine import evaluate_transition
from app.domain.workflow.types import (
    WorkflowProfileDefinition,
    WorkflowStateDefinition,
    WorkflowTransitionDefinition,
)
from app.models.estimates import CostEstimate, EstimateVersion
from app.models.user import User
from app.models.workflow import (
    EstimateReviewComment,
    EstimateWorkflowInstance,
    WorkflowProfile,
    WorkflowTransitionAttempt,
)
from app.models.workflow import (
    WorkflowTransitionDefinition as WorkflowTransitionDefinitionModel,
)
from app.schemas.workflow import (
    EstimateReviewCommentCreate,
    EstimateReviewCommentRead,
    EstimateWorkflowStatus,
    WorkflowProfileRead,
    WorkflowStateRead,
    WorkflowTransitionAttemptRead,
    WorkflowTransitionRead,
    WorkflowTransitionRequest,
)

WORKFLOW_RECORD_TYPE = "estimate_version"
WORKFLOW_POLICY_VERSION = "pending-estimate-review"
PENDING_WORKFLOW_REQUIREMENTS = [
    "approved estimate review states and display labels",
    "permitted transition graph and transition prerequisites",
    "reviewer and approver role mappings, delegation, and separation of duties",
    "calculation and validation checks required before each transition",
    "rejection, revision, resubmission, and comment afes",
    "profile publication, effective-date, retirement, and migration policy",
]


class EstimateWorkflowService:
    def __init__(self, session: Session, actor: User) -> None:
        self.session, self.actor = session, actor

    def list_profiles(self) -> list[WorkflowProfileRead]:
        profiles = list(
            self.session.scalars(
                select(WorkflowProfile)
                .where(WorkflowProfile.record_type == WORKFLOW_RECORD_TYPE)
                .order_by(WorkflowProfile.code, WorkflowProfile.version_number.desc())
            ).all()
        )
        return [self._profile_read(profile) for profile in profiles]

    def status(self, estimate_id: UUID, version_id: UUID | None = None) -> EstimateWorkflowStatus:
        estimate, version = self._estimate_version(estimate_id, version_id)
        profile = self._published_profile()
        instance = self.session.scalar(
            select(EstimateWorkflowInstance).where(
                EstimateWorkflowInstance.estimate_version_id == version.id
            )
        )
        attempts = list(
            self.session.scalars(
                select(WorkflowTransitionAttempt)
                .where(WorkflowTransitionAttempt.estimate_version_id == version.id)
                .order_by(WorkflowTransitionAttempt.created_at.desc())
            ).all()
        )
        comments = self._comments(version.id)
        current_state = instance.current_state_key if instance else self._initial_state(profile)
        available = (
            [
                self._transition_read(transition)
                for transition in sorted(profile.transitions, key=lambda item: item.sort_order)
                if transition.from_state_key == current_state
            ]
            if profile is not None and current_state is not None
            else []
        )
        if profile is None:
            workflow_status = "profile_pending"
        elif instance is None:
            workflow_status = "not_started"
        else:
            workflow_status = "active"
        return EstimateWorkflowStatus(
            estimate_id=estimate.id,
            estimate_version_id=version.id,
            version_number=version.version_number,
            workflow_status=workflow_status,
            profile=self._profile_read(profile) if profile else None,
            current_state_key=current_state,
            available_actions=available,
            transition_attempts=[
                WorkflowTransitionAttemptRead.model_validate(attempt) for attempt in attempts
            ],
            review_comments=[
                EstimateReviewCommentRead.model_validate(comment) for comment in comments
            ],
            pending_requirements=(PENDING_WORKFLOW_REQUIREMENTS if profile is None else []),
        )

    def request_transition(
        self, estimate_id: UUID, request: WorkflowTransitionRequest
    ) -> EstimateWorkflowStatus:
        estimate, version = self._estimate_version(estimate_id, request.version_id)
        profile = self._published_profile()
        instance = self.session.scalar(
            select(EstimateWorkflowInstance).where(
                EstimateWorkflowInstance.estimate_version_id == version.id
            )
        )
        current_state = instance.current_state_key if instance else self._initial_state(profile)
        role_names = frozenset(role.name for role in self.actor.roles if role.is_active)
        attempt = WorkflowTransitionAttempt(
            estimate_version_id=version.id,
            workflow_instance_id=instance.id if instance else None,
            workflow_profile_id=profile.id if profile else None,
            requested_action=request.action_key,
            from_state_key=current_state,
            status="blocked",
            context_snapshot={
                "estimate_id": str(estimate.id),
                "estimate_version_id": str(version.id),
                "version_number": version.version_number,
                "requested_action": request.action_key,
                "actor_role_names": sorted(role_names),
                "workflow_policy_version": WORKFLOW_POLICY_VERSION,
            },
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )
        self.session.add(attempt)
        self.session.flush()
        try:
            evaluation = evaluate_transition(
                self._domain_profile(profile) if profile else None,
                current_state or "",
                request.action_key,
                role_names,
                request.comment,
            )
        except NotImplementedError as exc:
            attempt.message = str(exc)
            self.session.commit()
            raise WorkflowProfilePendingError(
                "Estimate workflow transition is blocked pending an approved "
                "profile and role mappings",
                {
                    "transition_attempt_id": str(attempt.id),
                    "workflow_policy_version": WORKFLOW_POLICY_VERSION,
                    "pending_requirements": PENDING_WORKFLOW_REQUIREMENTS,
                },
            ) from exc
        attempt.to_state_key = evaluation.to_state_key
        if not evaluation.allowed:
            attempt.status = "denied"
            attempt.message = evaluation.reason_code
            self.session.commit()
            if evaluation.reason_code == "role_not_mapped":
                raise AuthorizationError("The current actor is not mapped to this transition")
            raise BusinessValidationError(
                "The requested workflow transition is not allowed",
                {"reason_code": evaluation.reason_code, "transition_attempt_id": str(attempt.id)},
            )
        if profile is None or evaluation.to_state_key is None:
            raise RuntimeError(
                "Allowed transition is missing its configured profile or target state"
            )
        if instance is None:
            instance = EstimateWorkflowInstance(
                estimate_version_id=version.id,
                workflow_profile_id=profile.id,
                current_state_key=evaluation.to_state_key,
                created_by=self.actor.id,
                updated_by=self.actor.id,
            )
            self.session.add(instance)
            self.session.flush()
            attempt.workflow_instance_id = instance.id
        else:
            instance.current_state_key = evaluation.to_state_key
            instance.updated_by = self.actor.id
        attempt.status = "completed"
        attempt.message = "Configured transition completed"
        if request.comment:
            self.session.add(
                EstimateReviewComment(
                    estimate_version_id=version.id,
                    body=request.comment.strip(),
                    created_by=self.actor.id,
                    updated_by=self.actor.id,
                )
            )
        self.session.commit()
        return self.status(estimate_id, version.id)

    def add_comment(
        self, estimate_id: UUID, request: EstimateReviewCommentCreate
    ) -> EstimateReviewCommentRead:
        _estimate, version = self._estimate_version(estimate_id, request.version_id)
        body = request.body.strip()
        if not body:
            raise BusinessValidationError("Review comment cannot be blank")
        comment = EstimateReviewComment(
            estimate_version_id=version.id,
            body=body,
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )
        self.session.add(comment)
        self.session.commit()
        self.session.refresh(comment)
        return EstimateReviewCommentRead.model_validate(comment)

    def comments(
        self, estimate_id: UUID, version_id: UUID | None = None
    ) -> list[EstimateReviewCommentRead]:
        _estimate, version = self._estimate_version(estimate_id, version_id)
        return [
            EstimateReviewCommentRead.model_validate(comment)
            for comment in self._comments(version.id)
        ]

    def _estimate_version(
        self, estimate_id: UUID, version_id: UUID | None
    ) -> tuple[CostEstimate, EstimateVersion]:
        estimate = self.session.get(CostEstimate, estimate_id)
        if estimate is None:
            raise NotFoundError("Estimate not found")
        if version_id is None:
            version = next(
                (
                    item
                    for item in estimate.versions
                    if item.version_number == estimate.current_version_number
                ),
                None,
            )
        else:
            version = next((item for item in estimate.versions if item.id == version_id), None)
        if version is None:
            raise NotFoundError("Estimate version not found")
        return estimate, version

    def _published_profile(self) -> WorkflowProfile | None:
        profiles = list(
            self.session.scalars(
                select(WorkflowProfile).where(
                    WorkflowProfile.record_type == WORKFLOW_RECORD_TYPE,
                    WorkflowProfile.lifecycle_status == "published",
                )
            ).all()
        )
        return profiles[0] if len(profiles) == 1 else None

    def _comments(self, version_id: UUID) -> list[EstimateReviewComment]:
        return list(
            self.session.scalars(
                select(EstimateReviewComment)
                .where(EstimateReviewComment.estimate_version_id == version_id)
                .order_by(EstimateReviewComment.created_at.desc())
            ).all()
        )

    @staticmethod
    def _initial_state(profile: WorkflowProfile | None) -> str | None:
        if profile is None:
            return None
        initial = [state.state_key for state in profile.states if state.is_initial]
        return initial[0] if len(initial) == 1 else None

    @staticmethod
    def _transition_read(
        transition: WorkflowTransitionDefinitionModel,
    ) -> WorkflowTransitionRead:
        return WorkflowTransitionRead(
            id=transition.id,
            action_key=transition.action_key,
            label=transition.label,
            from_state_key=transition.from_state_key,
            to_state_key=transition.to_state_key,
            sort_order=transition.sort_order,
            requires_comment=transition.requires_comment,
            allowed_role_names=sorted(mapping.role.name for mapping in transition.role_mappings),
        )

    def _profile_read(self, profile: WorkflowProfile) -> WorkflowProfileRead:
        return WorkflowProfileRead(
            id=profile.id,
            code=profile.code,
            name=profile.name,
            record_type=profile.record_type,
            version_number=profile.version_number,
            lifecycle_status=profile.lifecycle_status,
            description=profile.description,
            source_reference=profile.source_reference,
            effective_from=profile.effective_from,
            effective_to=profile.effective_to,
            states=[
                WorkflowStateRead.model_validate(state)
                for state in sorted(profile.states, key=lambda item: item.sort_order)
            ],
            transitions=[
                self._transition_read(transition)
                for transition in sorted(profile.transitions, key=lambda item: item.sort_order)
            ],
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            created_by=profile.created_by,
            updated_by=profile.updated_by,
        )

    @staticmethod
    def _domain_profile(profile: WorkflowProfile) -> WorkflowProfileDefinition:
        return WorkflowProfileDefinition(
            code=profile.code,
            version_number=profile.version_number,
            record_type=profile.record_type,
            lifecycle_status=profile.lifecycle_status,
            states=tuple(
                WorkflowStateDefinition(
                    key=state.state_key,
                    label=state.label,
                    is_initial=state.is_initial,
                    is_terminal=state.is_terminal,
                )
                for state in sorted(profile.states, key=lambda item: item.sort_order)
            ),
            transitions=tuple(
                WorkflowTransitionDefinition(
                    action_key=transition.action_key,
                    label=transition.label,
                    from_state_key=transition.from_state_key,
                    to_state_key=transition.to_state_key,
                    allowed_role_names=frozenset(
                        mapping.role.name for mapping in transition.role_mappings
                    ),
                    requires_comment=transition.requires_comment,
                )
                for transition in sorted(profile.transitions, key=lambda item: item.sort_order)
            ),
        )
