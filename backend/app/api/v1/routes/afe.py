"""Phase 7 immutable baseline AFE snapshot routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.afe import AfeSnapshotCreateRequest, AfeSnapshotRead, EstimateAfeStatus
from app.services.afe import EstimateAfeService

router = APIRouter(tags=["AFE snapshots"])


@router.get("/estimates/{estimate_id}/afe", response_model=EstimateAfeStatus)
def get_estimate_afe_status(
    estimate_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    version_id: Annotated[UUID | None, Query()] = None,
) -> EstimateAfeStatus:
    return EstimateAfeService(session, current_user).status(estimate_id, version_id)


@router.post(
    "/estimates/{estimate_id}/afe/snapshots",
    response_model=EstimateAfeStatus,
)
def create_baseline_afe_snapshot(
    estimate_id: UUID,
    request: AfeSnapshotCreateRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> EstimateAfeStatus:
    return EstimateAfeService(session, current_user).create_baseline(estimate_id, request)


@router.get("/afes/{snapshot_id}", response_model=AfeSnapshotRead)
def get_afe_snapshot(
    snapshot_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> AfeSnapshotRead:
    return EstimateAfeService(session, current_user).get_snapshot(snapshot_id)
