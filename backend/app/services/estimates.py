"""Phase 4 estimate-build orchestration without cost calculations."""

from math import ceil
from typing import Never
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.models.afe import Afe
from app.models.estimates import CostEstimate, EstimateAssumption, EstimateItem, EstimateVersion
from app.models.master_data import CostCategory, Currency, Rate, Unit, Vendor
from app.schemas.estimates import (
    AssumptionUpsert,
    BulkAssignRequest,
    EstimateGenerateRequest,
    EstimateItemRead,
    EstimateItemUpdate,
    EstimateRead,
    EstimateVersionRead,
)
from app.schemas.master_data import PageResponse


class CostEstimateService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id

    def list_page(self, page: int, page_size: int, search: str | None) -> PageResponse:
        statement = select(CostEstimate)
        count = select(func.count()).select_from(CostEstimate)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                CostEstimate.code.ilike(pattern) | CostEstimate.title.ilike(pattern)
            )
            count = count.where(
                CostEstimate.code.ilike(pattern) | CostEstimate.title.ilike(pattern)
            )
        statement = (
            statement.order_by(CostEstimate.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        records = self.session.scalars(statement).unique().all()
        total = int(self.session.scalar(count) or 0)
        return PageResponse(
            items=[self.read(record, include_versions=False) for record in records],
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )

    def get(self, estimate_id: UUID) -> EstimateRead:
        estimate = self.session.get(CostEstimate, estimate_id)
        if estimate is None:
            raise NotFoundError("Estimate not found")
        return self.read(estimate, include_versions=True)

    def generate(self, payload: EstimateGenerateRequest) -> EstimateRead:
        afe = self.session.get(Afe, payload.afe_id)
        if afe is None or not afe.is_active:
            raise NotFoundError("AFE not found")
        if afe.status != "submitted":
            raise BusinessValidationError("Only a submitted afe can generate an estimate")
        currency = self.session.get(Currency, payload.currency_id)
        if currency is None or not currency.is_active:
            raise BusinessValidationError("currency_id must reference an active currency")
        estimate = CostEstimate(
            afe_id=afe.id,
            code=payload.code.strip().upper(),
            title=payload.title.strip(),
            currency_id=currency.id,
            current_version_number=1,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        version = EstimateVersion(
            version_number=1,
            status="pending_calculation",
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        estimate.versions.append(version)
        for source in afe.items:
            if not source.is_active:
                continue
            version.items.append(
                EstimateItem(
                    line_number=source.line_number,
                    afe_line_id=source.id,
                    catalog_item_id=source.catalog_item_id,
                    cost_code_id=source.cost_code_id,
                    vendor_id=None,
                    rate_id=None,
                    quantity=source.quantity,
                    unit_id=source.unit_id,
                    created_by=self.actor_id,
                    updated_by=self.actor_id,
                )
            )
        self.session.add(estimate)
        try:
            self.session.commit()
            self.session.refresh(estimate)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("Estimate code already exists") from exc
        return self.read(estimate, include_versions=True)

    def bulk_update_items(
        self, rows: list[tuple[UUID, EstimateItemUpdate]]
    ) -> list[EstimateItemRead]:
        changed: list[EstimateItem] = []
        try:
            for item_id, payload in rows:
                item = self._item(item_id)
                values = payload.model_dump(exclude_unset=True)
                self._validate_assignment(item, values.get("vendor_id"), values.get("rate_id"))
                if "unit_id" in values and values["unit_id"] is not None:
                    unit = self.session.get(Unit, values["unit_id"])
                    if unit is None or not unit.is_active:
                        raise BusinessValidationError("unit_id must reference an active unit")
                for field, value in values.items():
                    setattr(item, field, value)
                item.base_cost = item.contingency_cost = item.escalation_cost = item.total_cost = (
                    None
                )
                item.updated_by = self.actor_id
                changed.append(item)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return [self.read_item(item) for item in changed]

    def bulk_assign(self, version_id: UUID, payload: BulkAssignRequest) -> list[EstimateItemRead]:
        version = self._version(version_id)
        items = [self._item(item_id) for item_id in payload.item_ids]
        if any(item.estimate_version_id != version.id for item in items):
            raise BusinessValidationError("Every selected item must belong to the estimate version")
        result: list[EstimateItemRead] = []
        try:
            for item in items:
                self._validate_assignment(item, payload.vendor_id, payload.rate_id)
                if payload.vendor_id is not None:
                    item.vendor_id = payload.vendor_id
                if payload.rate_id is not None:
                    rate = self.session.get(Rate, payload.rate_id)
                    item.rate_id = payload.rate_id
                    item.vendor_id = rate.vendor_id if rate else item.vendor_id
                item.base_cost = item.contingency_cost = item.escalation_cost = item.total_cost = (
                    None
                )
                item.updated_by = self.actor_id
                result.append(self.read_item(item))
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return result

    def duplicate_items(self, version_id: UUID, item_ids: list[UUID]) -> list[EstimateItemRead]:
        version = self._version(version_id)
        sources = [self._item(item_id) for item_id in item_ids]
        if any(item.estimate_version_id != version.id for item in sources):
            raise BusinessValidationError("Every item must belong to the estimate version")
        next_line = max((item.line_number for item in version.items), default=0) + 1
        created: list[EstimateItem] = []
        for source in sources:
            copy = EstimateItem(
                estimate_version_id=version.id,
                line_number=next_line,
                afe_line_id=source.afe_line_id,
                catalog_item_id=source.catalog_item_id,
                cost_code_id=source.cost_code_id,
                vendor_id=source.vendor_id,
                rate_id=source.rate_id,
                quantity=source.quantity,
                unit_id=source.unit_id,
                notes=source.notes,
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
            next_line += 1
            self.session.add(copy)
            created.append(copy)
        self.session.commit()
        for item in created:
            self.session.refresh(item)
        return [self.read_item(item) for item in created]

    def upsert_assumption(self, version_id: UUID, payload: AssumptionUpsert) -> EstimateVersionRead:
        version = self._version(version_id)
        if payload.cost_category_id is not None:
            category = self.session.get(CostCategory, payload.cost_category_id)
            if category is None or not category.is_active:
                raise BusinessValidationError("cost_category_id must reference an active category")
        existing = next(
            (
                assumption
                for assumption in version.assumptions
                if assumption.cost_category_id == payload.cost_category_id
            ),
            None,
        )
        if existing is None:
            existing = EstimateAssumption(
                estimate_version_id=version.id,
                created_by=self.actor_id,
                updated_by=self.actor_id,
            )
            version.assumptions.append(existing)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        existing.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(version)
        return self.read_version(version)

    def duplicate_version(self, estimate_id: UUID, notes: str | None) -> EstimateVersionRead:
        estimate = self.session.get(CostEstimate, estimate_id)
        if estimate is None:
            raise NotFoundError("Estimate not found")
        source = max(estimate.versions, key=lambda value: value.version_number)
        next_number = source.version_number + 1
        version = EstimateVersion(
            estimate_id=estimate.id,
            version_number=next_number,
            status="pending_calculation",
            notes=notes,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        for item in source.items:
            version.items.append(
                EstimateItem(
                    line_number=item.line_number,
                    afe_line_id=item.afe_line_id,
                    catalog_item_id=item.catalog_item_id,
                    cost_code_id=item.cost_code_id,
                    vendor_id=item.vendor_id,
                    rate_id=item.rate_id,
                    quantity=item.quantity,
                    unit_id=item.unit_id,
                    notes=item.notes,
                    created_by=self.actor_id,
                    updated_by=self.actor_id,
                )
            )
        for assumption in source.assumptions:
            version.assumptions.append(
                EstimateAssumption(
                    cost_category_id=assumption.cost_category_id,
                    contingency_percent=assumption.contingency_percent,
                    escalation_percent=assumption.escalation_percent,
                    notes=assumption.notes,
                    created_by=self.actor_id,
                    updated_by=self.actor_id,
                )
            )
        estimate.versions.append(version)
        estimate.current_version_number = next_number
        estimate.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(version)
        return self.read_version(version)

    def resolve_default_rate(self, item_id: UUID) -> Never:
        """Business rule to be confirmed during Excel/business-rule discovery."""

        del item_id
        raise NotImplementedError(
            "Business rule to be confirmed during Excel/business-rule discovery."
        )

    def _validate_assignment(
        self, item: EstimateItem, vendor_id: UUID | None, rate_id: UUID | None
    ) -> None:
        if vendor_id is not None:
            vendor = self.session.get(Vendor, vendor_id)
            if vendor is None or not vendor.is_active:
                raise BusinessValidationError("vendor_id must reference an active vendor")
        if rate_id is not None:
            rate = self.session.get(Rate, rate_id)
            if rate is None or not rate.is_active:
                raise BusinessValidationError("rate_id must reference an active rate")
            if rate.item_id != item.catalog_item_id:
                raise BusinessValidationError(
                    "The selected rate belongs to a different catalogue item"
                )
            if vendor_id is not None and rate.vendor_id != vendor_id:
                raise BusinessValidationError("The selected rate belongs to a different vendor")

    def _version(self, version_id: UUID) -> EstimateVersion:
        version = self.session.get(EstimateVersion, version_id)
        if version is None:
            raise NotFoundError("Estimate version not found")
        return version

    def _item(self, item_id: UUID) -> EstimateItem:
        item = self.session.get(EstimateItem, item_id)
        if item is None:
            raise NotFoundError("Estimate item not found")
        return item

    @classmethod
    def read(cls, estimate: CostEstimate, include_versions: bool) -> EstimateRead:
        afe = estimate.afe
        return EstimateRead.model_validate(
            {
                "id": estimate.id,
                "afe_id": estimate.afe_id,
                "afe_code": afe.code,
                "well_id": afe.well_id,
                "well_code": afe.well.code,
                "project_code": afe.well.project.code,
                "code": estimate.code,
                "title": estimate.title,
                "currency_id": estimate.currency_id,
                "currency_code": estimate.currency.code,
                "current_version_number": estimate.current_version_number,
                "versions": [cls.read_version(version) for version in estimate.versions]
                if include_versions
                else [],
                "created_at": estimate.created_at,
                "created_by": estimate.created_by,
            }
        )

    @classmethod
    def read_version(cls, version: EstimateVersion) -> EstimateVersionRead:
        return EstimateVersionRead.model_validate(
            {
                "id": version.id,
                "estimate_id": version.estimate_id,
                "version_number": version.version_number,
                "status": version.status,
                "notes": version.notes,
                "base_total": version.base_total,
                "contingency_total": version.contingency_total,
                "escalation_total": version.escalation_total,
                "grand_total": version.grand_total,
                "items": [cls.read_item(item) for item in version.items],
                "assumptions": version.assumptions,
                "created_at": version.created_at,
                "created_by": version.created_by,
            }
        )

    @staticmethod
    def read_item(item: EstimateItem) -> EstimateItemRead:
        catalog_item = item.catalog_item
        cost_code = item.cost_code
        unit = item.unit
        rate = item.rate
        return EstimateItemRead.model_validate(
            {
                "id": item.id,
                "estimate_version_id": item.estimate_version_id,
                "line_number": item.line_number,
                "afe_line_id": item.afe_line_id,
                "catalog_item_id": item.catalog_item_id,
                "catalog_item_code": catalog_item.code if catalog_item else None,
                "catalog_item_name": catalog_item.name if catalog_item else None,
                "item_type": catalog_item.item_type if catalog_item else None,
                "cost_code_id": item.cost_code_id,
                "cost_code": cost_code.code if cost_code else None,
                "vendor_id": item.vendor_id,
                "vendor_code": item.vendor.code if item.vendor else None,
                "rate_id": item.rate_id,
                "rate_amount": rate.amount if rate else None,
                "rate_currency_code": rate.currency.code if rate else None,
                "quantity": item.quantity,
                "unit_id": item.unit_id,
                "unit_code": unit.code if unit else None,
                "notes": item.notes,
                "base_cost": item.base_cost,
                "contingency_cost": item.contingency_cost,
                "escalation_cost": item.escalation_cost,
                "total_cost": item.total_cost,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
        )
