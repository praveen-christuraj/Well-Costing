"""Application services for service orders, purchase orders, rate cards, and prices."""

from datetime import date
from math import ceil
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.db.base import Base
from app.models.master_data import (
    CatalogItem,
    Currency,
    HoleSection,
    ItemPrice,
    PurchaseOrder,
    ServiceOrder,
    ServiceRateCard,
    Unit,
    Vendor,
)
from app.schemas.master_data import BulkRowError, BulkValidationResult, PageResponse
from app.schemas.procurement import (
    ItemPriceRead,
    PurchaseOrderRead,
    ServiceOrderRead,
    ServiceRateCardRead,
)

# ``Generic`` is used instead of PEP 695 type parameters so the module also imports
# under Python 3.11 tooling; behaviour is identical on the supported 3.12+ runtime.
ModelT = TypeVar("ModelT", bound=Base)
ReadT = TypeVar("ReadT", bound=BaseModel)


class _BaseService(Generic[ModelT, ReadT]):  # noqa: UP046
    """Shared audited CRUD, filtering, pagination, and all-or-nothing bulk writes."""

    model: type[ModelT]
    read_model: type[ReadT]
    label: str
    search_columns: tuple[str, ...] = ()
    sortable: frozenset[str] = frozenset()
    default_sort: str = "created_at"

    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session = session
        self.actor_id = actor_id

    # -- querying ---------------------------------------------------------
    def _apply_filters(self, statement: Select[Any], filters: dict[str, Any]) -> Select[Any]:
        search = filters.get("search")
        if search:
            pattern = f"%{str(search).strip()}%"
            clauses = [
                getattr(self.model, column).ilike(pattern) for column in self.search_columns
            ]
            if clauses:
                statement = statement.where(or_(*clauses))
        if filters.get("is_active") is not None:
            statement = statement.where(self.model.is_active == filters["is_active"])  # type: ignore[attr-defined]
        return self._apply_entity_filters(statement, filters)

    def _apply_entity_filters(
        self, statement: Select[Any], filters: dict[str, Any]
    ) -> Select[Any]:
        return statement

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
        **filters: Any,
    ) -> PageResponse:
        statement = select(self.model)
        count_statement = select(func.count()).select_from(self.model)
        statement = self._apply_filters(statement, filters)
        count_statement = self._apply_filters(count_statement, filters)

        resolved = sort_by if sort_by in self.sortable else self.default_sort
        column = getattr(self.model, resolved)
        statement = statement.order_by(column.desc() if sort_order == "desc" else column.asc())
        statement = statement.offset((page - 1) * page_size).limit(page_size)

        records = self.session.scalars(statement).unique().all()
        total = int(self.session.scalar(count_statement) or 0)
        return PageResponse(
            items=[self._serialize(record) for record in records],
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )

    def get(self, record_id: UUID) -> ReadT:
        return self._serialize(self._require(record_id))

    def _require(self, record_id: UUID) -> ModelT:
        record = self.session.get(self.model, record_id)
        if record is None:
            raise NotFoundError(f"{self.label} not found")
        return record

    # -- writing ----------------------------------------------------------
    def create(self, payload: BaseModel, *, commit: bool = True) -> ReadT:
        values = payload.model_dump(exclude_unset=True)
        self._validate(values)
        record = self.model(**values, created_by=self.actor_id, updated_by=self.actor_id)
        self.session.add(record)
        try:
            self.session.flush()
            if commit:
                self.session.commit()
            self.session.refresh(record)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                f"This {self.label.lower()} conflicts with an existing record"
            ) from exc
        return self._serialize(record)

    def update(self, record_id: UUID, payload: BaseModel, *, commit: bool = True) -> ReadT:
        record = self._require(record_id)
        values = payload.model_dump(exclude_unset=True)
        self._validate(values, record=record)
        for field, value in values.items():
            setattr(record, field, value)
        record.updated_by = self.actor_id  # type: ignore[attr-defined]
        try:
            self.session.flush()
            if commit:
                self.session.commit()
            self.session.refresh(record)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                f"This {self.label.lower()} conflicts with an existing record"
            ) from exc
        return self._serialize(record)

    def deactivate(self, record_id: UUID) -> None:
        record = self._require(record_id)
        record.is_active = False  # type: ignore[attr-defined]
        record.updated_by = self.actor_id  # type: ignore[attr-defined]
        self.session.commit()

    def delete(self, record_id: UUID) -> None:
        record = self._require(record_id)
        try:
            self.session.delete(record)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                f"This {self.label.lower()} is referenced by other records and cannot be deleted. "
                "Deactivate it instead."
            ) from exc

    def validate_bulk(self, rows: list[Any]) -> BulkValidationResult:
        errors: list[BulkRowError] = []
        seen: set[str] = set()
        for index, row in enumerate(rows):
            try:
                data = row.model_dump(exclude_unset=True)
                # Relaxation: normalize order_number for duplicate detection (trim + upper)
                order_no = data.get("order_number")
                if isinstance(order_no, str):
                    key = order_no.strip().upper()
                    if key in seen:
                        raise BusinessValidationError(f"Duplicate order_number '{order_no.strip()}' within bulk payload (row {index + 1})")
                    seen.add(key)
                    # DB duplicate check – friendly error before attempting insert
                    model = getattr(self, "model", None)
                    if model is not None and hasattr(model, "order_number") and key:
                        exists = self.session.scalar(select(model).where(model.order_number.ilike(key)))  # type: ignore
                        if exists is not None:
                            raise BusinessValidationError(f"order_number '{key}' already exists – row will be skipped; remove or change it for bulk import")
                self._validate(data)
            except BusinessValidationError as exc:
                errors.append(
                    BulkRowError(row_index=index, code="invalid_reference", message=exc.message)
                )
        invalid = {error.row_index for error in errors}
        return BulkValidationResult(
            valid=not errors,
            total_rows=len(rows),
            valid_rows=len(rows) - len(invalid),
            errors=errors,
        )

    def bulk_create(self, rows: list[Any]) -> list[ReadT]:
        validation = self.validate_bulk(rows)
        if not validation.valid:
            raise BusinessValidationError("Bulk validation failed", validation.model_dump())
        created: list[ReadT] = []
        BULK_CHUNK = 500
        try:
            for row in rows:
                created.append(self.create(row, commit=False))
                if len(created) % BULK_CHUNK == 0:
                    self.session.flush()
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return created

    def bulk_update(self, rows: list[tuple[UUID, BaseModel]]) -> list[ReadT]:
        updated: list[ReadT] = []
        try:
            for record_id, payload in rows:
                updated.append(self.update(record_id, payload, commit=False))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return updated

    # -- hooks ------------------------------------------------------------
    def _validate(self, values: dict[str, Any], record: ModelT | None = None) -> None:
        raise NotImplementedError

    def _serialize(self, record: ModelT) -> ReadT:
        raise NotImplementedError

    def _check_references(self, values: dict[str, Any], references: dict[str, type[Any]]) -> None:
        for field, model in references.items():
            value = values.get(field)
            if value is not None and self.session.get(model, value) is None:
                raise BusinessValidationError(f"{field} does not reference an existing record")

    @staticmethod
    def _resolve(values: dict[str, Any], record: Any, field: str) -> Any:
        return values.get(field, getattr(record, field, None)) if record else values.get(field)


def _date_range_guard(
    values: dict[str, Any], record: Any, start_field: str, end_field: str
) -> None:
    start = values.get(start_field, getattr(record, start_field, None) if record else None)
    end = values.get(end_field, getattr(record, end_field, None) if record else None)
    if isinstance(start, date) and isinstance(end, date) and end < start:
        raise BusinessValidationError(f"{end_field} must be on or after {start_field}")


class ServiceOrderService(_BaseService[ServiceOrder, ServiceOrderRead]):
    model = ServiceOrder
    read_model = ServiceOrderRead
    label = "Service order"
    search_columns = ("order_number", "title")
    sortable = frozenset(
        {"order_number", "title", "valid_from", "valid_to", "status", "created_at", "updated_at"}
    )
    default_sort = "order_number"

    def _apply_entity_filters(
        self, statement: Select[Any], filters: dict[str, Any]
    ) -> Select[Any]:
        if filters.get("vendor_id"):
            statement = statement.where(ServiceOrder.vendor_id == filters["vendor_id"])
        if filters.get("status"):
            statement = statement.where(ServiceOrder.status == filters["status"])
        if filters.get("valid_on"):
            valid_on = filters["valid_on"]
            statement = statement.where(
                ServiceOrder.valid_from <= valid_on,
                or_(ServiceOrder.valid_to.is_(None), ServiceOrder.valid_to >= valid_on),
            )
        return statement

    def _validate(self, values: dict[str, Any], record: ServiceOrder | None = None) -> None:
        if values.get("order_number"):
            values["order_number"] = str(values["order_number"]).strip().upper()
        # Relaxation: status case-insensitive and synonym tolerant
        if values.get("status"):
            raw = str(values["status"]).strip().lower().replace(" ", "_").replace("-", "_")
            synonyms = {"activated": "active", "enabled": "active", "canceled": "cancelled", "cancelled": "cancelled"}
            raw = synonyms.get(raw, raw)
            if raw not in {"draft", "active", "expired", "cancelled"}:
                raw = "draft"
            values["status"] = raw
        self._check_references(values, {"vendor_id": Vendor, "currency_id": Currency})
        _date_range_guard(values, record, "valid_from", "valid_to")

    def _serialize(self, record: ServiceOrder) -> ServiceOrderRead:
        return ServiceOrderRead.model_validate(record).model_copy(
            update={
                "vendor_code": record.vendor.code if record.vendor else None,
                "vendor_name": record.vendor.name if record.vendor else None,
                "currency_code": record.currency.code if record.currency else None,
            }
        )


class PurchaseOrderService(_BaseService[PurchaseOrder, PurchaseOrderRead]):
    model = PurchaseOrder
    read_model = PurchaseOrderRead
    label = "Purchase order"
    search_columns = ("order_number", "title")
    sortable = frozenset(
        {"order_number", "title", "order_date", "status", "created_at", "updated_at"}
    )
    default_sort = "order_number"

    def _apply_entity_filters(
        self, statement: Select[Any], filters: dict[str, Any]
    ) -> Select[Any]:
        if filters.get("vendor_id"):
            statement = statement.where(PurchaseOrder.vendor_id == filters["vendor_id"])
        if filters.get("status"):
            statement = statement.where(PurchaseOrder.status == filters["status"])
        return statement

    def _validate(self, values: dict[str, Any], record: PurchaseOrder | None = None) -> None:
        if values.get("order_number"):
            values["order_number"] = str(values["order_number"]).strip().upper()
        if values.get("status"):
            raw = str(values["status"]).strip().lower().replace(" ", "_").replace("-", "_")
            synonyms = {"activated": "open", "partial": "partially_received", "partiallyreceived": "partially_received", "canceled": "cancelled"}
            raw = synonyms.get(raw, raw)
            if raw not in {"draft", "open", "partially_received", "closed", "cancelled"}:
                raw = "draft"
            values["status"] = raw
        self._check_references(values, {"vendor_id": Vendor, "currency_id": Currency})
        _date_range_guard(values, record, "order_date", "expected_delivery_date")

    def _serialize(self, record: PurchaseOrder) -> PurchaseOrderRead:
        return PurchaseOrderRead.model_validate(record).model_copy(
            update={
                "vendor_code": record.vendor.code if record.vendor else None,
                "vendor_name": record.vendor.name if record.vendor else None,
                "currency_code": record.currency.code if record.currency else None,
            }
        )


class ServiceRateCardService(_BaseService[ServiceRateCard, ServiceRateCardRead]):
    model = ServiceRateCard
    read_model = ServiceRateCardRead
    label = "Service rate"
    sortable = frozenset(
        {"effective_from", "effective_to", "operating_rate", "created_at", "updated_at"}
    )
    default_sort = "effective_from"

    def _apply_filters(self, statement: Select[Any], filters: dict[str, Any]) -> Select[Any]:
        search = filters.get("search")
        if search:
            pattern = f"%{str(search).strip()}%"
            statement = statement.join(
                CatalogItem, ServiceRateCard.service_id == CatalogItem.id
            ).where(or_(CatalogItem.code.ilike(pattern), CatalogItem.name.ilike(pattern)))
        if filters.get("is_active") is not None:
            statement = statement.where(ServiceRateCard.is_active == filters["is_active"])
        return self._apply_entity_filters(statement, filters)

    def _apply_entity_filters(
        self, statement: Select[Any], filters: dict[str, Any]
    ) -> Select[Any]:
        if filters.get("service_id"):
            statement = statement.where(ServiceRateCard.service_id == filters["service_id"])
        if filters.get("vendor_id"):
            statement = statement.where(ServiceRateCard.vendor_id == filters["vendor_id"])
        if filters.get("hole_section_id"):
            statement = statement.where(ServiceRateCard.hole_section_id == filters["hole_section_id"])
        if filters.get("rate_basis"):
            statement = statement.where(ServiceRateCard.rate_basis == filters["rate_basis"])
        if filters.get("effective_on"):
            on = filters["effective_on"]
            statement = statement.where(
                ServiceRateCard.effective_from <= on,
                or_(ServiceRateCard.effective_to.is_(None), ServiceRateCard.effective_to >= on),
            )
        return statement

    def _validate(self, values: dict[str, Any], record: ServiceRateCard | None = None) -> None:
        self._check_references(
            values,
            {
                "service_id": CatalogItem,
                "vendor_id": Vendor,
                "hole_section_id": HoleSection,
                "currency_id": Currency,
                "unit_id": Unit,
            },
        )
        service_id = values.get("service_id")
        if service_id is not None:
            item = self.session.get(CatalogItem, service_id)
            if item is not None and item.item_type != "service":
                raise BusinessValidationError("service_id must reference a service catalogue item")
        rate_basis = self._resolve(values, record, "rate_basis")
        if rate_basis not in {"daily", "per_service", "per_section", "fixed"}:
            raise BusinessValidationError("rate_basis must be daily, per_service, per_section, or fixed")
        if rate_basis == "per_section" and self._resolve(values, record, "hole_section_id") is None:
            raise BusinessValidationError("hole_section_id is required for per-section rates")
        _date_range_guard(values, record, "effective_from", "effective_to")

    def _serialize(self, record: ServiceRateCard) -> ServiceRateCardRead:
        return ServiceRateCardRead.model_validate(record).model_copy(
            update={
                "service_code": record.service.code if record.service else None,
                "service_name": record.service.name if record.service else None,
                "vendor_code": record.vendor.code if record.vendor else None,
                "vendor_name": record.vendor.name if record.vendor else None,
                "hole_section_code": record.hole_section.code if record.hole_section else None,
                "hole_section_name": record.hole_section.name if record.hole_section else None,
                "currency_code": record.currency.code if record.currency else None,
                "unit_code": record.unit.code if record.unit else None,
            }
        )


class ItemPriceService(_BaseService[ItemPrice, ItemPriceRead]):
    model = ItemPrice
    read_model = ItemPriceRead
    label = "Item price"
    sortable = frozenset(
        {"effective_from", "effective_to", "unit_price", "created_at", "updated_at"}
    )
    default_sort = "effective_from"

    def _apply_filters(self, statement: Select[Any], filters: dict[str, Any]) -> Select[Any]:
        search = filters.get("search")
        item_type = filters.get("item_type")
        if search or item_type:
            statement = statement.join(CatalogItem, ItemPrice.item_id == CatalogItem.id)
        if search:
            pattern = f"%{str(search).strip()}%"
            statement = statement.where(
                or_(
                    CatalogItem.code.ilike(pattern),
                    CatalogItem.name.ilike(pattern),
                    CatalogItem.material_number.ilike(pattern),
                )
            )
        if item_type:
            statement = statement.where(CatalogItem.item_type == item_type)
        if filters.get("is_active") is not None:
            statement = statement.where(ItemPrice.is_active == filters["is_active"])
        return self._apply_entity_filters(statement, filters)

    def _apply_entity_filters(
        self, statement: Select[Any], filters: dict[str, Any]
    ) -> Select[Any]:
        if filters.get("item_id"):
            statement = statement.where(ItemPrice.item_id == filters["item_id"])
        if filters.get("vendor_id"):
            statement = statement.where(ItemPrice.vendor_id == filters["vendor_id"])
        if filters.get("purchase_order_id"):
            statement = statement.where(
                ItemPrice.purchase_order_id == filters["purchase_order_id"]
            )
        if filters.get("effective_on"):
            on = filters["effective_on"]
            statement = statement.where(
                ItemPrice.effective_from <= on,
                or_(ItemPrice.effective_to.is_(None), ItemPrice.effective_to >= on),
            )
        return statement

    def _validate(self, values: dict[str, Any], record: ItemPrice | None = None) -> None:
        self._check_references(
            values,
            {
                "item_id": CatalogItem,
                "vendor_id": Vendor,
                "purchase_order_id": PurchaseOrder,
                "currency_id": Currency,
                "unit_id": Unit,
            },
        )
        _date_range_guard(values, record, "effective_from", "effective_to")

    def _serialize(self, record: ItemPrice) -> ItemPriceRead:
        return ItemPriceRead.model_validate(record).model_copy(
            update={
                "item_code": record.item.code if record.item else None,
                "item_name": record.item.name if record.item else None,
                "item_type": record.item.item_type if record.item else None,
                "vendor_code": record.vendor.code if record.vendor else None,
                "vendor_name": record.vendor.name if record.vendor else None,
                "purchase_order_number": (
                    record.purchase_order.order_number if record.purchase_order else None
                ),
                "currency_code": record.currency.code if record.currency else None,
                "unit_code": record.unit.code if record.unit else None,
            }
        )
