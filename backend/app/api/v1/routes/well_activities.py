"""Well-scoped sub-activity routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.services.well_activities import (
    WellActivityCreate,
    WellActivityRead,
    WellActivityService,
    WellActivityUpdate,
)

router = APIRouter(prefix="/well-activities", tags=["well activities"])


def _service(session: Session, current_user: CurrentUser) -> WellActivityService:
    return WellActivityService(session, current_user.id)


@router.get("/well/{well_id}", response_model=list[WellActivityRead])
def list_well_activities(
    well_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> list[WellActivityRead]:
    return _service(session, current_user).list_for_well(well_id)


@router.post("", response_model=WellActivityRead, status_code=201)
def create_well_activity(
    payload: WellActivityCreate,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> WellActivityRead:
    return _service(session, current_user).create(payload)


@router.patch("/{item_id}", response_model=WellActivityRead)
def update_well_activity(
    item_id: UUID,
    payload: WellActivityUpdate,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> WellActivityRead:
    return _service(session, current_user).update(item_id, payload)


@router.delete("/{item_id}", status_code=204)
def delete_well_activity(
    item_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> None:
    _service(session, current_user).delete(item_id)
