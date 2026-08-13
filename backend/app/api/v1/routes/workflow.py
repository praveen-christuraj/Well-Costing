"""Phase 6 estimate review workflow and immutable comment routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.workflow import (
    EstimateReviewCommentCreate,
    EstimateReviewCommentRead,
    EstimateWorkflowStatus,
    WorkflowProfileRead,
    WorkflowTransitionRequest,
)
from app.services.workflow import EstimateWorkflowService

router = APIRouter(tags=["review workflow"])


@router.get("/workflow/profiles", response_model=list[WorkflowProfileRead])
def list_workflow_profiles(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> list[WorkflowProfileRead]:
    return EstimateWorkflowService(session, current_user).list_profiles()


@router.get("/estimates/{estimate_id}/workflow", response_model=EstimateWorkflowStatus)
def get_estimate_workflow(
    estimate_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    version_id: Annotated[UUID | None, Query()] = None,
) -> EstimateWorkflowStatus:
    return EstimateWorkflowService(session, current_user).status(estimate_id, version_id)


@router.post(
    "/estimates/{estimate_id}/workflow/transitions",
    response_model=EstimateWorkflowStatus,
)
def request_estimate_transition(
    estimate_id: UUID,
    request: WorkflowTransitionRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> EstimateWorkflowStatus:
    return EstimateWorkflowService(session, current_user).request_transition(estimate_id, request)


@router.get(
    "/estimates/{estimate_id}/review-comments",
    response_model=list[EstimateReviewCommentRead],
)
def list_review_comments(
    estimate_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    version_id: Annotated[UUID | None, Query()] = None,
) -> list[EstimateReviewCommentRead]:
    return EstimateWorkflowService(session, current_user).comments(estimate_id, version_id)


@router.post(
    "/estimates/{estimate_id}/review-comments",
    response_model=EstimateReviewCommentRead,
    status_code=status.HTTP_201_CREATED,
)
def add_review_comment(
    estimate_id: UUID,
    request: EstimateReviewCommentCreate,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> EstimateReviewCommentRead:
    return EstimateWorkflowService(session, current_user).add_comment(estimate_id, request)
