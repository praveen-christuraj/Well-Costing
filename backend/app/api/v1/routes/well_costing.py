"""Well rate-book and out-of-AFE routes.

Every path is scoped to one well: a rate only ever exists in the context of the
well that negotiated it, which is what keeps twenty concurrently drilling rigs
independent of central rate revisions.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.master_data import PageResponse
from app.schemas.well_costing import (
    AvailableServiceRead,
    AvailableTangibleRead,
    RateBookLockRequest,
    RateBookLockResult,
    WellCostExposureRead,
    WellServiceRateCreate,
    WellServiceRateRead,
    WellServiceRateUpdate,
    WellTangibleRateCreate,
    WellTangibleRateRead,
    WellTangibleRateUpdate,
    WellUnplannedDecision,
    WellUnplannedItemCreate,
    WellUnplannedItemRead,
    WellUnplannedItemUpdate,
)
from app.services.well_costing import (
    WellCostExposureService,
    WellRateBookService,
    WellUnplannedItemService,
)

router = APIRouter(prefix="/wells/{well_id}", tags=["well rate book"])

SessionDep = Annotated[Session, Depends(get_db)]
PageQuery = Annotated[int, Query(ge=1)]
SizeQuery = Annotated[int, Query(ge=1, le=500)]


def _book(session: Session, user: CurrentUser) -> WellRateBookService:
    return WellRateBookService(session, user.id)


def _unplanned(session: Session, user: CurrentUser) -> WellUnplannedItemService:
    return WellUnplannedItemService(session, user.id)


# ------------------------------------------------------------------ catalogue
@router.get("/rate-book/available-services", response_model=list[AvailableServiceRead])
def available_services(
    well_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    search: str | None = None,
) -> list[AvailableServiceRead]:
    """Master services, flagged with whether this well already prices them."""

    return _book(session, current_user).available_services(well_id, search=search)


@router.get("/rate-book/available-tangibles", response_model=list[AvailableTangibleRead])
def available_tangibles(
    well_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    search: str | None = None,
) -> list[AvailableTangibleRead]:
    """Master tangibles with the master rate that would be copied into the well."""

    return _book(session, current_user).available_tangibles(well_id, search=search)


# ------------------------------------------------------------------- services
@router.get("/rate-book/services", response_model=PageResponse)
def list_well_services(
    well_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    page: PageQuery = 1,
    page_size: SizeQuery = 50,
    search: str | None = None,
    is_active: bool | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    origin: str | None = None,
) -> PageResponse:
    return _book(session, current_user).list_services(
        well_id,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        status=status_filter,
        origin=origin,
    )


@router.post("/rate-book/services", response_model=WellServiceRateRead, status_code=201)
def add_well_service(
    well_id: UUID,
    payload: WellServiceRateCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> WellServiceRateRead:
    """Add a master service to the well at the rate negotiated for this well."""

    return _book(session, current_user).add_service(well_id, payload)


@router.patch("/rate-book/services/{rate_id}", response_model=WellServiceRateRead)
def update_well_service(
    well_id: UUID,
    rate_id: UUID,
    payload: WellServiceRateUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> WellServiceRateRead:
    """Revise a well service rate before the AFE locks it; a reason is required."""

    return _book(session, current_user).update_service(well_id, rate_id, payload)


@router.delete("/rate-book/services/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_well_service(
    well_id: UUID,
    rate_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    reason: str | None = None,
) -> Response:
    _book(session, current_user).remove_service(well_id, rate_id, reason=reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ tangibles
@router.get("/rate-book/tangibles", response_model=PageResponse)
def list_well_tangibles(
    well_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    page: PageQuery = 1,
    page_size: SizeQuery = 50,
    search: str | None = None,
    is_active: bool | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    origin: str | None = None,
) -> PageResponse:
    return _book(session, current_user).list_tangibles(
        well_id,
        page=page,
        page_size=page_size,
        search=search,
        is_active=is_active,
        status=status_filter,
        origin=origin,
    )


@router.post("/rate-book/tangibles", response_model=WellTangibleRateRead, status_code=201)
def add_well_tangible(
    well_id: UUID,
    payload: WellTangibleRateCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> WellTangibleRateRead:
    """Copy the current master tangible rate into the well, or override it."""

    return _book(session, current_user).add_tangible(well_id, payload)


@router.patch("/rate-book/tangibles/{rate_id}", response_model=WellTangibleRateRead)
def update_well_tangible(
    well_id: UUID,
    rate_id: UUID,
    payload: WellTangibleRateUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> WellTangibleRateRead:
    """Revise a well tangible rate before the AFE locks it; a reason is required."""

    return _book(session, current_user).update_tangible(well_id, rate_id, payload)


@router.delete("/rate-book/tangibles/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_well_tangible(
    well_id: UUID,
    rate_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    reason: str | None = None,
) -> Response:
    _book(session, current_user).remove_tangible(well_id, rate_id, reason=reason)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------ lock and history
@router.post("/rate-book/lock", response_model=RateBookLockResult)
def lock_rate_book(
    well_id: UUID,
    payload: RateBookLockRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> RateBookLockResult:
    """Freeze the well's rates, typically when the AFE baseline is issued."""

    return _book(session, current_user).lock(well_id, payload)


@router.get("/rate-book/revisions", response_model=PageResponse)
def list_rate_revisions(
    well_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    page: PageQuery = 1,
    page_size: SizeQuery = 50,
    scope: str | None = None,
) -> PageResponse:
    """Every add, revision, lock, and withdrawal in this well's rate book."""

    return _book(session, current_user).revisions(
        well_id, page=page, page_size=page_size, scope=scope
    )


# ----------------------------------------------------------- out-of-AFE register
@router.get("/unplanned-items", response_model=PageResponse)
def list_unplanned_items(
    well_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    page: PageQuery = 1,
    page_size: SizeQuery = 50,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    item_kind: str | None = None,
    search: str | None = None,
) -> PageResponse:
    return _unplanned(session, current_user).list_items(
        well_id,
        page=page,
        page_size=page_size,
        status=status_filter,
        item_kind=item_kind,
        search=search,
    )


@router.post("/unplanned-items", response_model=WellUnplannedItemRead, status_code=201)
def create_unplanned_item(
    well_id: UUID,
    payload: WellUnplannedItemCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> WellUnplannedItemRead:
    """Record a charge incurred outside the approved AFE and the well plan."""

    return _unplanned(session, current_user).create(well_id, payload)


@router.get("/unplanned-items/{item_id}", response_model=WellUnplannedItemRead)
def get_unplanned_item(
    well_id: UUID, item_id: UUID, current_user: CurrentUser, session: SessionDep
) -> WellUnplannedItemRead:
    return _unplanned(session, current_user).get(well_id, item_id)


@router.patch("/unplanned-items/{item_id}", response_model=WellUnplannedItemRead)
def update_unplanned_item(
    well_id: UUID,
    item_id: UUID,
    payload: WellUnplannedItemUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> WellUnplannedItemRead:
    return _unplanned(session, current_user).update(well_id, item_id, payload)


@router.post("/unplanned-items/{item_id}/submit", response_model=WellUnplannedItemRead)
def submit_unplanned_item(
    well_id: UUID, item_id: UUID, current_user: CurrentUser, session: SessionDep
) -> WellUnplannedItemRead:
    return _unplanned(session, current_user).submit(well_id, item_id)


@router.post("/unplanned-items/{item_id}/approve", response_model=WellUnplannedItemRead)
def approve_unplanned_item(
    well_id: UUID,
    item_id: UUID,
    payload: WellUnplannedDecision,
    current_user: CurrentUser,
    session: SessionDep,
) -> WellUnplannedItemRead:
    """Approve the deviation and price it into the well rate book."""

    return _unplanned(session, current_user).approve(well_id, item_id, payload)


@router.post("/unplanned-items/{item_id}/reject", response_model=WellUnplannedItemRead)
def reject_unplanned_item(
    well_id: UUID,
    item_id: UUID,
    payload: WellUnplannedDecision,
    current_user: CurrentUser,
    session: SessionDep,
) -> WellUnplannedItemRead:
    return _unplanned(session, current_user).reject(well_id, item_id, payload)


@router.post("/unplanned-items/{item_id}/cancel", response_model=WellUnplannedItemRead)
def cancel_unplanned_item(
    well_id: UUID,
    item_id: UUID,
    payload: WellUnplannedDecision,
    current_user: CurrentUser,
    session: SessionDep,
) -> WellUnplannedItemRead:
    return _unplanned(session, current_user).cancel(well_id, item_id, payload)


@router.get("/cost-exposure", response_model=WellCostExposureRead)
def cost_exposure(
    well_id: UUID, current_user: CurrentUser, session: SessionDep
) -> WellCostExposureRead:
    """Approved AFE, approved out-of-AFE spend, pending requests, and variance."""

    return WellCostExposureService(session, current_user.id).summary(well_id)
