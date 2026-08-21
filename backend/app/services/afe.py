"""Application workflows for project, well, and AFE preparation."""

from datetime import UTC, datetime
from math import ceil
from typing import Any, Never
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.domain.afe.rate_basis import (
    RateBasisError,
    default_rate_basis,
    requires_hole_section,
    resolve_planned_quantity,
    validate_rate_basis,
)
from app.models.afe import Afe, AfeLine, Project, Well
from app.models.master_data import CatalogItem, CostCode, HoleSection, Unit
from app.repositories.afe import (
    AfeLineRepository,
    AfeRepository,
    ProjectRepository,
    WellRepository,
)
from app.schemas.afe import (
    AfeCreate,
    AfeLineCreate,
    AfeLineRead,
    AfeLineUpdate,
    AfeRead,
    AfeUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    WellCreate,
    WellRead,
    WellUpdate,
)
from app.schemas.master_data import BulkRowError, BulkValidationResult, PageResponse


def _page(items: list[Any], page: int, page_size: int, total: int) -> PageResponse:
    return PageResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=ceil(total / page_size) if total else 0,
    )


class ProjectService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.repository = ProjectRepository(session)

    def list_page(
        self, page: int, page_size: int, search: str | None, is_active: bool | None
    ) -> PageResponse:
        records, total = self.repository.list(page, page_size, search, is_active)
        return _page(
            [ProjectRead.model_validate(record) for record in records], page, page_size, total
        )

    def get(self, project_id: UUID) -> ProjectRead:
        record = self.repository.get(project_id)
        if record is None:
            raise NotFoundError("Project not found")
        return ProjectRead.model_validate(record)

    def create(self, payload: ProjectCreate, commit: bool = True) -> ProjectRead:
        values = payload.model_dump()
        values.update(code=payload.code.strip().upper(), name=payload.name.strip())
        project = Project(
            **values,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(project)
        try:
            self.session.flush()
            if commit:
                self.session.commit()
                self.session.refresh(project)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("Project code already exists") from exc
        return ProjectRead.model_validate(project)

    def update(self, project_id: UUID, payload: ProjectUpdate, commit: bool = True) -> ProjectRead:
        project = self.repository.get(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        values = payload.model_dump(exclude_unset=True)
        if values.get("code"):
            values["code"] = str(values["code"]).strip().upper()
        if values.get("name"):
            values["name"] = str(values["name"]).strip()
        for field, value in values.items():
            setattr(project, field, value)
        project.updated_by = self.actor_id
        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(project)
        return ProjectRead.model_validate(project)

    def bulk_update(self, rows: list[tuple[UUID, ProjectUpdate]]) -> list[ProjectRead]:
        try:
            result = [self.update(item_id, payload, commit=False) for item_id, payload in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def deactivate(self, project_id: UUID) -> None:
        project = self.repository.get(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        project.is_active, project.updated_by = False, self.actor_id
        self.session.commit()

    def bulk_create(self, rows: list[ProjectCreate]) -> list[ProjectRead]:
        errors: list[BulkRowError] = []
        seen: set[str] = set()
        for index, row in enumerate(rows):
            code = row.code.strip().upper()
            if code in seen or self.repository.get_by_code(code):
                errors.append(
                    BulkRowError(
                        row_index=index,
                        column="code",
                        code="duplicate_code",
                        message="Project code is duplicated",
                    )
                )
            seen.add(code)
        if errors:
            raise BusinessValidationError(
                "Bulk project validation failed",
                BulkValidationResult(
                    valid=False,
                    total_rows=len(rows),
                    valid_rows=len(rows) - len({error.row_index for error in errors}),
                    errors=errors,
                ).model_dump(),
            )
        try:
            result = [self.create(row, commit=False) for row in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise


class WellService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.repository = WellRepository(session)

    def list_page(
        self,
        page: int,
        page_size: int,
        search: str | None,
        project_id: UUID | None,
        is_active: bool | None,
    ) -> PageResponse:
        records, total = self.repository.list(page, page_size, search, project_id, is_active)
        return _page([self._read(record) for record in records], page, page_size, total)

    def get(self, well_id: UUID) -> WellRead:
        well = self.repository.get(well_id)
        if well is None:
            raise NotFoundError("Well not found")
        return self._read(well)

    def create(self, payload: WellCreate, commit: bool = True) -> WellRead:
        project = self.session.get(Project, payload.project_id)
        if project is None or not project.is_active:
            raise BusinessValidationError("project_id must reference an active project")
        values = payload.model_dump()
        values.update(code=payload.code.strip().upper(), name=payload.name.strip())
        well = Well(**values, created_by=self.actor_id, updated_by=self.actor_id)
        self.session.add(well)
        try:
            self.session.flush()
            if commit:
                self.session.commit()
                self.session.refresh(well)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("Well code already exists within this project") from exc
        return self._read(well)

    def update(self, well_id: UUID, payload: WellUpdate, commit: bool = True) -> WellRead:
        well = self.repository.get(well_id)
        if well is None:
            raise NotFoundError("Well not found")
        values = payload.model_dump(exclude_unset=True)
        if "project_id" in values:
            project = self.session.get(Project, values["project_id"])
            if project is None or not project.is_active:
                raise BusinessValidationError("project_id must reference an active project")
        if values.get("code"):
            values["code"] = str(values["code"]).strip().upper()
        if values.get("name"):
            values["name"] = str(values["name"]).strip()
        for field, value in values.items():
            setattr(well, field, value)
        well.updated_by = self.actor_id
        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(well)
        return self._read(well)

    def bulk_update(self, rows: list[tuple[UUID, WellUpdate]]) -> list[WellRead]:
        try:
            result = [self.update(item_id, payload, commit=False) for item_id, payload in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def deactivate(self, well_id: UUID) -> None:
        well = self.repository.get(well_id)
        if well is None:
            raise NotFoundError("Well not found")
        well.is_active, well.updated_by = False, self.actor_id
        self.session.commit()

    def bulk_create(self, rows: list[WellCreate]) -> list[WellRead]:
        try:
            result = [self.create(row, commit=False) for row in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    @staticmethod
    def _read(well: Well) -> WellRead:
        return WellRead.model_validate(
            {
                **{
                    field: getattr(well, field)
                    for field in WellRead.model_fields
                    if field != "project_code"
                },
                "project_code": well.project.code,
            }
        )


class AfeService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.repository = AfeRepository(session)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        project_id: UUID | None,
        well_id: UUID | None,
        status: str | None,
        is_active: bool | None,
    ) -> PageResponse:
        if status not in {None, "draft", "submitted"}:
            raise BusinessValidationError("status must be draft or submitted")
        records, total = self.repository.list(
            page=page,
            page_size=page_size,
            search=search,
            project_id=project_id,
            well_id=well_id,
            status=status,
            is_active=is_active,
        )
        return _page(
            [self._read(record, include_items=False) for record in records], page, page_size, total
        )

    def get(self, afe_id: UUID) -> AfeRead:
        afe = self.repository.get(afe_id)
        if afe is None:
            raise NotFoundError("AFE not found")
        return self._read(afe, include_items=True)

    def create(self, payload: AfeCreate, commit: bool = True) -> AfeRead:
        well = self.session.get(Well, payload.well_id)
        if well is None or not well.is_active or not well.project.is_active:
            raise BusinessValidationError("well_id must reference an active well and project")
        values = payload.model_dump()
        values.update(code=payload.code.strip().upper(), title=payload.title.strip())
        afe = Afe(
            **values,
            status="draft",
            revision_number=1,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(afe)
        try:
            self.session.flush()
            if commit:
                self.session.commit()
                self.session.refresh(afe)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("AFE code/revision already exists for this well") from exc
        return self._read(afe, include_items=False)

    def update(self, afe_id: UUID, payload: AfeUpdate, commit: bool = True) -> AfeRead:
        afe = self._draft(afe_id)
        values = payload.model_dump(exclude_unset=True)
        if "well_id" in values:
            well = self.session.get(Well, values["well_id"])
            if well is None or not well.is_active:
                raise BusinessValidationError("well_id must reference an active well")
        if values.get("code"):
            values["code"] = str(values["code"]).strip().upper()
        if values.get("title"):
            values["title"] = str(values["title"]).strip()
        for field, value in values.items():
            setattr(afe, field, value)
        afe.updated_by = self.actor_id
        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(afe)
        return self._read(afe, include_items=True)

    def bulk_update(self, rows: list[tuple[UUID, AfeUpdate]]) -> list[AfeRead]:
        try:
            result = [self.update(item_id, payload, commit=False) for item_id, payload in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def submit(self, afe_id: UUID) -> AfeRead:
        afe = self._draft(afe_id)
        active_items = int(
            self.session.scalar(
                select(func.count())
                .select_from(AfeLine)
                .where(
                    AfeLine.afe_id == afe.id,
                    AfeLine.is_active.is_(True),
                )
            )
            or 0
        )
        if active_items == 0:
            raise BusinessValidationError("A afe needs at least one active item before submission")
        afe.status = "submitted"
        afe.submitted_at = datetime.now(UTC)
        afe.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(afe)
        self.session.expire(afe, ["items"])
        return self._read(afe, include_items=True)

    def deactivate(self, afe_id: UUID) -> None:
        afe = self._draft(afe_id)
        afe.is_active, afe.updated_by = False, self.actor_id
        self.session.commit()

    def bulk_create(self, rows: list[AfeCreate]) -> list[AfeRead]:
        try:
            result = [self.create(row, commit=False) for row in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def create_revision(self, afe_id: UUID) -> Never:
        """Business rule to be confirmed during Excel/business-rule discovery."""

        del afe_id
        raise NotImplementedError(
            "Business rule to be confirmed during Excel/business-rule discovery."
        )

    def _draft(self, afe_id: UUID) -> Afe:
        afe = self.repository.get(afe_id)
        if afe is None:
            raise NotFoundError("AFE not found")
        if afe.status != "draft":
            raise BusinessValidationError(
                "Submitted afes are read-only until revision rules are confirmed"
            )
        return afe

    @staticmethod
    def _read(afe: Afe, include_items: bool) -> AfeRead:
        items = [AfeLineService.read(item) for item in afe.items]
        return AfeRead.model_validate(
            {
                **{
                    field: getattr(afe, field)
                    for field in AfeRead.model_fields
                    if field
                    not in {"well_code", "project_id", "project_code", "item_count", "items"}
                },
                "well_code": afe.well.code,
                "project_id": afe.well.project_id,
                "project_code": afe.well.project.code,
                "item_count": len(items),
                "items": items if include_items else [],
            }
        )


class AfeLineService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.repository = AfeLineRepository(session)

    def list_items(self, afe_id: UUID) -> list[AfeLineRead]:
        self._afe(afe_id)
        return [self.read(item) for item in self.repository.list_for_afe(afe_id)]

    def create(self, afe_id: UUID, payload: AfeLineCreate, commit: bool = True) -> AfeLineRead:
        afe = self._afe(afe_id, must_be_draft=True)
        values = payload.model_dump()
        self._validate_references(values)
        self._apply_rate_basis(values)
        item = AfeLine(
            **values,
            afe_id=afe.id,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(item)
        try:
            self.session.flush()
            if commit:
                self.session.commit()
                self.session.refresh(item)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("AFE line number already exists") from exc
        return self.read(item)

    def update(self, item_id: UUID, payload: AfeLineUpdate, commit: bool = True) -> AfeLineRead:
        item = self.repository.get(item_id)
        if item is None:
            raise NotFoundError("AFE item not found")
        self._afe(item.afe_id, must_be_draft=True)
        values = payload.model_dump(exclude_unset=True)
        self._validate_references(values)
        # A quantity the app computed is not a planner's choice: leave it out so a
        # change to usage or planned days recomputes instead of reading as an override.
        was_computed = (
            item.computed_quantity is not None and item.quantity == item.computed_quantity
        )
        merged = {
            "catalog_item_id": item.catalog_item_id,
            "hole_section_id": item.hole_section_id,
            "rate_basis": item.rate_basis,
            "quantity": None if was_computed else item.quantity,
            "daily_consumption": item.daily_consumption,
            "planned_duration_days": item.planned_duration_days,
            "quantity_override_reason": item.quantity_override_reason,
            **values,
        }
        self._apply_rate_basis(merged)
        for field in (
            "rate_basis",
            "quantity",
            "computed_quantity",
            "quantity_override_reason",
        ):
            values[field] = merged[field]
        for field, value in values.items():
            setattr(item, field, value)
        if (
            item.planned_depth_from is not None
            and item.planned_depth_to is not None
            and item.planned_depth_to < item.planned_depth_from
        ):
            raise BusinessValidationError("planned_depth_to must be on or after planned_depth_from")
        if (item.planned_depth_from is not None or item.planned_depth_to is not None) and (
            item.depth_unit_id is None
        ):
            raise BusinessValidationError("A depth unit is required when planned depth is supplied")
        item.updated_by = self.actor_id
        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(item)
        return self.read(item)

    def deactivate(self, item_id: UUID) -> None:
        item = self.repository.get(item_id)
        if item is None:
            raise NotFoundError("AFE item not found")
        self._afe(item.afe_id, must_be_draft=True)
        item.is_active, item.updated_by = False, self.actor_id
        self.session.commit()

    def validate_bulk(self, afe_id: UUID, rows: list[AfeLineCreate]) -> BulkValidationResult:
        self._afe(afe_id, must_be_draft=True)
        errors: list[BulkRowError] = []
        seen: set[int] = set()
        for index, row in enumerate(rows):
            if row.line_number in seen:
                errors.append(
                    BulkRowError(
                        row_index=index,
                        column="line_number",
                        code="duplicate_line",
                        message="Line number is duplicated in the batch",
                    )
                )
            seen.add(row.line_number)
            values = row.model_dump()
            try:
                self._validate_references(values)
            except BusinessValidationError as exc:
                errors.append(
                    BulkRowError(row_index=index, code="invalid_reference", message=exc.message)
                )
                continue
            try:
                self._apply_rate_basis(values)
            except BusinessValidationError as exc:
                errors.append(
                    BulkRowError(
                        row_index=index,
                        column="rate_basis",
                        code="invalid_rate_basis",
                        message=exc.message,
                    )
                )
        invalid = {error.row_index for error in errors}
        return BulkValidationResult(
            valid=not errors,
            total_rows=len(rows),
            valid_rows=len(rows) - len(invalid),
            errors=errors,
        )

    def bulk_create(self, afe_id: UUID, rows: list[AfeLineCreate]) -> list[AfeLineRead]:
        validation = self.validate_bulk(afe_id, rows)
        if not validation.valid:
            raise BusinessValidationError("Bulk item validation failed", validation.model_dump())
        try:
            result = [self.create(afe_id, row, commit=False) for row in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def bulk_update(self, rows: list[tuple[UUID, AfeLineUpdate]]) -> list[AfeLineRead]:
        try:
            result = [self.update(item_id, payload, commit=False) for item_id, payload in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def _afe(self, afe_id: UUID, must_be_draft: bool = False) -> Afe:
        afe = self.session.get(Afe, afe_id)
        if afe is None or not afe.is_active:
            raise NotFoundError("AFE not found")
        if must_be_draft and afe.status != "draft":
            raise BusinessValidationError("Submitted afe items are read-only")
        return afe

    def _validate_references(self, values: dict[str, Any]) -> None:
        references = {
            "catalog_item_id": CatalogItem,
            "cost_code_id": CostCode,
            "unit_id": Unit,
            "depth_unit_id": Unit,
            "hole_section_id": HoleSection,
        }
        for field, model in references.items():
            value = values.get(field)
            if value is None:
                continue
            record = self.session.get(model, value)
            if record is None or not record.is_active:
                raise BusinessValidationError(f"{field} must reference an active record")

    def _apply_rate_basis(self, values: dict[str, Any]) -> None:
        """Settle the line's rate basis and the quantity that follows from it.

        The basis defaults to whatever the catalogue item is normally charged
        on and the planner may override it for this line. On a daily-consumption
        line the quantity is computed from consumption per day and planned days
        unless a reasoned override is supplied.
        """

        item = self.session.get(CatalogItem, values["catalog_item_id"])
        if item is None:
            raise BusinessValidationError("catalog_item_id must reference an active record")
        catalogue_basis = getattr(item, "rate_basis", None)
        try:
            basis = (
                validate_rate_basis(item.item_type, values["rate_basis"])
                if values.get("rate_basis")
                else default_rate_basis(item.item_type, catalogue_basis)
            )
            resolved = resolve_planned_quantity(
                rate_basis=basis,
                quantity=values.get("quantity"),
                daily_consumption=values.get("daily_consumption"),
                planned_duration_days=values.get("planned_duration_days"),
                override_reason=values.get("quantity_override_reason"),
            )
        except RateBasisError as exc:
            raise BusinessValidationError(str(exc)) from exc
        if requires_hole_section(basis) and values.get("hole_section_id") is None:
            raise BusinessValidationError(
                "hole_section_id is required when a line is charged per section"
            )

        values["rate_basis"] = basis
        values["quantity"] = resolved.quantity
        values["computed_quantity"] = resolved.computed_quantity
        if not resolved.is_overridden:
            values["quantity_override_reason"] = None

    @staticmethod
    def read(item: AfeLine) -> AfeLineRead:
        return AfeLineRead.model_validate(
            {
                **{
                    field: getattr(item, field)
                    for field in AfeLineRead.model_fields
                    if field
                    not in {
                        "catalog_item_code",
                        "catalog_item_name",
                        "item_type",
                        "cost_code",
                        "unit_code",
                        "depth_unit_code",
                        "hole_section_code",
                        "hole_section_name",
                        "quantity_source",
                    }
                },
                "catalog_item_code": item.catalog_item.code,
                "catalog_item_name": item.catalog_item.name,
                "item_type": item.catalog_item.item_type,
                "cost_code": item.cost_code.code,
                "unit_code": item.unit.code,
                "depth_unit_code": item.depth_unit.code if item.depth_unit else None,
                "hole_section_code": item.hole_section.code if item.hole_section else None,
                "hole_section_name": item.hole_section.name if item.hole_section else None,
                "quantity_source": AfeLineService._quantity_source(item),
            }
        )

    @staticmethod
    def _quantity_source(item: AfeLine) -> str:
        if item.computed_quantity is None:
            return "entered"
        return "overridden" if item.quantity != item.computed_quantity else "computed"
