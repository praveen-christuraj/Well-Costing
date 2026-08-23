"""Resolution and administration of the configurable dropdown registry.

Screens ask this service for the options of a *slot* — ``afe.line.item``,
``daily_cost.sub_activity`` — and it decides what to read. The decision comes
from three layers, in order:

1. the slot's declared default source (code, always present);
2. the super administrator's stored binding, if the slot is not locked;
3. runtime narrowing — the parent selection of a cascade, a search term, and
   for well-scoped slots the well being worked on.

Because layer 1 always exists, a fresh database behaves correctly with no
configuration at all; the binding table only ever refines it.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.domain.reference.slots import MODULES, SLOTS, DropdownSlot, get_slot
from app.domain.reference.sources import (
    DEFAULT_LABEL_TEMPLATE,
    LABEL_TEMPLATES,
    SOURCES,
    ReferenceSource,
    get_source,
)
from app.models.categories import WellActivity
from app.models.master_data import CatalogItem, PurchaseOrder, ServiceOrder
from app.models.reference_bindings import DropdownBinding
from app.schemas.reference import (
    DropdownBindingRead,
    DropdownBindingWrite,
    DropdownRegistryRead,
    DropdownSlotRead,
    ReferenceOption,
    ReferenceOptionsRead,
    ReferenceSourceRead,
)
from app.services.audit import log_entity_action

MAX_OPTIONS = 1000

_PROCUREMENT_MODELS: dict[str, type[Any]] = {
    "service-orders": ServiceOrder,
    "purchase-orders": PurchaseOrder,
}


def _source_read(source: ReferenceSource) -> ReferenceSourceRead:
    return ReferenceSourceRead(
        code=source.code,
        label=source.label,
        kind=source.kind,
        entity=source.entity,
        description=source.description,
        parent_field=source.parent_field,
        parent_source=source.parent_source,
        filterable=list(source.filterable),
    )


class ReferenceBindingService:
    """Reads the registry, applies overrides, and resolves options."""

    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session = session
        self.actor_id = actor_id

    # -- registry ---------------------------------------------------------
    def _binding(self, slot_code: str) -> DropdownBinding | None:
        return self.session.scalar(
            select(DropdownBinding).where(
                DropdownBinding.slot_code == slot_code,
                DropdownBinding.is_active.is_(True),
            )
        )

    def _slot_read(self, slot: DropdownSlot) -> DropdownSlotRead:
        binding = None if slot.locked else self._binding(slot.code)
        effective = binding.source_code if binding else slot.default_source
        filters = dict(slot.fixed_filters)
        if binding and binding.filters:
            filters.update(binding.filters)
        return DropdownSlotRead(
            code=slot.code,
            module=slot.module,
            label=slot.label,
            description=slot.description,
            default_source=slot.default_source,
            allowed_sources=list(slot.selectable_sources),
            cascades_from=slot.cascades_from,
            locked=slot.locked,
            effective_source=effective,
            is_overridden=binding is not None,
            binding=DropdownBindingRead.model_validate(binding) if binding else None,
            label_template=(
                binding.label_template
                if binding and binding.label_template
                else DEFAULT_LABEL_TEMPLATE
            ),
            filters=filters,
        )

    def registry(self, module: str | None = None) -> DropdownRegistryRead:
        """The complete registry: modules, sources, and slots with their bindings."""

        slots = [slot for slot in SLOTS if module is None or slot.module == module]
        return DropdownRegistryRead(
            modules=[{"key": key, "label": label} for key, label in MODULES],
            sources=[_source_read(source) for source in SOURCES],
            slots=[self._slot_read(slot) for slot in slots],
        )

    def get_slot_read(self, slot_code: str) -> DropdownSlotRead:
        return self._slot_read(self._require_slot(slot_code))

    @staticmethod
    def _require_slot(slot_code: str) -> DropdownSlot:
        try:
            return get_slot(slot_code)
        except KeyError as exc:
            raise NotFoundError(f"Unknown dropdown slot: {slot_code}") from exc

    @staticmethod
    def _require_source(source_code: str) -> ReferenceSource:
        try:
            return get_source(source_code)
        except KeyError as exc:
            raise NotFoundError(f"Unknown reference source: {source_code}") from exc

    # -- administration ---------------------------------------------------
    def set_binding(self, slot_code: str, payload: DropdownBindingWrite) -> DropdownSlotRead:
        """Point a slot at a different registered source."""

        slot = self._require_slot(slot_code)
        if slot.locked:
            raise BusinessValidationError(
                f"'{slot.label}' is a structural dropdown and cannot be rebound"
            )
        source = self._require_source(payload.source_code)
        if payload.source_code not in slot.selectable_sources:
            allowed = ", ".join(slot.selectable_sources)
            raise BusinessValidationError(
                f"'{source.label}' is not permitted for this dropdown. Allowed sources: {allowed}"
            )
        if payload.label_template and payload.label_template not in LABEL_TEMPLATES:
            allowed = ", ".join(LABEL_TEMPLATES)
            raise BusinessValidationError(f"label_template must be one of: {allowed}")
        unknown = set(payload.filters) - set(source.filterable)
        if unknown:
            raise BusinessValidationError(
                f"'{source.label}' cannot be filtered by: {', '.join(sorted(unknown))}"
            )

        binding = self.session.scalar(
            select(DropdownBinding).where(DropdownBinding.slot_code == slot_code)
        )
        if binding is None:
            binding = DropdownBinding(slot_code=slot_code, created_by=self.actor_id)
            self.session.add(binding)
        binding.source_code = payload.source_code
        binding.filters = dict(payload.filters)
        binding.label_template = payload.label_template
        binding.sort_by = payload.sort_by
        binding.include_inactive = payload.include_inactive
        binding.notes = payload.notes
        binding.is_active = True
        binding.updated_by = self.actor_id
        self.session.flush()
        log_entity_action(
            self.session,
            self.actor_id,
            "update",
            "dropdown_binding",
            entity_id=binding.id,
            entity_code=slot_code,
            details=payload.model_dump(),
        )
        self.session.commit()
        return self.get_slot_read(slot_code)

    def reset_binding(self, slot_code: str) -> DropdownSlotRead:
        """Return a slot to the source declared in code."""

        self._require_slot(slot_code)
        binding = self.session.scalar(
            select(DropdownBinding).where(DropdownBinding.slot_code == slot_code)
        )
        if binding is not None:
            self.session.delete(binding)
            self.session.flush()
            log_entity_action(
                self.session,
                self.actor_id,
                "delete",
                "dropdown_binding",
                entity_id=binding.id,
                entity_code=slot_code,
                details=None,
            )
            self.session.commit()
        return self.get_slot_read(slot_code)

    # -- resolution -------------------------------------------------------
    def resolve(
        self,
        slot_code: str,
        *,
        parent_id: UUID | None = None,
        well_id: UUID | None = None,
        search: str | None = None,
        limit: int = 500,
        include_inactive: bool | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> ReferenceOptionsRead:
        """Options for one dropdown, ready to render."""

        slot_read = self._slot_read(self._require_slot(slot_code))
        source = self._require_source(slot_read.effective_source)
        binding_inactive = slot_read.binding.include_inactive if slot_read.binding else False
        show_inactive = binding_inactive if include_inactive is None else include_inactive

        filters: dict[str, Any] = dict(slot_read.filters)
        for key, value in (extra_filters or {}).items():
            if value not in (None, ""):
                filters[key] = value
        if parent_id is not None and source.parent_field:
            filters[source.parent_field] = parent_id
        if well_id is not None and source.kind == "well_scoped":
            filters["well_id"] = well_id

        options = self._read_options(
            source,
            filters=filters,
            search=search,
            limit=min(limit, MAX_OPTIONS),
            include_inactive=show_inactive,
            label_template=slot_read.label_template,
        )
        return ReferenceOptionsRead(
            slot=slot_code,
            source=source.code,
            total=len(options),
            options=options,
        )

    def _read_options(
        self,
        source: ReferenceSource,
        *,
        filters: dict[str, Any],
        search: str | None,
        limit: int,
        include_inactive: bool,
        label_template: str,
    ) -> list[ReferenceOption]:
        if source.kind == "static":
            return [
                ReferenceOption(value=value, label=label, code=value, name=label)
                for value, label in source.options
                if not search or search.lower() in label.lower()
            ]
        if source.kind == "well_scoped":
            return self._well_activity_options(filters, search, limit, include_inactive)
        if source.kind == "procurement":
            return self._procurement_options(source, filters, search, limit, include_inactive)
        model = self._model_for(source)
        statement: Select[Any] = select(model)
        if source.kind == "catalog" and source.entity:
            item_types = [value.strip() for value in source.entity.split(",") if value.strip()]
            statement = statement.where(CatalogItem.item_type.in_(item_types))
        statement = self._apply_common(model, statement, filters, search, include_inactive)
        statement = statement.order_by(model.code.asc()).limit(limit)
        records = self.session.scalars(statement).unique().all()
        return [self._option(record, source, label_template) for record in records]

    @staticmethod
    def _model_for(source: ReferenceSource) -> Any:
        if source.kind == "catalog":
            return CatalogItem
        from app.services.master_data import get_entity_config  # local: avoids a cycle

        return get_entity_config(str(source.entity)).model

    @staticmethod
    def _apply_common(
        model: Any,
        statement: Select[Any],
        filters: dict[str, Any],
        search: str | None,
        include_inactive: bool,
    ) -> Select[Any]:
        if not include_inactive and hasattr(model, "is_active"):
            statement = statement.where(model.is_active.is_(True))
        for field, value in filters.items():
            column = getattr(model, field, None)
            if column is not None and value not in (None, ""):
                statement = statement.where(column == value)
        if search:
            pattern = f"%{search.strip()}%"
            clauses = [
                getattr(model, field).ilike(pattern)
                for field in ("code", "name")
                if hasattr(model, field)
            ]
            if clauses:
                statement = statement.where(or_(*clauses))
        return statement

    def _well_activity_options(
        self,
        filters: dict[str, Any],
        search: str | None,
        limit: int,
        include_inactive: bool,
    ) -> list[ReferenceOption]:
        well_id = filters.get("well_id")
        if not well_id:
            raise BusinessValidationError("well_id is required to list well sub-activities")
        statement = select(WellActivity).where(WellActivity.well_id == well_id)
        if not include_inactive:
            statement = statement.where(WellActivity.is_active.is_(True))
        if filters.get("activity_id"):
            statement = statement.where(WellActivity.activity_id == filters["activity_id"])
        if search:
            statement = statement.where(WellActivity.name.ilike(f"%{search.strip()}%"))
        statement = statement.order_by(WellActivity.name.asc()).limit(limit)
        return [
            ReferenceOption(
                value=str(record.id),
                label=record.name,
                code=record.activity.code if record.activity else None,
                name=record.name,
                parent_id=str(record.activity_id),
                meta={"responsible_party": record.responsible_party or ""},
            )
            for record in self.session.scalars(statement).unique().all()
        ]

    def _procurement_options(
        self,
        source: ReferenceSource,
        filters: dict[str, Any],
        search: str | None,
        limit: int,
        include_inactive: bool,
    ) -> list[ReferenceOption]:
        model = _PROCUREMENT_MODELS[str(source.entity)]
        statement = select(model)
        if not include_inactive:
            statement = statement.where(model.is_active.is_(True))
        for field in ("vendor_id", "status"):
            if filters.get(field):
                statement = statement.where(getattr(model, field) == filters[field])
        if search:
            pattern = f"%{search.strip()}%"
            statement = statement.where(
                or_(model.order_number.ilike(pattern), model.title.ilike(pattern))
            )
        statement = statement.order_by(model.order_number.asc()).limit(limit)
        return [
            ReferenceOption(
                value=str(record.id),
                label=f"{record.order_number} — {record.title}",
                code=record.order_number,
                name=record.title,
                meta={"status": record.status},
            )
            for record in self.session.scalars(statement).unique().all()
        ]

    @staticmethod
    def _option(record: Any, source: ReferenceSource, template: str) -> ReferenceOption:
        code = str(getattr(record, "code", "") or "")
        name = str(getattr(record, "name", "") or "")
        parent_value = getattr(record, source.parent_field, None) if source.parent_field else None
        meta: dict[str, Any] = {}
        for field in (
            "item_type",
            "rate_basis",
            "default_unit_id",
            "cost_code_id",
            "cost_category_id",
            "primary_category_id",
            "secondary_category_id",
            "tertiary_category_id",
            "sequence",
        ):
            value = getattr(record, field, None)
            if value is not None:
                meta[field] = str(value)
        return ReferenceOption(
            value=str(record.id),
            label=template.format(code=code, name=name).strip(" —"),
            code=code,
            name=name,
            parent_id=str(parent_value) if parent_value is not None else None,
            meta=meta,
        )

    # -- diagnostics ------------------------------------------------------
    def usage_counts(self) -> dict[str, int]:
        """Row counts per source, so the console can show what is configured."""

        counts: dict[str, int] = {}
        for source in SOURCES:
            if source.kind in {"static", "well_scoped"}:
                continue
            try:
                if source.kind == "procurement":
                    model = _PROCUREMENT_MODELS[str(source.entity)]
                    statement = select(func.count()).select_from(model)
                elif source.kind == "catalog":
                    statement = select(func.count()).select_from(CatalogItem)
                    if source.entity:
                        item_types = [value.strip() for value in source.entity.split(",")]
                        statement = statement.where(CatalogItem.item_type.in_(item_types))
                else:
                    statement = select(func.count()).select_from(self._model_for(source))
                counts[source.code] = int(self.session.scalar(statement) or 0)
            except Exception:  # a missing table must not break the console
                counts[source.code] = 0
        return counts
