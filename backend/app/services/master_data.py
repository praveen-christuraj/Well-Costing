"""Cost-library application services and entity registry."""

from dataclasses import dataclass
from math import ceil
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.db.base import Base
from app.domain.afe.rate_basis import (
    RateBasisError,
    allowed_rate_bases,
    normalize_rate_basis,
    validate_rate_basis,
)
from app.models.master_data import (
    CatalogItem,
    CementAdditive,
    CostCategory,
    CostCode,
    Currency,
    Equipment,
    HoleSection,
    ItemCategory,
    ItemSubCategory,
    Material,
    MudChemical,
    Rate,
    Service,
    Tangible,
    Unit,
    Vendor,
)
from app.repositories.master_data import MasterDataRepository, RateRepository
from app.schemas.master_data import (
    BulkRowError,
    BulkValidationResult,
    MasterDataCreate,
    MasterDataRead,
    MasterDataUpdate,
    PageResponse,
    RateCreate,
    RateRead,
    RateUpdate,
)
from app.services.audit import log_entity_action


@dataclass(frozen=True)
class EntityConfig:
    model: type[Base]
    fields: frozenset[str]
    item_type: str | None = None


COMMON_FIELDS = frozenset({"code", "name", "description", "is_active"})
VENDOR_FIELDS = COMMON_FIELDS | {
    "vendor_type",
    "contact_person",
    "email",
    "phone",
    "country",
}
CATALOG_FIELDS = COMMON_FIELDS | {
    "cost_category_id",
    "cost_code_id",
    "default_unit_id",
    "item_category_id",
    "sub_category_id",
    "material_number",
    "specification",
    "manufacturer",
}
ENTITY_CONFIGS: dict[str, EntityConfig] = {
    "units": EntityConfig(Unit, COMMON_FIELDS | {"symbol"}),
    "currencies": EntityConfig(Currency, COMMON_FIELDS | {"symbol"}),
    "hole-sections": EntityConfig(HoleSection, COMMON_FIELDS),
    "cost-categories": EntityConfig(CostCategory, COMMON_FIELDS | {"parent_id"}),
    "cost-codes": EntityConfig(CostCode, COMMON_FIELDS | {"cost_category_id"}),
    "vendors": EntityConfig(Vendor, VENDOR_FIELDS),
    "item-categories": EntityConfig(ItemCategory, COMMON_FIELDS | {"applies_to"}),
    "item-subcategories": EntityConfig(ItemSubCategory, COMMON_FIELDS | {"applies_to"}),
    "services": EntityConfig(Service, CATALOG_FIELDS | {"rate_basis"}, "service"),
    "tangibles": EntityConfig(Tangible, CATALOG_FIELDS, "tangible"),
    "materials": EntityConfig(Material, CATALOG_FIELDS, "material"),
    "equipment": EntityConfig(Equipment, CATALOG_FIELDS, "equipment"),
    "mud-chemicals": EntityConfig(MudChemical, CATALOG_FIELDS | {"rate_basis"}, "mud_chemical"),
    "cement-additives": EntityConfig(
        CementAdditive, CATALOG_FIELDS | {"rate_basis"}, "cement_additive"
    ),
}


def get_entity_config(entity: str) -> EntityConfig:
    try:
        return ENTITY_CONFIGS[entity]
    except KeyError as exc:
        raise NotFoundError(f"Unknown master-data entity: {entity}") from exc


def _audit_master(session, actor_id, action, entity_type, entity_id, entity_code=None, details=None):
    log_entity_action(
        session,
        actor_id,
        action,
        entity_type,
        entity_id=entity_id,
        entity_code=entity_code,
        details=details,
    )

class MasterDataService:
    """Generic audited workflow for reference and catalogue entities."""

    def __init__(self, session: Session, entity: str, actor_id: UUID) -> None:
        self.session = session
        self.entity = entity
        self.actor_id = actor_id
        self.config = get_entity_config(entity)
        self.repository: MasterDataRepository[Any] = MasterDataRepository(
            session, self.config.model
        )

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        is_active: bool | None,
        sort_by: str,
        sort_order: str,
        filters: dict[str, Any] | None = None,
    ) -> PageResponse:
        items, total = self.repository.list(
            page=page,
            page_size=page_size,
            search=search,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
        )
        return PageResponse(
            items=[self._serialize(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )

    def get(self, item_id: UUID) -> MasterDataRead:
        item = self.repository.get(item_id)
        if item is None:
            raise NotFoundError(f"{self.entity} record not found")
        return self._serialize(item)

    def create(self, payload: MasterDataCreate, *, commit: bool = True) -> MasterDataRead:
        values = self._values(payload)
        self._validate_references(values)
        model = self.config.model
        instance = model(**values, created_by=self.actor_id, updated_by=self.actor_id)
        try:
            self.repository.add(instance)
            self.session.flush()
            _audit_master(self.session, self.actor_id, "create", self.entity, instance.id, instance.code, values)
            if commit:
                self.session.commit()
                self.session.refresh(instance)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                f"A {self.entity} record with code '{values['code']}' already exists"
            ) from exc
        return self._serialize(instance)

    def update(
        self, item_id: UUID, payload: MasterDataUpdate, *, commit: bool = True
    ) -> MasterDataRead:
        instance = self.repository.get(item_id)
        if instance is None:
            raise NotFoundError(f"{self.entity} record not found")
        values = self._values(payload)
        self._validate_references(values, current_id=item_id)
        for field, value in values.items():
            setattr(instance, field, value)
        instance.updated_by = self.actor_id
        try:
            self.session.flush()
            _audit_master(self.session, self.actor_id, "update", self.entity, instance.id, instance.code, values)
            if commit:
                self.session.commit()
                self.session.refresh(instance)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("The update conflicts with an existing code or reference") from exc
        return self._serialize(instance)

    def deactivate(self, item_id: UUID) -> None:
        instance = self.repository.get(item_id)
        if instance is None:
            raise NotFoundError(f"{self.entity} record not found")
        instance.is_active = False
        instance.updated_by = self.actor_id
        self.session.flush()
        _audit_master(self.session, self.actor_id, "soft_delete", self.entity, instance.id, instance.code, None)
        self.session.commit()

    def recover(self, item_id: UUID) -> MasterDataRead:
        instance = self.repository.get(item_id)
        if instance is None:
            raise NotFoundError(f"{self.entity} record not found")
        if instance.is_active:
            raise BusinessValidationError("Record is not deleted and cannot be recovered")
        # Check if another active record with same code exists (prevent duplicate)
        existing = self.repository.get_by_code(instance.code)
        if existing is not None and existing.id != instance.id and existing.is_active:
            raise BusinessValidationError(f"Cannot recover: an active {self.entity} with code '{instance.code}' already exists")
        instance.is_active = True
        instance.updated_by = self.actor_id
        self.session.flush()
        _audit_master(self.session, self.actor_id, "recover", self.entity, instance.id, instance.code, None)
        self.session.commit()
        self.session.refresh(instance)
        return self._serialize(instance)

    def hard_delete(self, item_id: UUID) -> None:
        instance = self.repository.get(item_id)
        if instance is None:
            raise NotFoundError(f"{self.entity} record not found")
        if instance.is_active:
            raise BusinessValidationError("Record must be soft-deleted before permanent deletion")
        code = instance.code
        try:
            self.repository.delete(instance)
            self.session.flush()
            _audit_master(self.session, self.actor_id, "hard_delete", self.entity, item_id, code, None)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                f"This {self.entity} record is referenced by other records and cannot be deleted. Deactivate it instead."
            ) from exc

    def delete(self, item_id: UUID) -> None:
        """Permanently remove a record, refusing when it is still referenced."""

        instance = self.repository.get(item_id)
        if instance is None:
            raise NotFoundError(f"{self.entity} record not found")
        code = instance.code
        try:
            self.repository.delete(instance)
            self.session.flush()
            _audit_master(self.session, self.actor_id, "hard_delete", self.entity, item_id, code, None)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                f"This {self.entity} record is referenced by other records and cannot be "
                "deleted. Deactivate it instead."
            ) from exc

    def validate_bulk(self, rows: list[MasterDataCreate]) -> BulkValidationResult:
        errors: list[BulkRowError] = []
        seen: dict[str, int] = {}
        for index, row in enumerate(rows):
            code = row.code.strip().upper()
            if code in seen:
                errors.append(
                    BulkRowError(
                        row_index=index,
                        column="code",
                        code="duplicate_in_batch",
                        message=f"Code duplicates row {seen[code] + 1}",
                    )
                )
            else:
                seen[code] = index
            if self.repository.get_by_code(code) is not None:
                errors.append(
                    BulkRowError(
                        row_index=index,
                        column="code",
                        code="duplicate_existing",
                        message="Code already exists",
                    )
                )
            try:
                self._validate_references(self._values(row))
            except BusinessValidationError as exc:
                errors.append(
                    BulkRowError(
                        row_index=index,
                        code="invalid_reference",
                        message=exc.message,
                    )
                )
        invalid_rows = {error.row_index for error in errors}
        return BulkValidationResult(
            valid=not errors,
            total_rows=len(rows),
            valid_rows=len(rows) - len(invalid_rows),
            errors=errors,
        )

    def bulk_create(self, rows: list[MasterDataCreate]) -> list[MasterDataRead]:
        validation = self.validate_bulk(rows)
        if not validation.valid:
            raise BusinessValidationError("Bulk validation failed", validation.model_dump())
        created: list[MasterDataRead] = []
        try:
            for row in rows:
                created.append(self.create(row, commit=False))
            self.session.commit()
            _audit_master(self.session, self.actor_id, "bulk_create", self.entity, None, None, {"count": len(rows)})
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return created

    def bulk_update(self, rows: list[tuple[UUID, MasterDataUpdate]]) -> list[MasterDataRead]:
        updated: list[MasterDataRead] = []
        try:
            for item_id, payload in rows:
                updated.append(self.update(item_id, payload, commit=False))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return updated

    def _values(self, payload: MasterDataCreate | MasterDataUpdate) -> dict[str, Any]:
        supplied = payload.model_dump(exclude_unset=True)
        unsupported = set(supplied) - self.config.fields
        if unsupported:
            raise BusinessValidationError(
                f"Fields are not supported for {self.entity}: {', '.join(sorted(unsupported))}"
            )
        if "code" in supplied and supplied["code"] is not None:
            supplied["code"] = str(supplied["code"]).strip().upper()
        if "name" in supplied and supplied["name"] is not None:
            supplied["name"] = str(supplied["name"]).strip()
        if "rate_basis" in supplied and supplied["rate_basis"] is not None:
            supplied["rate_basis"] = normalize_rate_basis(str(supplied["rate_basis"]))
        return supplied

    def _validate_references(self, values: dict[str, Any], current_id: UUID | None = None) -> None:
        if (
            self.entity == "cost-codes"
            and current_id is None
            and not values.get("cost_category_id")
        ):
            raise BusinessValidationError("cost_category_id is required for cost codes")
        vendor_type = values.get("vendor_type")
        if vendor_type is not None and vendor_type not in {"third_party", "inhouse"}:
            raise BusinessValidationError("vendor_type must be 'third_party' or 'inhouse'")
        applies_to = values.get("applies_to")
        if applies_to is not None and applies_to not in {
            "service",
            "tangible",
            "mud_chemical",
            "cement_additive",
        }:
            raise BusinessValidationError(
                "applies_to must be one of service, tangible, mud_chemical, cement_additive"
            )
        rate_basis = values.get("rate_basis")
        if rate_basis is not None:
            item_type = self.config.item_type or ""
            try:
                values["rate_basis"] = validate_rate_basis(item_type, str(rate_basis))
            except RateBasisError as exc:
                allowed = ", ".join(allowed_rate_bases(item_type))
                raise BusinessValidationError(
                    f"rate_basis must be one of {allowed} for {self.entity}"
                ) from exc
        reference_models = {
            "parent_id": CostCategory,
            "cost_category_id": CostCategory,
            "cost_code_id": CostCode,
            "default_unit_id": Unit,
            "item_category_id": ItemCategory,
            "sub_category_id": ItemSubCategory,
        }
        for field, model in reference_models.items():
            value = values.get(field)
            if value is not None and self.session.get(model, value) is None:
                raise BusinessValidationError(f"{field} does not reference an existing record")
        if values.get("parent_id") is not None and values["parent_id"] == current_id:
            raise BusinessValidationError("A cost category cannot be its own parent")

    def _serialize(self, instance: Any) -> MasterDataRead:
        values: dict[str, Any] = {
            "id": instance.id,
            "code": instance.code,
            "name": instance.name,
            "description": instance.description,
            "is_active": instance.is_active,
            "created_at": instance.created_at,
            "updated_at": instance.updated_at,
            "created_by": instance.created_by,
            "updated_by": instance.updated_by,
            "symbol": getattr(instance, "symbol", None),
            "parent_id": getattr(instance, "parent_id", None),
            "cost_category_id": getattr(instance, "cost_category_id", None),
            "cost_code_id": getattr(instance, "cost_code_id", None),
            "default_unit_id": getattr(instance, "default_unit_id", None),
            "item_category_id": getattr(instance, "item_category_id", None),
            "sub_category_id": getattr(instance, "sub_category_id", None),
            "rate_basis": getattr(instance, "rate_basis", None),
            "material_number": getattr(instance, "material_number", None),
            "specification": getattr(instance, "specification", None),
            "manufacturer": getattr(instance, "manufacturer", None),
            "applies_to": getattr(instance, "applies_to", None),
            "vendor_type": getattr(instance, "vendor_type", None),
            "contact_person": getattr(instance, "contact_person", None),
            "email": getattr(instance, "email", None),
            "phone": getattr(instance, "phone", None),
            "country": getattr(instance, "country", None),
            "item_type": getattr(instance, "item_type", None),
        }
        if isinstance(instance, CostCategory):
            values["parent_code"] = instance.parent.code if instance.parent else None
        if isinstance(instance, CostCode):
            values["cost_category_code"] = instance.cost_category.code
        if isinstance(instance, CatalogItem):
            values.update(
                {
                    "cost_category_code": instance.cost_category.code
                    if instance.cost_category
                    else None,
                    "cost_code": instance.cost_code.code if instance.cost_code else None,
                    "default_unit_code": instance.default_unit.code
                    if instance.default_unit
                    else None,
                    "item_category_code": instance.item_category.code
                    if instance.item_category
                    else None,
                    "item_category_name": instance.item_category.name
                    if instance.item_category
                    else None,
                    "sub_category_code": instance.sub_category.code
                    if instance.sub_category
                    else None,
                    "sub_category_name": instance.sub_category.name
                    if instance.sub_category
                    else None,
                }
            )
        return MasterDataRead.model_validate(values)


class RateService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session = session
        self.actor_id = actor_id
        self.repository = RateRepository(session, Rate)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        is_active: bool | None,
        sort_by: str,
        sort_order: str,
    ) -> PageResponse:
        rates, total = self.repository.list(
            page=page,
            page_size=page_size,
            search=search,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return PageResponse(
            items=[self._serialize(rate) for rate in rates],
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )

    def get(self, rate_id: UUID) -> RateRead:
        rate = self.repository.get(rate_id)
        if rate is None:
            raise NotFoundError("Rate not found")
        return self._serialize(rate)

    def create(self, payload: RateCreate, *, commit: bool = True) -> RateRead:
        values = payload.model_dump()
        self._validate_references(values)
        rate = Rate(**values, created_by=self.actor_id, updated_by=self.actor_id)
        self.repository.add(rate)
        self.session.flush()
        _audit_master(self.session, self.actor_id, "create", "rates", rate.id, None, values)
        if commit:
            self.session.commit()
            self.session.refresh(rate)
        return self._serialize(rate)

    def update(self, rate_id: UUID, payload: RateUpdate, *, commit: bool = True) -> RateRead:
        rate = self.repository.get(rate_id)
        if rate is None:
            raise NotFoundError("Rate not found")
        values = payload.model_dump(exclude_unset=True)
        self._validate_references(values)
        for field, value in values.items():
            setattr(rate, field, value)
        if rate.effective_to is not None and rate.effective_to < rate.effective_from:
            raise BusinessValidationError("effective_to must be on or after effective_from")
        rate.updated_by = self.actor_id
        self.session.flush()
        _audit_master(self.session, self.actor_id, "update", "rates", rate.id, None, values)
        if commit:
            self.session.commit()
            self.session.refresh(rate)
        return self._serialize(rate)

    def deactivate(self, rate_id: UUID) -> None:
        rate = self.repository.get(rate_id)
        if rate is None:
            raise NotFoundError("Rate not found")
        rate.is_active = False
        rate.updated_by = self.actor_id
        self.session.flush()
        _audit_master(self.session, self.actor_id, "soft_delete", "rates", rate.id, None, None)
        self.session.commit()

    def validate_bulk(self, rows: list[RateCreate]) -> BulkValidationResult:
        errors: list[BulkRowError] = []
        for index, row in enumerate(rows):
            try:
                self._validate_references(row.model_dump())
            except BusinessValidationError as exc:
                errors.append(
                    BulkRowError(row_index=index, code="invalid_reference", message=exc.message)
                )
        invalid_rows = {error.row_index for error in errors}
        return BulkValidationResult(
            valid=not errors,
            total_rows=len(rows),
            valid_rows=len(rows) - len(invalid_rows),
            errors=errors,
        )

    def bulk_create(self, rows: list[RateCreate]) -> list[RateRead]:
        validation = self.validate_bulk(rows)
        if not validation.valid:
            raise BusinessValidationError("Bulk validation failed", validation.model_dump())
        created: list[RateRead] = []
        try:
            for row in rows:
                created.append(self.create(row, commit=False))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return created

    def bulk_update(self, rows: list[tuple[UUID, RateUpdate]]) -> list[RateRead]:
        updated: list[RateRead] = []
        try:
            for rate_id, payload in rows:
                updated.append(self.update(rate_id, payload, commit=False))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return updated

    def _validate_references(self, values: dict[str, Any]) -> None:
        references = {
            "item_id": CatalogItem,
            "vendor_id": Vendor,
            "currency_id": Currency,
            "unit_id": Unit,
        }
        for field, model in references.items():
            value = values.get(field)
            if value is not None and self.session.get(model, value) is None:
                raise BusinessValidationError(f"{field} does not reference an existing record")

    @staticmethod
    def _serialize(rate: Rate) -> RateRead:
        result = RateRead.model_validate(rate)
        return result.model_copy(
            update={
                "item_code": rate.item.code,
                "item_type": rate.item.item_type,
                "vendor_code": rate.vendor.code,
                "currency_code": rate.currency.code,
                "unit_code": rate.unit.code,
            }
        )
