"""Bulk-first master-data routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.master_data import (
    BulkCreateRequest,
    BulkUpdateRequest,
    BulkValidationResult,
    MasterDataCreate,
    MasterDataRead,
    MasterDataUpdate,
    PageResponse,
)
from app.services.master_data import MasterDataService

router = APIRouter(prefix="/master-data", tags=["master data"])


def _service(session: Session, entity: str, current_user: CurrentUser) -> MasterDataService:
    return MasterDataService(session, entity, current_user.id)


@router.get("/{entity}", response_model=PageResponse)
def list_records(
    entity: str,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    search: str | None = None,
    is_active: bool | None = None,
    sort_by: str = "code",
    sort_order: str = "asc",
) -> PageResponse:
    return _service(session, entity, current_user).list_page(
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/{entity}/bulk/validate", response_model=BulkValidationResult)
def validate_records(
    entity: str,
    payload: BulkCreateRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> BulkValidationResult:
    return _service(session, entity, current_user).validate_bulk(payload.rows)


@router.post("/{entity}/bulk/create", response_model=list[MasterDataRead], status_code=201)
def bulk_create_records(
    entity: str,
    payload: BulkCreateRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> list[MasterDataRead]:
    return _service(session, entity, current_user).bulk_create(payload.rows)


@router.patch("/{entity}/bulk/update", response_model=list[MasterDataRead])
def bulk_update_records(
    entity: str,
    payload: BulkUpdateRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> list[MasterDataRead]:
    rows = [
        (
            row.id,
            MasterDataUpdate.model_validate(row.model_dump(exclude={"id"}, exclude_unset=True)),
        )
        for row in payload.rows
    ]
    return _service(session, entity, current_user).bulk_update(rows)


@router.get("/{entity}/{item_id}", response_model=MasterDataRead)
def get_record(
    entity: str,
    item_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> MasterDataRead:
    return _service(session, entity, current_user).get(item_id)


@router.post("/{entity}", response_model=MasterDataRead, status_code=201)
def create_record(
    entity: str,
    payload: MasterDataCreate,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> MasterDataRead:
    return _service(session, entity, current_user).create(payload)


@router.patch("/{entity}/{item_id}", response_model=MasterDataRead)
def update_record(
    entity: str,
    item_id: UUID,
    payload: MasterDataUpdate,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> MasterDataRead:
    return _service(session, entity, current_user).update(item_id, payload)


@router.delete("/{entity}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_record(
    entity: str,
    item_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    _service(session, entity, current_user).deactivate(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
