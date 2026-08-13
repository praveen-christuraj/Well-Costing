"""Effective-dated rate CRUD and bulk routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.master_data import (
    BulkValidationResult,
    PageResponse,
    RateBulkCreateRequest,
    RateBulkUpdateRequest,
    RateCreate,
    RateRead,
    RateUpdate,
)
from app.services.master_data import RateService

router = APIRouter(prefix="/master-data/rates", tags=["rates"])


@router.get("", response_model=PageResponse)
def list_rates(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    search: str | None = None,
    is_active: bool | None = None,
    sort_by: str = "effective_from",
    sort_order: str = "desc",
) -> PageResponse:
    return RateService(session, current_user.id).list_page(
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/bulk/validate", response_model=BulkValidationResult)
def validate_rates(
    payload: RateBulkCreateRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> BulkValidationResult:
    return RateService(session, current_user.id).validate_bulk(payload.rows)


@router.post("/bulk/create", response_model=list[RateRead], status_code=201)
def bulk_create_rates(
    payload: RateBulkCreateRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> list[RateRead]:
    return RateService(session, current_user.id).bulk_create(payload.rows)


@router.patch("/bulk/update", response_model=list[RateRead])
def bulk_update_rates(
    payload: RateBulkUpdateRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> list[RateRead]:
    rows = [
        (
            row.id,
            RateUpdate.model_validate(row.model_dump(exclude={"id"}, exclude_unset=True)),
        )
        for row in payload.rows
    ]
    return RateService(session, current_user.id).bulk_update(rows)


@router.get("/{rate_id}", response_model=RateRead)
def get_rate(
    rate_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> RateRead:
    return RateService(session, current_user.id).get(rate_id)


@router.post("", response_model=RateRead, status_code=201)
def create_rate(
    payload: RateCreate,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> RateRead:
    return RateService(session, current_user.id).create(payload)


@router.patch("/{rate_id}", response_model=RateRead)
def update_rate(
    rate_id: UUID,
    payload: RateUpdate,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> RateRead:
    return RateService(session, current_user.id).update(rate_id, payload)


@router.delete("/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_rate(
    rate_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    RateService(session, current_user.id).deactivate(rate_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
