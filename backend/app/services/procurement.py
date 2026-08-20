"""Application services for service orders, purchase orders, and master rates.

Services carry no master rate: they are priced per well in the well rate book,
because the same crew is quoted differently per well and per campaign. Only
tangibles and consumables hold a master rate here, and that rate is revised —
never overwritten — so a well that copied it earlier keeps its own number.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
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
    ItemPrice,
    PurchaseOrder,
    RateRevision,
    ServiceOrder,
    Unit,
    Vendor,
)
from app.schemas.master_data import BulkRowError, BulkValidationResult, PageResponse
from app.schemas.procurement import (
    ItemPriceRead,
    ItemPriceReviseRequest,
    PurchaseOrderRead,
    RateRevisionRead,
    ServiceOrderRead,
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
        item_id = self._resolve(values, record, "item_id")
        if item_id is not None:
            item = self.session.get(CatalogItem, item_id)
            if item is not None and item.item_type == "service":
                raise BusinessValidationError(
                    "Services have no master rate. Price the service on the well's "
                    "rate book instead."
                )
        _date_range_guard(values, record, "effective_from", "effective_to")

    # -- revision tracking ------------------------------------------------
    def create(self, payload: BaseModel, *, commit: bool = True) -> ItemPriceRead:
        """Create a master rate and open its revision history."""

        created = super().create(payload, commit=commit)
        record = self.session.get(ItemPrice, created.id)
        if record is not None:
            self._log_revision(record, change_type="created", previous=None)
            if commit:
                self.session.commit()
        return created

    def revise(self, record_id: UUID, payload: ItemPriceReviseRequest) -> ItemPriceRead:
        """Supersede a master rate with its next revision.

        The current row is closed the day before the new rate takes effect and a
        new row is inserted carrying ``revision_number + 1`` and a link back to
        the row it replaces. Wells that already copied the old rate are
        untouched — that is the whole point of the copy.
        """

        current = self._require(record_id)
        if current.effective_to is not None and payload.effective_from <= current.effective_to:
            raise BusinessValidationError(
                "effective_from must fall after the current rate's effective_to"
            )
        if payload.effective_from <= current.effective_from:
            raise BusinessValidationError(
                "A revision must take effect after the rate it supersedes "
                f"({current.effective_from.isoformat()})"
            )
        previous_amount = current.unit_price
        current.effective_to = payload.effective_from - timedelta(days=1)
        current.superseded_at = datetime.now(UTC)
        current.updated_by = self.actor_id

        revision = ItemPrice(
            item_id=current.item_id,
            vendor_id=payload.vendor_id if payload.vendor_id is not None else current.vendor_id,
            purchase_order_id=(
                payload.purchase_order_id
                if payload.purchase_order_id is not None
                else current.purchase_order_id
            ),
            currency_id=(
                payload.currency_id if payload.currency_id is not None else current.currency_id
            ),
            unit_id=payload.unit_id if payload.unit_id is not None else current.unit_id,
            unit_price=payload.unit_price,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            revision_number=current.revision_number + 1,
            supersedes_id=current.id,
            change_reason=payload.change_reason,
            description=(
                payload.description if payload.description is not None else current.description
            ),
            is_active=True,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(revision)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("This rate revision conflicts with an existing record") from exc
        self._log_revision(
            revision,
            change_type="revised",
            previous=previous_amount,
            previous_price_id=current.id,
            reason=payload.change_reason,
        )
        self.session.commit()
        self.session.refresh(revision)
        return self._serialize(revision)

    def deactivate(self, record_id: UUID) -> None:
        record = self._require(record_id)
        super().deactivate(record_id)
        self._log_revision(
            record, change_type="withdrawn", previous=record.unit_price, withdrawn=True
        )
        self.session.commit()

    def revisions(
        self,
        *,
        page: int,
        page_size: int,
        item_id: UUID | None = None,
        change_type: str | None = None,
    ) -> PageResponse:
        """The master rate change log, newest first."""

        statement = select(RateRevision)
        if item_id:
            statement = statement.where(RateRevision.item_id == item_id)
        if change_type:
            statement = statement.where(RateRevision.change_type == change_type)
        total = int(
            self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        )
        records = (
            self.session.scalars(
                statement.order_by(
                    RateRevision.created_at.desc(), RateRevision.revision_number.desc()
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .unique()
            .all()
        )
        return PageResponse(
            items=[self._serialize_revision(record) for record in records],
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )

    def _log_revision(
        self,
        record: ItemPrice,
        *,
        change_type: str,
        previous: Decimal | None,
        withdrawn: bool = False,
        previous_price_id: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        """Append one entry to the master rate change log."""

        amount = None if withdrawn else record.unit_price
        self.session.add(
            RateRevision(
                scope="item_price",
                item_id=record.item_id,
                item_price_id=record.id,
                previous_price_id=previous_price_id,
                vendor_id=record.vendor_id,
                currency_id=record.currency_id,
                unit_id=record.unit_id,
                change_type=change_type,
                revision_number=record.revision_number,
                previous_amount=previous,
                new_amount=amount,
                effective_from=record.effective_from,
                reason=reason or record.change_reason,
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
        )

    @staticmethod
    def _serialize_revision(record: RateRevision) -> RateRevisionRead:
        return RateRevisionRead.model_validate(record).model_copy(
            update={
                "item_code": record.item.code if record.item else None,
                "item_name": record.item.name if record.item else None,
                "item_type": record.item.item_type if record.item else None,
                "vendor_code": record.vendor.code if record.vendor else None,
                "currency_code": record.currency.code if record.currency else None,
                "unit_code": record.unit.code if record.unit else None,
                "delta_amount": (
                    (record.new_amount or Decimal("0")) - (record.previous_amount or Decimal("0"))
                ),
            }
        )

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
