"""Application services for the well rate book and the out-of-AFE register.

Master rates change while rigs drill. These services keep each well on the rate
it was planned with by copying the rate into the well and freezing it when the
AFE baseline is issued, and by routing every later deviation through the
out-of-AFE register instead of an edit to an approved AFE.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.domain.well_costing import (
    RateBookLockedError,
    RateChangeReasonRequiredError,
    UnplannedTransitionError,
    assert_rate_change_allowed,
    assert_reason_supplied,
    changed_financial_fields,
    next_revision_number,
    summarise_exposure,
    unplanned_transition,
)
from app.models.afe import Afe, Well
from app.models.afe_snapshots import AfeSnapshot
from app.models.estimates import CostEstimate, EstimateVersion
from app.models.master_data import (
    CatalogItem,
    CostCode,
    Currency,
    HoleSection,
    ItemPrice,
    Unit,
    Vendor,
)
from app.models.well_costing import (
    WellRateRevision,
    WellServiceRate,
    WellTangibleRate,
    WellUnplannedItem,
)
from app.schemas.master_data import PageResponse
from app.schemas.well_costing import (
    AvailableServiceRead,
    AvailableTangibleRead,
    RateBookLockRequest,
    RateBookLockResult,
    WellCostExposureRead,
    WellRateRevisionRead,
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

SERVICE_RATE_FIELDS = (
    "rate_basis",
    "operating_rate",
    "standby_rate",
    "mobilisation_rate",
    "demobilisation_rate",
    "personnel_operating_rate",
    "personnel_standby_rate",
    "other_rate",
    "currency_id",
    "unit_id",
    "vendor_id",
    "hole_section_id",
)
TANGIBLE_RATE_FIELDS = ("unit_rate", "currency_id", "unit_id", "vendor_id")


def _page(items: list[Any], page: int, page_size: int, total: int) -> PageResponse:
    return PageResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=ceil(total / page_size) if total else 0,
    )


#: Money is stored at four decimal places, so snapshots are normalised to the
#: same scale — otherwise "13000" and "13000.0000" would look like a change.
MONEY_SCALE = Decimal("0.0001")


def _snapshot(record: object, fields: tuple[str, ...]) -> dict[str, object]:
    """Capture the rate-bearing fields of a row for the audit log."""

    values: dict[str, object] = {}
    for field in fields:
        value = getattr(record, field, None)
        if isinstance(value, Decimal):
            values[field] = str(value.quantize(MONEY_SCALE))
        elif isinstance(value, UUID):
            values[field] = str(value)
        elif isinstance(value, date):
            values[field] = value.isoformat()
        else:
            values[field] = value
    return values


def _translate_rule_error(exc: Exception) -> BusinessValidationError | ConflictError:
    if isinstance(exc, RateBookLockedError):
        error = ConflictError(str(exc))
        error.code = exc.code  # type: ignore[attr-defined]
        return error
    error = BusinessValidationError(str(exc))
    error.code = getattr(exc, "code", error.code)  # type: ignore[attr-defined]
    return error


class _WellScopedService:
    """Shared reference resolution and well lookup for well-scoped writes."""

    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session = session
        self.actor_id = actor_id

    def require_well(self, well_id: UUID) -> Well:
        well = self.session.get(Well, well_id)
        if well is None:
            raise NotFoundError("Well not found")
        return well

    def _check_references(self, values: dict[str, Any], references: dict[str, type[Any]]) -> None:
        for field, model in references.items():
            value = values.get(field)
            if value is not None and self.session.get(model, value) is None:
                raise BusinessValidationError(f"{field} does not reference an existing record")

    def _require_catalog_item(self, item_id: UUID, item_type: str, field: str) -> CatalogItem:
        item = self.session.get(CatalogItem, item_id)
        if item is None:
            raise BusinessValidationError(f"{field} does not reference an existing record")
        if item.item_type != item_type:
            raise BusinessValidationError(
                f"{field} must reference a {item_type} from master data, not a "
                f"{item.item_type}"
            )
        return item

    def current_master_price(self, item_id: UUID, on: date | None = None) -> ItemPrice | None:
        """Return the master rate in force for ``item_id`` on ``on`` (today by default)."""

        as_of = on or datetime.now(UTC).date()
        statement = (
            select(ItemPrice)
            .where(
                ItemPrice.item_id == item_id,
                ItemPrice.is_active.is_(True),
                ItemPrice.effective_from <= as_of,
                or_(ItemPrice.effective_to.is_(None), ItemPrice.effective_to >= as_of),
            )
            .order_by(ItemPrice.effective_from.desc(), ItemPrice.revision_number.desc())
        )
        return self.session.scalars(statement).first()

    def _log(
        self,
        *,
        well_id: UUID,
        scope: str,
        change_type: str,
        item_code: str,
        item_name: str,
        revision_number: int,
        previous_rates: dict[str, object] | None,
        new_rates: dict[str, object] | None,
        reason: str | None,
        service_rate_id: UUID | None = None,
        tangible_rate_id: UUID | None = None,
    ) -> WellRateRevision:
        revision = WellRateRevision(
            well_id=well_id,
            scope=scope,
            well_service_rate_id=service_rate_id,
            well_tangible_rate_id=tangible_rate_id,
            item_code=item_code,
            item_name=item_name,
            change_type=change_type,
            revision_number=revision_number,
            previous_rates=previous_rates,
            new_rates=new_rates,
            reason=reason,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(revision)
        return revision


class WellRateBookService(_WellScopedService):
    """The per-well rate book: services priced per well, tangibles copied in."""

    # -- reads ------------------------------------------------------------
    def list_services(
        self,
        well_id: UUID,
        *,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        is_active: bool | None = None,
        status: str | None = None,
        origin: str | None = None,
    ) -> PageResponse:
        self.require_well(well_id)
        statement = select(WellServiceRate).where(WellServiceRate.well_id == well_id)
        statement = self._filter_rates(
            statement,
            WellServiceRate,
            search=search,
            is_active=is_active,
            status=status,
            origin=origin,
            item_column=WellServiceRate.service_id,
        )
        total = self._count(statement)
        rows = self.session.scalars(
            statement.order_by(WellServiceRate.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().all()
        return _page([self.serialize_service(row) for row in rows], page, page_size, total)

    def list_tangibles(
        self,
        well_id: UUID,
        *,
        page: int = 1,
        page_size: int = 50,
        search: str | None = None,
        is_active: bool | None = None,
        status: str | None = None,
        origin: str | None = None,
    ) -> PageResponse:
        self.require_well(well_id)
        statement = select(WellTangibleRate).where(WellTangibleRate.well_id == well_id)
        statement = self._filter_rates(
            statement,
            WellTangibleRate,
            search=search,
            is_active=is_active,
            status=status,
            origin=origin,
            item_column=WellTangibleRate.tangible_id,
        )
        total = self._count(statement)
        rows = self.session.scalars(
            statement.order_by(WellTangibleRate.created_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().all()
        return _page([self.serialize_tangible(row) for row in rows], page, page_size, total)

    def _filter_rates(
        self,
        statement: Select[Any],
        model: type[Any],
        *,
        search: str | None,
        is_active: bool | None,
        status: str | None,
        origin: str | None,
        item_column: Any,
    ) -> Select[Any]:
        if is_active is not None:
            statement = statement.where(model.is_active.is_(is_active))
        if status:
            statement = statement.where(model.status == status)
        if origin:
            statement = statement.where(model.origin == origin)
        if search:
            pattern = f"%{search.strip()}%"
            matches = select(CatalogItem.id).where(
                or_(CatalogItem.code.ilike(pattern), CatalogItem.name.ilike(pattern))
            )
            statement = statement.where(item_column.in_(matches))
        return statement

    def _count(self, statement: Select[Any]) -> int:
        return int(
            self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        )

    def available_services(
        self, well_id: UUID, *, search: str | None = None, limit: int = 500
    ) -> list[AvailableServiceRead]:
        """Master services, flagged with whether the well already prices them."""

        self.require_well(well_id)
        taken = {
            row
            for row in self.session.scalars(
                select(WellServiceRate.service_id).where(
                    WellServiceRate.well_id == well_id, WellServiceRate.is_active.is_(True)
                )
            ).all()
        }
        items = self._catalogue(item_type="service", search=search, limit=limit)
        return [
            AvailableServiceRead(
                id=item.id,
                code=item.code,
                name=item.name,
                description=item.description,
                cost_code_id=item.cost_code_id,
                cost_code=item.cost_code.code if item.cost_code else None,
                default_unit_id=item.default_unit_id,
                default_unit_code=item.default_unit.code if item.default_unit else None,
                in_rate_book=item.id in taken,
            )
            for item in items
        ]

    def available_tangibles(
        self, well_id: UUID, *, search: str | None = None, limit: int = 500
    ) -> list[AvailableTangibleRead]:
        """Master tangibles plus the master rate that would be copied into the well."""

        self.require_well(well_id)
        taken = {
            row
            for row in self.session.scalars(
                select(WellTangibleRate.tangible_id).where(
                    WellTangibleRate.well_id == well_id, WellTangibleRate.is_active.is_(True)
                )
            ).all()
        }
        results: list[AvailableTangibleRead] = []
        for item in self._catalogue(item_type="tangible", search=search, limit=limit):
            price = self.current_master_price(item.id)
            results.append(
                AvailableTangibleRead(
                    id=item.id,
                    code=item.code,
                    name=item.name,
                    description=item.description,
                    cost_code_id=item.cost_code_id,
                    cost_code=item.cost_code.code if item.cost_code else None,
                    default_unit_id=item.default_unit_id,
                    default_unit_code=item.default_unit.code if item.default_unit else None,
                    in_rate_book=item.id in taken,
                    master_price_id=price.id if price else None,
                    master_unit_rate=price.unit_price if price else None,
                    master_currency_id=price.currency_id if price else None,
                    master_currency_code=price.currency.code if price else None,
                    master_unit_id=price.unit_id if price else None,
                    master_unit_code=price.unit.code if price else None,
                    master_vendor_id=price.vendor_id if price else None,
                    master_effective_from=price.effective_from if price else None,
                )
            )
        return results

    def _catalogue(self, *, item_type: str, search: str | None, limit: int) -> list[CatalogItem]:
        statement = select(CatalogItem).where(
            CatalogItem.item_type == item_type, CatalogItem.is_active.is_(True)
        )
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(CatalogItem.code.ilike(pattern), CatalogItem.name.ilike(pattern))
            )
        statement = statement.order_by(CatalogItem.code.asc()).limit(limit)
        return list(self.session.scalars(statement).unique().all())

    def revisions(
        self, well_id: UUID, *, page: int = 1, page_size: int = 50, scope: str | None = None
    ) -> PageResponse:
        self.require_well(well_id)
        statement = select(WellRateRevision).where(WellRateRevision.well_id == well_id)
        if scope:
            statement = statement.where(WellRateRevision.scope == scope)
        total = self._count(statement)
        rows = self.session.scalars(
            statement.order_by(
                WellRateRevision.created_at.desc(), WellRateRevision.revision_number.desc()
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().all()
        return _page(
            [WellRateRevisionRead.model_validate(row) for row in rows], page, page_size, total
        )

    # -- service writes ---------------------------------------------------
    def add_service(self, well_id: UUID, payload: WellServiceRateCreate) -> WellServiceRateRead:
        well = self.require_well(well_id)
        values = payload.model_dump(exclude_unset=True)
        service = self._require_catalog_item(payload.service_id, "service", "service_id")
        self._check_references(
            values,
            {
                "vendor_id": Vendor,
                "currency_id": Currency,
                "unit_id": Unit,
                "hole_section_id": HoleSection,
            },
        )
        self._reject_duplicate_service(well_id, payload)
        record = WellServiceRate(
            well_id=well.id,
            origin="well_planning",
            status="draft",
            created_by=self.actor_id,
            updated_by=self.actor_id,
            **values,
        )
        self.session.add(record)
        self._flush("service rate")
        self._log(
            well_id=well.id,
            scope="service",
            change_type="added",
            item_code=service.code,
            item_name=service.name,
            revision_number=1,
            previous_rates=None,
            new_rates=_snapshot(record, SERVICE_RATE_FIELDS),
            reason=payload.notes,
            service_rate_id=record.id,
        )
        self.session.commit()
        self.session.refresh(record)
        return self.serialize_service(record)

    def _reject_duplicate_service(self, well_id: UUID, payload: WellServiceRateCreate) -> None:
        existing = self.session.scalar(
            select(WellServiceRate).where(
                WellServiceRate.well_id == well_id,
                WellServiceRate.service_id == payload.service_id,
                WellServiceRate.rate_basis == payload.rate_basis,
                WellServiceRate.hole_section_id.is_(payload.hole_section_id)
                if payload.hole_section_id is None
                else WellServiceRate.hole_section_id == payload.hole_section_id,
            )
        )
        if existing is not None:
            raise ConflictError(
                "This service is already priced for the well on the same basis and "
                "hole section. Revise the existing entry instead."
            )

    def update_service(
        self, well_id: UUID, rate_id: UUID, payload: WellServiceRateUpdate
    ) -> WellServiceRateRead:
        self.require_well(well_id)
        record = self._require_service(well_id, rate_id)
        values = payload.model_dump(exclude_unset=True)
        reason = values.pop("change_reason", None)
        try:
            assert_rate_change_allowed(record.status, values)
            assert_reason_supplied(reason, values)
        except (RateBookLockedError, RateChangeReasonRequiredError) as exc:
            raise _translate_rule_error(exc) from exc
        self._check_references(
            values,
            {
                "vendor_id": Vendor,
                "currency_id": Currency,
                "unit_id": Unit,
                "hole_section_id": HoleSection,
            },
        )
        financial = bool(changed_financial_fields(values))
        previous = _snapshot(record, SERVICE_RATE_FIELDS)
        for field, value in values.items():
            setattr(record, field, value)
        if financial:
            record.revision_number = next_revision_number(record.revision_number)
        record.updated_by = self.actor_id
        self._flush("service rate")
        self._log(
            well_id=well_id,
            scope="service",
            change_type="rate_revised" if financial else "details_updated",
            item_code=record.service.code,
            item_name=record.service.name,
            revision_number=record.revision_number,
            previous_rates=previous,
            new_rates=_snapshot(record, SERVICE_RATE_FIELDS),
            reason=reason,
            service_rate_id=record.id,
        )
        self.session.commit()
        self.session.refresh(record)
        return self.serialize_service(record)

    def remove_service(self, well_id: UUID, rate_id: UUID, *, reason: str | None = None) -> None:
        self.require_well(well_id)
        record = self._require_service(well_id, rate_id)
        if record.status == "locked":
            raise _translate_rule_error(
                RateBookLockedError(
                    "This rate is locked to the approved AFE and cannot be removed. "
                    "Raise an out-of-AFE entry for the well instead."
                )
            )
        record.is_active = False
        record.updated_by = self.actor_id
        self._log(
            well_id=well_id,
            scope="service",
            change_type="deactivated",
            item_code=record.service.code,
            item_name=record.service.name,
            revision_number=record.revision_number,
            previous_rates=_snapshot(record, SERVICE_RATE_FIELDS),
            new_rates=None,
            reason=reason,
            service_rate_id=record.id,
        )
        self.session.commit()

    # -- tangible writes --------------------------------------------------
    def add_tangible(self, well_id: UUID, payload: WellTangibleRateCreate) -> WellTangibleRateRead:
        well = self.require_well(well_id)
        tangible = self._require_catalog_item(payload.tangible_id, "tangible", "tangible_id")
        values = payload.model_dump(exclude_unset=True)
        self._check_references(
            values, {"vendor_id": Vendor, "currency_id": Currency, "unit_id": Unit}
        )
        if self.session.scalar(
            select(WellTangibleRate).where(
                WellTangibleRate.well_id == well_id,
                WellTangibleRate.tangible_id == payload.tangible_id,
            )
        ):
            raise ConflictError(
                "This tangible is already priced for the well. Revise the existing entry."
            )

        master = self.current_master_price(payload.tangible_id)
        currency_id = payload.currency_id or (master.currency_id if master else None)
        unit_id = payload.unit_id or (master.unit_id if master else tangible.default_unit_id)
        if currency_id is None or unit_id is None:
            raise BusinessValidationError(
                "This tangible has no master rate yet, so currency_id and unit_id must "
                "be supplied with the well rate."
            )
        master_rate = master.unit_price if master else None
        unit_rate = payload.unit_rate if payload.unit_rate is not None else master_rate
        if unit_rate is None:
            raise BusinessValidationError(
                "This tangible has no master rate yet, so unit_rate must be supplied."
            )
        overridden = master_rate is not None and Decimal(unit_rate) != Decimal(master_rate)
        if overridden and not (payload.override_reason or "").strip():
            raise BusinessValidationError(
                "override_reason is required when the well rate differs from the "
                "master tangible rate."
            )

        record = WellTangibleRate(
            well_id=well.id,
            tangible_id=payload.tangible_id,
            vendor_id=payload.vendor_id or (master.vendor_id if master else None),
            currency_id=currency_id,
            unit_id=unit_id,
            unit_rate=unit_rate,
            master_price_id=master.id if master else None,
            master_unit_rate=master_rate,
            master_effective_from=master.effective_from if master else None,
            is_overridden=overridden,
            override_reason=payload.override_reason,
            contract_reference=payload.contract_reference,
            notes=payload.notes,
            origin="well_planning",
            status="draft",
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(record)
        self._flush("tangible rate")
        self._log(
            well_id=well.id,
            scope="tangible",
            change_type="added",
            item_code=tangible.code,
            item_name=tangible.name,
            revision_number=1,
            previous_rates=None,
            new_rates=_snapshot(record, TANGIBLE_RATE_FIELDS),
            reason=payload.override_reason or payload.notes,
            tangible_rate_id=record.id,
        )
        self.session.commit()
        self.session.refresh(record)
        return self.serialize_tangible(record)

    def update_tangible(
        self, well_id: UUID, rate_id: UUID, payload: WellTangibleRateUpdate
    ) -> WellTangibleRateRead:
        self.require_well(well_id)
        record = self._require_tangible(well_id, rate_id)
        values = payload.model_dump(exclude_unset=True)
        reason = values.pop("change_reason", None) or values.get("override_reason")
        try:
            assert_rate_change_allowed(record.status, values)
            assert_reason_supplied(reason, values)
        except (RateBookLockedError, RateChangeReasonRequiredError) as exc:
            raise _translate_rule_error(exc) from exc
        self._check_references(
            values, {"vendor_id": Vendor, "currency_id": Currency, "unit_id": Unit}
        )
        financial = bool(changed_financial_fields(values))
        previous = _snapshot(record, TANGIBLE_RATE_FIELDS)
        for field, value in values.items():
            setattr(record, field, value)
        if record.master_unit_rate is not None:
            record.is_overridden = Decimal(record.unit_rate) != Decimal(record.master_unit_rate)
        if financial:
            record.revision_number = next_revision_number(record.revision_number)
        record.updated_by = self.actor_id
        self._flush("tangible rate")
        self._log(
            well_id=well_id,
            scope="tangible",
            change_type="rate_revised" if financial else "details_updated",
            item_code=record.tangible.code,
            item_name=record.tangible.name,
            revision_number=record.revision_number,
            previous_rates=previous,
            new_rates=_snapshot(record, TANGIBLE_RATE_FIELDS),
            reason=reason,
            tangible_rate_id=record.id,
        )
        self.session.commit()
        self.session.refresh(record)
        return self.serialize_tangible(record)

    def remove_tangible(self, well_id: UUID, rate_id: UUID, *, reason: str | None = None) -> None:
        self.require_well(well_id)
        record = self._require_tangible(well_id, rate_id)
        if record.status == "locked":
            raise _translate_rule_error(
                RateBookLockedError(
                    "This rate is locked to the approved AFE and cannot be removed. "
                    "Raise an out-of-AFE entry for the well instead."
                )
            )
        record.is_active = False
        record.updated_by = self.actor_id
        self._log(
            well_id=well_id,
            scope="tangible",
            change_type="deactivated",
            item_code=record.tangible.code,
            item_name=record.tangible.name,
            revision_number=record.revision_number,
            previous_rates=_snapshot(record, TANGIBLE_RATE_FIELDS),
            new_rates=None,
            reason=reason,
            tangible_rate_id=record.id,
        )
        self.session.commit()

    # -- locking ----------------------------------------------------------
    def lock(self, well_id: UUID, payload: RateBookLockRequest) -> RateBookLockResult:
        """Freeze every draft rate so later master revisions cannot reach this well."""

        well = self.require_well(well_id)
        locked_at = datetime.now(UTC)
        services = list(
            self.session.scalars(
                select(WellServiceRate).where(
                    WellServiceRate.well_id == well_id,
                    WellServiceRate.status == "draft",
                    WellServiceRate.is_active.is_(True),
                )
            ).unique()
        )
        tangibles = list(
            self.session.scalars(
                select(WellTangibleRate).where(
                    WellTangibleRate.well_id == well_id,
                    WellTangibleRate.status == "draft",
                    WellTangibleRate.is_active.is_(True),
                )
            ).unique()
        )
        if not services and not tangibles and well.rates_locked_at is not None:
            raise ConflictError("This well's rate book is already locked.")
        for record in services:
            record.status = "locked"
            record.locked_at = locked_at
            record.updated_by = self.actor_id
            self._log(
                well_id=well_id,
                scope="service",
                change_type="locked",
                item_code=record.service.code,
                item_name=record.service.name,
                revision_number=record.revision_number,
                previous_rates=None,
                new_rates=_snapshot(record, SERVICE_RATE_FIELDS),
                reason=payload.reason,
                service_rate_id=record.id,
            )
        for tangible in tangibles:
            tangible.status = "locked"
            tangible.locked_at = locked_at
            tangible.updated_by = self.actor_id
            self._log(
                well_id=well_id,
                scope="tangible",
                change_type="locked",
                item_code=tangible.tangible.code,
                item_name=tangible.tangible.name,
                revision_number=tangible.revision_number,
                previous_rates=None,
                new_rates=_snapshot(tangible, TANGIBLE_RATE_FIELDS),
                reason=payload.reason,
                tangible_rate_id=tangible.id,
            )
        well.rates_locked_at = well.rates_locked_at or locked_at
        well.rate_lock_reference = payload.reference or well.rate_lock_reference
        well.updated_by = self.actor_id
        self.session.commit()
        return RateBookLockResult(
            well_id=well_id,
            locked_at=well.rates_locked_at or locked_at,
            reference=well.rate_lock_reference,
            locked_services=len(services),
            locked_tangibles=len(tangibles),
        )

    # -- helpers ----------------------------------------------------------
    def _require_service(self, well_id: UUID, rate_id: UUID) -> WellServiceRate:
        record = self.session.get(WellServiceRate, rate_id)
        if record is None or record.well_id != well_id:
            raise NotFoundError("Well service rate not found")
        return record

    def _require_tangible(self, well_id: UUID, rate_id: UUID) -> WellTangibleRate:
        record = self.session.get(WellTangibleRate, rate_id)
        if record is None or record.well_id != well_id:
            raise NotFoundError("Well tangible rate not found")
        return record

    def _flush(self, label: str) -> None:
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(f"This {label} conflicts with an existing record") from exc

    @staticmethod
    def serialize_service(record: WellServiceRate) -> WellServiceRateRead:
        return WellServiceRateRead.model_validate(record).model_copy(
            update={
                "service_code": record.service.code,
                "service_name": record.service.name,
                "vendor_code": record.vendor.code if record.vendor else None,
                "vendor_name": record.vendor.name if record.vendor else None,
                "currency_code": record.currency.code,
                "unit_code": record.unit.code,
                "hole_section_code": record.hole_section.code if record.hole_section else None,
            }
        )

    @staticmethod
    def serialize_tangible(record: WellTangibleRate) -> WellTangibleRateRead:
        variance = (
            Decimal(record.unit_rate) - Decimal(record.master_unit_rate)
            if record.master_unit_rate is not None
            else None
        )
        return WellTangibleRateRead.model_validate(record).model_copy(
            update={
                "tangible_code": record.tangible.code,
                "tangible_name": record.tangible.name,
                "vendor_code": record.vendor.code if record.vendor else None,
                "vendor_name": record.vendor.name if record.vendor else None,
                "currency_code": record.currency.code,
                "unit_code": record.unit.code,
                "variance_to_master": variance,
            }
        )


class WellUnplannedItemService(_WellScopedService):
    """Charges incurred outside the approved AFE and the well plan."""

    def list_items(
        self,
        well_id: UUID,
        *,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
        item_kind: str | None = None,
        search: str | None = None,
    ) -> PageResponse:
        self.require_well(well_id)
        statement = select(WellUnplannedItem).where(
            WellUnplannedItem.well_id == well_id, WellUnplannedItem.is_active.is_(True)
        )
        if status:
            statement = statement.where(WellUnplannedItem.status == status)
        if item_kind:
            statement = statement.where(WellUnplannedItem.item_kind == item_kind)
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(
                    WellUnplannedItem.item_description.ilike(pattern),
                    WellUnplannedItem.reference.ilike(pattern),
                )
            )
        total = int(
            self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        )
        rows = self.session.scalars(
            statement.order_by(WellUnplannedItem.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().all()
        return _page([self.serialize(row) for row in rows], page, page_size, total)

    def get(self, well_id: UUID, item_id: UUID) -> WellUnplannedItemRead:
        return self.serialize(self._require(well_id, item_id))

    def create(self, well_id: UUID, payload: WellUnplannedItemCreate) -> WellUnplannedItemRead:
        well = self.require_well(well_id)
        values = payload.model_dump(exclude_unset=True)
        self._check_references(
            values,
            {
                "vendor_id": Vendor,
                "currency_id": Currency,
                "unit_id": Unit,
                "cost_code_id": CostCode,
                "afe_snapshot_id": AfeSnapshot,
            },
        )
        description = (payload.item_description or "").strip()
        if payload.catalog_item_id is not None:
            item = self.session.get(CatalogItem, payload.catalog_item_id)
            if item is None:
                raise BusinessValidationError(
                    "catalog_item_id does not reference an existing record"
                )
            if payload.item_kind in {"service", "tangible"} and item.item_type != payload.item_kind:
                raise BusinessValidationError(
                    f"catalog_item_id must reference a {payload.item_kind}"
                )
            description = description or f"{item.code} — {item.name}"

        record = WellUnplannedItem(
            well_id=well.id,
            reference=payload.reference or self._next_reference(well.id),
            afe_snapshot_id=payload.afe_snapshot_id or self._latest_afe_snapshot_id(well.id),
            item_kind=payload.item_kind,
            catalog_item_id=payload.catalog_item_id,
            item_description=description,
            cost_code_id=payload.cost_code_id,
            vendor_id=payload.vendor_id,
            currency_id=payload.currency_id,
            unit_id=payload.unit_id,
            quantity=payload.quantity,
            unit_rate=payload.unit_rate,
            amount=Decimal(payload.quantity) * Decimal(payload.unit_rate),
            reason_code=payload.reason_code,
            justification=payload.justification,
            incurred_on=payload.incurred_on,
            source_document_reference=payload.source_document_reference,
            status="draft",
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(record)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                "An out-of-AFE entry with this reference already exists for the well"
            ) from exc
        self.session.refresh(record)
        return self.serialize(record)

    def update(
        self, well_id: UUID, item_id: UUID, payload: WellUnplannedItemUpdate
    ) -> WellUnplannedItemRead:
        record = self._require(well_id, item_id)
        if record.status not in {"draft", "rejected"}:
            raise ConflictError(
                f"An out-of-AFE entry in '{record.status}' can no longer be edited."
            )
        values = payload.model_dump(exclude_unset=True)
        self._check_references(
            values,
            {
                "vendor_id": Vendor,
                "currency_id": Currency,
                "unit_id": Unit,
                "cost_code_id": CostCode,
                "catalog_item_id": CatalogItem,
                "afe_snapshot_id": AfeSnapshot,
            },
        )
        for field, value in values.items():
            setattr(record, field, value)
        record.amount = Decimal(record.quantity) * Decimal(record.unit_rate)
        record.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(record)
        return self.serialize(record)

    def submit(self, well_id: UUID, item_id: UUID) -> WellUnplannedItemRead:
        record = self._require(well_id, item_id)
        self._transition(record, "submitted")
        record.submitted_at = datetime.now(UTC)
        record.submitted_by = self.actor_id
        record.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(record)
        return self.serialize(record)

    def approve(
        self, well_id: UUID, item_id: UUID, payload: WellUnplannedDecision
    ) -> WellUnplannedItemRead:
        """Approve the deviation and, when it names a catalogue item, price it.

        Approval never touches the AFE. It records the variance and, so the
        remainder of the operation uses one consistent rate, adds the item to
        the well rate book already locked.
        """

        record = self._require(well_id, item_id)
        self._transition(record, "approved")
        record.decided_at = datetime.now(UTC)
        record.decided_by = self.actor_id
        record.decision_note = payload.decision_note
        record.updated_by = self.actor_id
        if payload.add_to_rate_book and record.catalog_item_id is not None:
            self._attach_rate_book_entry(record)
        self.session.commit()
        self.session.refresh(record)
        return self.serialize(record)

    def reject(
        self, well_id: UUID, item_id: UUID, payload: WellUnplannedDecision
    ) -> WellUnplannedItemRead:
        record = self._require(well_id, item_id)
        self._transition(record, "rejected")
        record.decided_at = datetime.now(UTC)
        record.decided_by = self.actor_id
        record.decision_note = payload.decision_note
        record.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(record)
        return self.serialize(record)

    def cancel(
        self, well_id: UUID, item_id: UUID, payload: WellUnplannedDecision
    ) -> WellUnplannedItemRead:
        record = self._require(well_id, item_id)
        self._transition(record, "cancelled")
        record.decided_at = datetime.now(UTC)
        record.decided_by = self.actor_id
        record.decision_note = payload.decision_note
        record.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(record)
        return self.serialize(record)

    # -- helpers ----------------------------------------------------------
    def _transition(self, record: WellUnplannedItem, target: str) -> None:
        try:
            record.status = unplanned_transition(record.status, target)
        except UnplannedTransitionError as exc:
            raise _translate_rule_error(exc) from exc

    def _attach_rate_book_entry(self, record: WellUnplannedItem) -> None:
        locked_at = datetime.now(UTC)
        if record.item_kind == "service" and record.well_service_rate_id is None:
            existing = self.session.scalar(
                select(WellServiceRate).where(
                    WellServiceRate.well_id == record.well_id,
                    WellServiceRate.service_id == record.catalog_item_id,
                )
            )
            if existing is not None:
                record.well_service_rate_id = existing.id
                return
            unit_id = record.unit_id or self._default_unit_id(record.catalog_item_id)
            if unit_id is None:
                raise BusinessValidationError(
                    "unit_id is required to price an unplanned service in the rate book"
                )
            entry = WellServiceRate(
                well_id=record.well_id,
                service_id=record.catalog_item_id,
                vendor_id=record.vendor_id,
                currency_id=record.currency_id,
                unit_id=unit_id,
                rate_basis="per_service",
                operating_rate=record.unit_rate,
                origin="unplanned",
                status="locked",
                locked_at=locked_at,
                notes=f"Out-of-AFE entry {record.reference}: {record.justification}",
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
            self.session.add(entry)
            self.session.flush()
            record.well_service_rate_id = entry.id
            self._log(
                well_id=record.well_id,
                scope="service",
                change_type="unplanned_added",
                item_code=entry.service.code,
                item_name=entry.service.name,
                revision_number=1,
                previous_rates=None,
                new_rates=_snapshot(entry, SERVICE_RATE_FIELDS),
                reason=f"Out-of-AFE {record.reference}: {record.justification}",
                service_rate_id=entry.id,
            )
        elif record.item_kind == "tangible" and record.well_tangible_rate_id is None:
            existing_tangible = self.session.scalar(
                select(WellTangibleRate).where(
                    WellTangibleRate.well_id == record.well_id,
                    WellTangibleRate.tangible_id == record.catalog_item_id,
                )
            )
            if existing_tangible is not None:
                record.well_tangible_rate_id = existing_tangible.id
                return
            unit_id = record.unit_id or self._default_unit_id(record.catalog_item_id)
            if unit_id is None:
                raise BusinessValidationError(
                    "unit_id is required to price an unplanned tangible in the rate book"
                )
            master = self.current_master_price(record.catalog_item_id)  # type: ignore[arg-type]
            entry_tangible = WellTangibleRate(
                well_id=record.well_id,
                tangible_id=record.catalog_item_id,
                vendor_id=record.vendor_id,
                currency_id=record.currency_id,
                unit_id=unit_id,
                unit_rate=record.unit_rate,
                master_price_id=master.id if master else None,
                master_unit_rate=master.unit_price if master else None,
                master_effective_from=master.effective_from if master else None,
                is_overridden=bool(
                    master and Decimal(record.unit_rate) != Decimal(master.unit_price)
                ),
                override_reason=f"Out-of-AFE entry {record.reference}",
                origin="unplanned",
                status="locked",
                locked_at=locked_at,
                notes=f"Out-of-AFE entry {record.reference}: {record.justification}",
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
            self.session.add(entry_tangible)
            self.session.flush()
            record.well_tangible_rate_id = entry_tangible.id
            self._log(
                well_id=record.well_id,
                scope="tangible",
                change_type="unplanned_added",
                item_code=entry_tangible.tangible.code,
                item_name=entry_tangible.tangible.name,
                revision_number=1,
                previous_rates=None,
                new_rates=_snapshot(entry_tangible, TANGIBLE_RATE_FIELDS),
                reason=f"Out-of-AFE {record.reference}: {record.justification}",
                tangible_rate_id=entry_tangible.id,
            )

    def _default_unit_id(self, item_id: UUID | None) -> UUID | None:
        if item_id is None:
            return None
        item = self.session.get(CatalogItem, item_id)
        return item.default_unit_id if item else None

    def _next_reference(self, well_id: UUID) -> str:
        count = int(
            self.session.scalar(
                select(func.count())
                .select_from(WellUnplannedItem)
                .where(WellUnplannedItem.well_id == well_id)
            )
            or 0
        )
        return f"OOA-{count + 1:04d}"

    def _latest_afe_snapshot_id(self, well_id: UUID) -> UUID | None:
        snapshot = self.session.scalars(
            select(AfeSnapshot)
            .join(EstimateVersion, AfeSnapshot.estimate_version_id == EstimateVersion.id)
            .join(CostEstimate, EstimateVersion.estimate_id == CostEstimate.id)
            .join(Afe, CostEstimate.afe_id == Afe.id)
            .where(Afe.well_id == well_id)
            .order_by(AfeSnapshot.issue_date.desc(), AfeSnapshot.created_at.desc())
        ).first()
        return snapshot.id if snapshot else None

    def _require(self, well_id: UUID, item_id: UUID) -> WellUnplannedItem:
        record = self.session.get(WellUnplannedItem, item_id)
        if record is None or record.well_id != well_id:
            raise NotFoundError("Out-of-AFE entry not found")
        return record

    @staticmethod
    def serialize(record: WellUnplannedItem) -> WellUnplannedItemRead:
        return WellUnplannedItemRead.model_validate(record).model_copy(
            update={
                "catalog_item_code": record.catalog_item.code if record.catalog_item else None,
                "vendor_code": record.vendor.code if record.vendor else None,
                "currency_code": record.currency.code,
                "unit_code": record.unit.code if record.unit else None,
                "cost_code": record.cost_code.code if record.cost_code else None,
            }
        )


class WellCostExposureService(_WellScopedService):
    """The variance view: approved AFE versus everything raised outside it."""

    def summary(self, well_id: UUID) -> WellCostExposureRead:
        well = self.require_well(well_id)
        snapshot = self._latest_afe_snapshot(well_id)
        approved_total, approved_count = self._unplanned_totals(well_id, "approved")
        pending_total, pending_count = self._unplanned_totals(well_id, "submitted")
        exposure = summarise_exposure(
            afe_total=snapshot.grand_total if snapshot else None,
            approved_unplanned_total=approved_total,
            pending_unplanned_total=pending_total,
        )
        services = int(
            self.session.scalar(
                select(func.count())
                .select_from(WellServiceRate)
                .where(
                    WellServiceRate.well_id == well_id, WellServiceRate.is_active.is_(True)
                )
            )
            or 0
        )
        tangibles = int(
            self.session.scalar(
                select(func.count())
                .select_from(WellTangibleRate)
                .where(
                    WellTangibleRate.well_id == well_id, WellTangibleRate.is_active.is_(True)
                )
            )
            or 0
        )
        return WellCostExposureRead(
            well_id=well.id,
            well_code=well.code,
            well_name=well.name,
            rig_name=well.rig_name,
            well_status=well.status,
            rates_locked_at=well.rates_locked_at,
            currency_code=snapshot.currency_code if snapshot else None,
            afe_number=snapshot.afe_number if snapshot else None,
            afe_total=exposure.afe_total,
            approved_unplanned_total=exposure.approved_unplanned_total,
            pending_unplanned_total=exposure.pending_unplanned_total,
            committed_total=exposure.committed_total,
            variance_amount=exposure.variance_amount,
            variance_percent=exposure.variance_percent,
            approved_unplanned_count=approved_count,
            pending_unplanned_count=pending_count,
            rate_book_services=services,
            rate_book_tangibles=tangibles,
        )

    def _unplanned_totals(self, well_id: UUID, status: str) -> tuple[Decimal, int]:
        row = self.session.execute(
            select(func.coalesce(func.sum(WellUnplannedItem.amount), 0), func.count()).where(
                WellUnplannedItem.well_id == well_id,
                WellUnplannedItem.status == status,
                WellUnplannedItem.is_active.is_(True),
            )
        ).one()
        return Decimal(str(row[0] or 0)), int(row[1] or 0)

    def _latest_afe_snapshot(self, well_id: UUID) -> AfeSnapshot | None:
        return self.session.scalars(
            select(AfeSnapshot)
            .join(EstimateVersion, AfeSnapshot.estimate_version_id == EstimateVersion.id)
            .join(CostEstimate, EstimateVersion.estimate_id == CostEstimate.id)
            .join(Afe, CostEstimate.afe_id == Afe.id)
            .where(Afe.well_id == well_id)
            .order_by(AfeSnapshot.issue_date.desc(), AfeSnapshot.created_at.desc())
        ).first()


__all__ = [
    "WellCostExposureService",
    "WellRateBookService",
    "WellUnplannedItemService",
]
