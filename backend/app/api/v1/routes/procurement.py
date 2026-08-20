"""Routes for service orders, purchase orders, and master item rates.

Master rates cover tangibles and consumables. Services are priced per well on
``/wells/{well_id}/rate-book/services``.
"""

from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.master_data import BulkValidationResult, PageResponse
from app.schemas.procurement import (
    ItemPriceBulkCreateRequest,
    ItemPriceBulkUpdateRequest,
    ItemPriceCreate,
    ItemPriceRead,
    ItemPriceReviseRequest,
    ItemPriceUpdate,
    PurchaseOrderBulkCreateRequest,
    PurchaseOrderBulkUpdateRequest,
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderUpdate,
    ServiceOrderBulkCreateRequest,
    ServiceOrderBulkUpdateRequest,
    ServiceOrderCreate,
    ServiceOrderRead,
    ServiceOrderUpdate,
)
from app.services.procurement import (
    ItemPriceService,
    PurchaseOrderService,
    ServiceOrderService,
)

router = APIRouter(prefix="/procurement", tags=["procurement"])

SessionDep = Annotated[Session, Depends(get_db)]
PageQuery = Annotated[int, Query(ge=1)]
SizeQuery = Annotated[int, Query(ge=1, le=500)]


def _bulk_rows(rows: list[Any], update_model: type[Any]) -> list[tuple[UUID, Any]]:
    return [
        (
            row.id,
            update_model.model_validate(row.model_dump(exclude={"id"}, exclude_unset=True)),
        )
        for row in rows
    ]


# --------------------------------------------------------------------------- service orders
@router.get("/service-orders", response_model=PageResponse)
def list_service_orders(
    current_user: CurrentUser,
    session: SessionDep,
    page: PageQuery = 1,
    page_size: SizeQuery = 25,
    search: str | None = None,
    is_active: bool | None = None,
    vendor_id: UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    valid_on: date | None = None,
    sort_by: str = "order_number",
    sort_order: str = "asc",
) -> PageResponse:
    return ServiceOrderService(session, current_user.id).list_page(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        is_active=is_active,
        vendor_id=vendor_id,
        status=status_filter,
        valid_on=valid_on,
    )


@router.post("/service-orders", response_model=ServiceOrderRead, status_code=201)
def create_service_order(
    payload: ServiceOrderCreate, current_user: CurrentUser, session: SessionDep
) -> ServiceOrderRead:
    return ServiceOrderService(session, current_user.id).create(payload)


@router.post("/service-orders/bulk/validate", response_model=BulkValidationResult)
def validate_service_orders(
    payload: ServiceOrderBulkCreateRequest, current_user: CurrentUser, session: SessionDep
) -> BulkValidationResult:
    return ServiceOrderService(session, current_user.id).validate_bulk(payload.rows)


@router.post("/service-orders/bulk/create", response_model=list[ServiceOrderRead], status_code=201)
def bulk_create_service_orders(
    payload: ServiceOrderBulkCreateRequest, current_user: CurrentUser, session: SessionDep
) -> list[ServiceOrderRead]:
    return ServiceOrderService(session, current_user.id).bulk_create(payload.rows)


@router.patch("/service-orders/bulk/update", response_model=list[ServiceOrderRead])
def bulk_update_service_orders(
    payload: ServiceOrderBulkUpdateRequest, current_user: CurrentUser, session: SessionDep
) -> list[ServiceOrderRead]:
    return ServiceOrderService(session, current_user.id).bulk_update(
        _bulk_rows(payload.rows, ServiceOrderUpdate)
    )


@router.get("/service-orders/{record_id}", response_model=ServiceOrderRead)
def get_service_order(
    record_id: UUID, current_user: CurrentUser, session: SessionDep
) -> ServiceOrderRead:
    return ServiceOrderService(session, current_user.id).get(record_id)


@router.patch("/service-orders/{record_id}", response_model=ServiceOrderRead)
def update_service_order(
    record_id: UUID,
    payload: ServiceOrderUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> ServiceOrderRead:
    return ServiceOrderService(session, current_user.id).update(record_id, payload)


@router.delete("/service-orders/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_order(
    record_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    hard: bool = False,
) -> Response:
    service = ServiceOrderService(session, current_user.id)
    service.delete(record_id) if hard else service.deactivate(record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- purchase orders
@router.get("/purchase-orders", response_model=PageResponse)
def list_purchase_orders(
    current_user: CurrentUser,
    session: SessionDep,
    page: PageQuery = 1,
    page_size: SizeQuery = 25,
    search: str | None = None,
    is_active: bool | None = None,
    vendor_id: UUID | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    sort_by: str = "order_number",
    sort_order: str = "asc",
) -> PageResponse:
    return PurchaseOrderService(session, current_user.id).list_page(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        is_active=is_active,
        vendor_id=vendor_id,
        status=status_filter,
    )


@router.post("/purchase-orders", response_model=PurchaseOrderRead, status_code=201)
def create_purchase_order(
    payload: PurchaseOrderCreate, current_user: CurrentUser, session: SessionDep
) -> PurchaseOrderRead:
    return PurchaseOrderService(session, current_user.id).create(payload)


@router.post("/purchase-orders/bulk/validate", response_model=BulkValidationResult)
def validate_purchase_orders(
    payload: PurchaseOrderBulkCreateRequest, current_user: CurrentUser, session: SessionDep
) -> BulkValidationResult:
    return PurchaseOrderService(session, current_user.id).validate_bulk(payload.rows)


@router.post(
    "/purchase-orders/bulk/create", response_model=list[PurchaseOrderRead], status_code=201
)
def bulk_create_purchase_orders(
    payload: PurchaseOrderBulkCreateRequest, current_user: CurrentUser, session: SessionDep
) -> list[PurchaseOrderRead]:
    return PurchaseOrderService(session, current_user.id).bulk_create(payload.rows)


@router.patch("/purchase-orders/bulk/update", response_model=list[PurchaseOrderRead])
def bulk_update_purchase_orders(
    payload: PurchaseOrderBulkUpdateRequest, current_user: CurrentUser, session: SessionDep
) -> list[PurchaseOrderRead]:
    return PurchaseOrderService(session, current_user.id).bulk_update(
        _bulk_rows(payload.rows, PurchaseOrderUpdate)
    )


@router.get("/purchase-orders/{record_id}", response_model=PurchaseOrderRead)
def get_purchase_order(
    record_id: UUID, current_user: CurrentUser, session: SessionDep
) -> PurchaseOrderRead:
    return PurchaseOrderService(session, current_user.id).get(record_id)


@router.patch("/purchase-orders/{record_id}", response_model=PurchaseOrderRead)
def update_purchase_order(
    record_id: UUID,
    payload: PurchaseOrderUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> PurchaseOrderRead:
    return PurchaseOrderService(session, current_user.id).update(record_id, payload)


@router.delete("/purchase-orders/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase_order(
    record_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    hard: bool = False,
) -> Response:
    service = PurchaseOrderService(session, current_user.id)
    service.delete(record_id) if hard else service.deactivate(record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- item prices
@router.get("/item-prices", response_model=PageResponse)
def list_item_prices(
    current_user: CurrentUser,
    session: SessionDep,
    page: PageQuery = 1,
    page_size: SizeQuery = 25,
    search: str | None = None,
    is_active: bool | None = None,
    item_id: UUID | None = None,
    item_type: str | None = None,
    vendor_id: UUID | None = None,
    purchase_order_id: UUID | None = None,
    effective_on: date | None = None,
    sort_by: str = "effective_from",
    sort_order: str = "desc",
) -> PageResponse:
    return ItemPriceService(session, current_user.id).list_page(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        is_active=is_active,
        item_id=item_id,
        item_type=item_type,
        vendor_id=vendor_id,
        purchase_order_id=purchase_order_id,
        effective_on=effective_on,
    )


@router.post("/item-prices", response_model=ItemPriceRead, status_code=201)
def create_item_price(
    payload: ItemPriceCreate, current_user: CurrentUser, session: SessionDep
) -> ItemPriceRead:
    return ItemPriceService(session, current_user.id).create(payload)


@router.post("/item-prices/bulk/validate", response_model=BulkValidationResult)
def validate_item_prices(
    payload: ItemPriceBulkCreateRequest, current_user: CurrentUser, session: SessionDep
) -> BulkValidationResult:
    return ItemPriceService(session, current_user.id).validate_bulk(payload.rows)


@router.post("/item-prices/bulk/create", response_model=list[ItemPriceRead], status_code=201)
def bulk_create_item_prices(
    payload: ItemPriceBulkCreateRequest, current_user: CurrentUser, session: SessionDep
) -> list[ItemPriceRead]:
    return ItemPriceService(session, current_user.id).bulk_create(payload.rows)


@router.patch("/item-prices/bulk/update", response_model=list[ItemPriceRead])
def bulk_update_item_prices(
    payload: ItemPriceBulkUpdateRequest, current_user: CurrentUser, session: SessionDep
) -> list[ItemPriceRead]:
    return ItemPriceService(session, current_user.id).bulk_update(
        _bulk_rows(payload.rows, ItemPriceUpdate)
    )


@router.get("/item-prices/{record_id}", response_model=ItemPriceRead)
def get_item_price(
    record_id: UUID, current_user: CurrentUser, session: SessionDep
) -> ItemPriceRead:
    return ItemPriceService(session, current_user.id).get(record_id)


@router.patch("/item-prices/{record_id}", response_model=ItemPriceRead)
def update_item_price(
    record_id: UUID,
    payload: ItemPriceUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> ItemPriceRead:
    return ItemPriceService(session, current_user.id).update(record_id, payload)


@router.delete("/item-prices/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item_price(
    record_id: UUID,
    current_user: CurrentUser,
    session: SessionDep,
    hard: bool = False,
) -> Response:
    service = ItemPriceService(session, current_user.id)
    service.delete(record_id) if hard else service.deactivate(record_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/item-prices/{record_id}/revise", response_model=ItemPriceRead, status_code=201)
def revise_item_price(
    record_id: UUID,
    payload: ItemPriceReviseRequest,
    current_user: CurrentUser,
    session: SessionDep,
) -> ItemPriceRead:
    """Supersede a master rate, keeping the superseded row and its history.

    Wells that already copied the previous rate into their rate book are not
    affected: they keep the number they were planned with until completion.
    """

    return ItemPriceService(session, current_user.id).revise(record_id, payload)


@router.get("/rate-revisions", response_model=PageResponse)
def list_rate_revisions(
    current_user: CurrentUser,
    session: SessionDep,
    page: PageQuery = 1,
    page_size: SizeQuery = 25,
    item_id: UUID | None = None,
    change_type: str | None = None,
) -> PageResponse:
    """The master rate change log: who changed which rate, when, and why."""

    return ItemPriceService(session, current_user.id).revisions(
        page=page, page_size=page_size, item_id=item_id, change_type=change_type
    )
