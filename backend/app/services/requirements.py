"""Application workflows for project, well, and requirement intake."""

from datetime import UTC, datetime
from math import ceil
from typing import Any, Never
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, ConflictError, NotFoundError
from app.models.master_data import CatalogItem, CostCode, Unit
from app.models.requirements import Project, RequirementItem, Well, WellRequirement
from app.repositories.requirements import (
    ProjectRepository,
    RequirementItemRepository,
    RequirementRepository,
    WellRepository,
)
from app.schemas.master_data import BulkRowError, BulkValidationResult, PageResponse
from app.schemas.requirements import (
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    RequirementCreate,
    RequirementItemCreate,
    RequirementItemRead,
    RequirementItemUpdate,
    RequirementRead,
    RequirementUpdate,
    WellCreate,
    WellRead,
    WellUpdate,
)


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


class RequirementService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.repository = RequirementRepository(session)

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

    def get(self, requirement_id: UUID) -> RequirementRead:
        requirement = self.repository.get(requirement_id)
        if requirement is None:
            raise NotFoundError("Requirement not found")
        return self._read(requirement, include_items=True)

    def create(self, payload: RequirementCreate, commit: bool = True) -> RequirementRead:
        well = self.session.get(Well, payload.well_id)
        if well is None or not well.is_active or not well.project.is_active:
            raise BusinessValidationError("well_id must reference an active well and project")
        values = payload.model_dump()
        values.update(code=payload.code.strip().upper(), title=payload.title.strip())
        requirement = WellRequirement(
            **values,
            status="draft",
            revision_number=1,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(requirement)
        try:
            self.session.flush()
            if commit:
                self.session.commit()
                self.session.refresh(requirement)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("Requirement code/revision already exists for this well") from exc
        return self._read(requirement, include_items=False)

    def update(
        self, requirement_id: UUID, payload: RequirementUpdate, commit: bool = True
    ) -> RequirementRead:
        requirement = self._draft(requirement_id)
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
            setattr(requirement, field, value)
        requirement.updated_by = self.actor_id
        self.session.flush()
        if commit:
            self.session.commit()
            self.session.refresh(requirement)
        return self._read(requirement, include_items=True)

    def bulk_update(self, rows: list[tuple[UUID, RequirementUpdate]]) -> list[RequirementRead]:
        try:
            result = [self.update(item_id, payload, commit=False) for item_id, payload in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def submit(self, requirement_id: UUID) -> RequirementRead:
        requirement = self._draft(requirement_id)
        active_items = int(
            self.session.scalar(
                select(func.count())
                .select_from(RequirementItem)
                .where(
                    RequirementItem.requirement_id == requirement.id,
                    RequirementItem.is_active.is_(True),
                )
            )
            or 0
        )
        if active_items == 0:
            raise BusinessValidationError(
                "A requirement needs at least one active item before submission"
            )
        requirement.status = "submitted"
        requirement.submitted_at = datetime.now(UTC)
        requirement.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(requirement)
        self.session.expire(requirement, ["items"])
        return self._read(requirement, include_items=True)

    def deactivate(self, requirement_id: UUID) -> None:
        requirement = self._draft(requirement_id)
        requirement.is_active, requirement.updated_by = False, self.actor_id
        self.session.commit()

    def bulk_create(self, rows: list[RequirementCreate]) -> list[RequirementRead]:
        try:
            result = [self.create(row, commit=False) for row in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def create_revision(self, requirement_id: UUID) -> Never:
        """Business rule to be confirmed during Excel/business-rule discovery."""

        del requirement_id
        raise NotImplementedError(
            "Business rule to be confirmed during Excel/business-rule discovery."
        )

    def _draft(self, requirement_id: UUID) -> WellRequirement:
        requirement = self.repository.get(requirement_id)
        if requirement is None:
            raise NotFoundError("Requirement not found")
        if requirement.status != "draft":
            raise BusinessValidationError(
                "Submitted requirements are read-only until revision rules are confirmed"
            )
        return requirement

    @staticmethod
    def _read(requirement: WellRequirement, include_items: bool) -> RequirementRead:
        items = [RequirementItemService.read(item) for item in requirement.items]
        return RequirementRead.model_validate(
            {
                **{
                    field: getattr(requirement, field)
                    for field in RequirementRead.model_fields
                    if field
                    not in {"well_code", "project_id", "project_code", "item_count", "items"}
                },
                "well_code": requirement.well.code,
                "project_id": requirement.well.project_id,
                "project_code": requirement.well.project.code,
                "item_count": len(items),
                "items": items if include_items else [],
            }
        )


class RequirementItemService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.repository = RequirementItemRepository(session)

    def list_items(self, requirement_id: UUID) -> list[RequirementItemRead]:
        self._requirement(requirement_id)
        return [self.read(item) for item in self.repository.list_for_requirement(requirement_id)]

    def create(
        self, requirement_id: UUID, payload: RequirementItemCreate, commit: bool = True
    ) -> RequirementItemRead:
        requirement = self._requirement(requirement_id, must_be_draft=True)
        self._validate_references(payload.model_dump())
        item = RequirementItem(
            **payload.model_dump(),
            requirement_id=requirement.id,
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
            raise ConflictError("Requirement line number already exists") from exc
        return self.read(item)

    def update(
        self, item_id: UUID, payload: RequirementItemUpdate, commit: bool = True
    ) -> RequirementItemRead:
        item = self.repository.get(item_id)
        if item is None:
            raise NotFoundError("Requirement item not found")
        self._requirement(item.requirement_id, must_be_draft=True)
        values = payload.model_dump(exclude_unset=True)
        self._validate_references(values)
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
            raise NotFoundError("Requirement item not found")
        self._requirement(item.requirement_id, must_be_draft=True)
        item.is_active, item.updated_by = False, self.actor_id
        self.session.commit()

    def validate_bulk(
        self, requirement_id: UUID, rows: list[RequirementItemCreate]
    ) -> BulkValidationResult:
        self._requirement(requirement_id, must_be_draft=True)
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
            try:
                self._validate_references(row.model_dump())
            except BusinessValidationError as exc:
                errors.append(
                    BulkRowError(
                        row_index=index,
                        code="invalid_reference",
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

    def bulk_create(
        self, requirement_id: UUID, rows: list[RequirementItemCreate]
    ) -> list[RequirementItemRead]:
        validation = self.validate_bulk(requirement_id, rows)
        if not validation.valid:
            raise BusinessValidationError("Bulk item validation failed", validation.model_dump())
        try:
            result = [self.create(requirement_id, row, commit=False) for row in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def bulk_update(
        self, rows: list[tuple[UUID, RequirementItemUpdate]]
    ) -> list[RequirementItemRead]:
        try:
            result = [self.update(item_id, payload, commit=False) for item_id, payload in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def _requirement(self, requirement_id: UUID, must_be_draft: bool = False) -> WellRequirement:
        requirement = self.session.get(WellRequirement, requirement_id)
        if requirement is None or not requirement.is_active:
            raise NotFoundError("Requirement not found")
        if must_be_draft and requirement.status != "draft":
            raise BusinessValidationError("Submitted requirement items are read-only")
        return requirement

    def _validate_references(self, values: dict[str, Any]) -> None:
        references = {
            "catalog_item_id": CatalogItem,
            "cost_code_id": CostCode,
            "unit_id": Unit,
            "depth_unit_id": Unit,
        }
        for field, model in references.items():
            value = values.get(field)
            if value is None:
                continue
            record = self.session.get(model, value)
            if record is None or not record.is_active:
                raise BusinessValidationError(f"{field} must reference an active record")

    @staticmethod
    def read(item: RequirementItem) -> RequirementItemRead:
        return RequirementItemRead.model_validate(
            {
                **{
                    field: getattr(item, field)
                    for field in RequirementItemRead.model_fields
                    if field
                    not in {
                        "catalog_item_code",
                        "catalog_item_name",
                        "item_type",
                        "cost_code",
                        "unit_code",
                        "depth_unit_code",
                    }
                },
                "catalog_item_code": item.catalog_item.code,
                "catalog_item_name": item.catalog_item.name,
                "item_type": item.catalog_item.item_type,
                "cost_code": item.cost_code.code,
                "unit_code": item.unit.code,
                "depth_unit_code": item.depth_unit.code if item.depth_unit else None,
            }
        )
