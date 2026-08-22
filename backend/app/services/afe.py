"""Application workflows for project, well, AFE preparation, and sections/phases."""

from datetime import UTC, datetime
from decimal import Decimal
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
from app.models.afe import (
    Afe,
    AfeAuditLog,
    AfeLine,
    AfeSection,
    DrillingPhase,
    Project,
    Well,
)
from app.models.master_data import CatalogItem, CostCode, HoleSection, Unit
from app.repositories.afe import (
    AfeLineRepository,
    AfeRepository,
    ProjectRepository,
    WellRepository,
)
from app.schemas.afe import (
    AfeAuditLogRead,
    AfeCreate,
    AfeLineCreate,
    AfeLineRead,
    AfeLineUpdate,
    AfeRead,
    AfeSectionRead,
    AfeUpdate,
    DrillingPhaseCreate,
    DrillingPhaseRead,
    DrillingPhaseUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    WellCreate,
    WellRead,
    WellUpdate,
)
from app.schemas.master_data import BulkRowError, BulkValidationResult, PageResponse
from app.services.audit import log_entity_action


def _page(items: list[Any], page: int, page_size: int, total: int) -> PageResponse:
    return PageResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=ceil(total / page_size) if total else 0,
    )


def _audit(session: Session, actor_id: UUID, action: str, entity_type: str, entity_id: UUID | None, entity_code: str | None = None, details: Any | None = None) -> None:
    """Single audited-procedure hook shared by every entity action below."""

    log_entity_action(
        session,
        actor_id,
        action,
        entity_type,
        entity_id=entity_id,
        entity_code=entity_code,
        details=details,
    )


DEFAULT_DRILLING_PHASES = [
    {"code": "DRILL", "name": "Drilling", "description": "Hole drilling operations", "sequence": 1},
    {"code": "LOG", "name": "Logging", "description": "Wireline and formation evaluation logging", "sequence": 2},
    {"code": "CAS_CEM", "name": "Casing & Cementing", "description": "Running casing and primary cementing", "sequence": 3},
    {"code": "COMP", "name": "Completion", "description": "Lower and upper completion operations", "sequence": 4},
    {"code": "TEST", "name": "Well Testing", "description": "Flow testing and well cleanup", "sequence": 5},
    {"code": "MOB", "name": "Mobilisation & Rig Move", "description": "Rig move, positioning, and rig up", "sequence": 6},
    {"code": "ABAN", "name": "Plug & Abandonment", "description": "Well plugging and decommissioning", "sequence": 7},
]


class DrillingPhaseService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id

    def list_all(self) -> list[DrillingPhaseRead]:
        phases = self.session.scalars(
            select(DrillingPhase)
            .where(DrillingPhase.is_active.is_(True))
            .order_by(DrillingPhase.sequence, DrillingPhase.name)
        ).all()
        if not phases:
            for item in DEFAULT_DRILLING_PHASES:
                phase = DrillingPhase(
                    code=item["code"],
                    name=item["name"],
                    description=item["description"],
                    sequence=item["sequence"],
                    is_active=True,
                    created_by=self.actor_id,
                    updated_by=self.actor_id,
                )
                self.session.add(phase)
            self.session.commit()
            phases = self.session.scalars(
                select(DrillingPhase)
                .where(DrillingPhase.is_active.is_(True))
                .order_by(DrillingPhase.sequence, DrillingPhase.name)
            ).all()
        return [DrillingPhaseRead.model_validate(p) for p in phases]

    def create(self, payload: DrillingPhaseCreate) -> DrillingPhaseRead:
        code = payload.code.strip().upper()
        existing = self.session.scalar(select(DrillingPhase).where(DrillingPhase.code == code))
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.name = payload.name.strip()
                existing.description = payload.description
                existing.sequence = payload.sequence
                existing.updated_by = self.actor_id
                self.session.commit()
                _audit(self.session, self.actor_id, "update", "drilling_phase", existing.id, existing.code, {"action": "reactivated"})
                self.session.commit()
                return DrillingPhaseRead.model_validate(existing)
            raise ConflictError(f"Drilling phase '{code}' already exists")
        phase = DrillingPhase(
            code=code,
            name=payload.name.strip(),
            description=payload.description,
            sequence=payload.sequence,
            is_active=payload.is_active,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(phase)
        self.session.commit()
        self.session.refresh(phase)
        _audit(self.session, self.actor_id, "create", "drilling_phase", phase.id, phase.code, payload.model_dump())
        self.session.commit()
        return DrillingPhaseRead.model_validate(phase)

    def update(self, phase_id: UUID, payload: DrillingPhaseUpdate) -> DrillingPhaseRead:
        phase = self.session.get(DrillingPhase, phase_id)
        if not phase or not phase.is_active:
            raise NotFoundError("Drilling phase not found")
        values = payload.model_dump(exclude_unset=True)
        if values.get("code"):
            values["code"] = str(values["code"]).strip().upper()
        if values.get("name"):
            values["name"] = str(values["name"]).strip()
        for k, v in values.items():
            setattr(phase, k, v)
        phase.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(phase)
        _audit(self.session, self.actor_id, "update", "drilling_phase", phase.id, phase.code, values)
        self.session.commit()
        return DrillingPhaseRead.model_validate(phase)

    def delete(self, phase_id: UUID) -> None:
        phase = self.session.get(DrillingPhase, phase_id)
        if not phase:
            raise NotFoundError("Drilling phase not found")
        phase.is_active = False
        phase.updated_by = self.actor_id
        self.session.flush()
        _audit(self.session, self.actor_id, "soft_delete", "drilling_phase", phase.id, phase.code, None)
        self.session.commit()

    def recover(self, phase_id: UUID) -> DrillingPhaseRead:
        phase = self.session.get(DrillingPhase, phase_id)
        if not phase:
            raise NotFoundError("Drilling phase not found")
        if phase.is_active:
            raise BusinessValidationError("Drilling phase is not deleted and cannot be recovered")
        existing = self.session.scalar(
            select(DrillingPhase).where(
                DrillingPhase.code == phase.code,
                DrillingPhase.is_active.is_(True),
                DrillingPhase.id != phase.id,
            )
        )
        if existing:
            raise ConflictError(
                f"Cannot recover: an active drilling phase with code '{phase.code}' already exists"
            )
        phase.is_active = True
        phase.updated_by = self.actor_id
        self.session.commit()
        self.session.refresh(phase)
        _audit(self.session, self.actor_id, "recover", "drilling_phase", phase.id, phase.code, None)
        self.session.commit()
        return DrillingPhaseRead.model_validate(phase)


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
            _audit(self.session, self.actor_id, "create", "project", project.id, project.code, values)
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
        _audit(self.session, self.actor_id, "update", "project", project.id, project.code, values)
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
        self.session.flush()
        _audit(self.session, self.actor_id, "soft_delete", "project", project.id, project.code, None)
        self.session.commit()

    def recover(self, project_id: UUID) -> ProjectRead:
        """Restore a soft-deleted project back to active use."""
        project = self.repository.get(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        if project.is_active:
            raise BusinessValidationError("Project is not deleted and cannot be recovered")
        existing = self.session.scalar(
            select(Project).where(
                Project.code == project.code,
                Project.is_active.is_(True),
                Project.id != project.id,
            )
        )
        if existing:
            raise ConflictError(
                f"Cannot recover: an active project with code '{project.code}' already exists"
            )
        project.is_active, project.updated_by = True, self.actor_id
        self.session.flush()
        _audit(self.session, self.actor_id, "recover", "project", project.id, project.code, None)
        self.session.commit()
        self.session.refresh(project)
        return ProjectRead.model_validate(project)

    def hard_delete(self, project_id: UUID) -> None:
        """Permanently delete a soft-deleted project.

        Refuses with a clear conflict message while the project still owns wells,
        because wells reference projects with an ON DELETE RESTRICT constraint.
        """

        project = self.repository.get(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        if project.is_active:
            raise BusinessValidationError(
                "Project must be deleted (deactivated) before permanent deletion"
            )
        well_count = int(
            self.session.scalar(
                select(func.count()).select_from(Well).where(Well.project_id == project.id)
            )
            or 0
        )
        if well_count:
            raise ConflictError(
                f"Project '{project.code}' still has {well_count} well(s). "
                "Delete its wells first before permanently deleting the project."
            )
        code = project.code
        try:
            self.session.delete(project)
            self.session.flush()
            _audit(self.session, self.actor_id, "hard_delete", "project", project_id, code, None)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                "This project is referenced by other records and cannot be permanently "
                "deleted. Delete the referencing records first."
            ) from exc

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
            _audit(self.session, self.actor_id, "create", "well", well.id, well.code, values)
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
        _audit(self.session, self.actor_id, "update", "well", well.id, well.code, values)
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
        self.session.flush()
        _audit(self.session, self.actor_id, "soft_delete", "well", well.id, well.code, None)
        self.session.commit()

    def recover(self, well_id: UUID) -> WellRead:
        """Restore a soft-deleted well back to active use."""
        well = self.repository.get(well_id)
        if well is None:
            raise NotFoundError("Well not found")
        if well.is_active:
            raise BusinessValidationError("Well is not deleted and cannot be recovered")
        project = self.session.get(Project, well.project_id)
        if project is None or not project.is_active:
            raise BusinessValidationError(
                "The project this well belongs to is deleted. Recover the project first."
            )
        existing = self.session.scalar(
            select(Well).where(
                Well.project_id == well.project_id,
                Well.code == well.code,
                Well.is_active.is_(True),
                Well.id != well.id,
            )
        )
        if existing:
            raise ConflictError(
                f"Cannot recover: an active well with code '{well.code}' already exists "
                "in this project"
            )
        well.is_active, well.updated_by = True, self.actor_id
        self.session.flush()
        _audit(self.session, self.actor_id, "recover", "well", well.id, well.code, None)
        self.session.commit()
        self.session.refresh(well)
        return self._read(well)

    def hard_delete(self, well_id: UUID) -> None:
        """Permanently delete a soft-deleted well.

        Refuses with a clear conflict message while AFEs still reference the well,
        because AFEs reference wells with an ON DELETE RESTRICT constraint. Well
        rates, unplanned items, and daily cost entries are removed with the well
        by the database's cascade rules.
        """

        well = self.repository.get(well_id)
        if well is None:
            raise NotFoundError("Well not found")
        if well.is_active:
            raise BusinessValidationError(
                "Well must be deleted (deactivated) before permanent deletion"
            )
        afe_count = int(
            self.session.scalar(
                select(func.count()).select_from(Afe).where(Afe.well_id == well.id)
            )
            or 0
        )
        if afe_count:
            raise ConflictError(
                f"Well '{well.code}' still has {afe_count} AFE(s) (active or deleted). "
                "Delete the AFEs permanently first, then delete the well."
            )
        code = well.code
        try:
            self.session.delete(well)
            self.session.flush()
            _audit(self.session, self.actor_id, "hard_delete", "well", well_id, code, None)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                "This well is referenced by other records and cannot be permanently "
                "deleted. Delete the referencing records first."
            ) from exc

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
                "project_code": well.project.code if well.project else None,
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

    def get_any(self, afe_id: UUID) -> Afe:
        """Get AFE regardless of is_active (for deleted view)."""
        afe = self.repository.get(afe_id)
        if afe is None:
            raise NotFoundError("AFE not found")
        return afe

    def create(self, payload: AfeCreate, commit: bool = True) -> AfeRead:
        well = self.session.get(Well, payload.well_id)
        if well is None or not well.is_active or not well.project.is_active:
            raise BusinessValidationError("well_id must reference an active well and project")
        values = payload.model_dump(exclude={"sections"})
        values.update(code=payload.code.strip().upper(), title=payload.title.strip())

        sections_input = payload.sections
        if sections_input:
            if not values.get("total_planned_days") or values["total_planned_days"] == Decimal("0"):
                values["total_planned_days"] = sum((s.planned_days for s in sections_input), Decimal("0"))
            if not values.get("total_planned_depth") or values["total_planned_depth"] == Decimal("0"):
                values["total_planned_depth"] = max(
                    (s.planned_depth_to for s in sections_input if s.planned_depth_to is not None),
                    default=Decimal("0"),
                )

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
            if sections_input:
                for idx, sec_input in enumerate(sections_input):
                    sec = AfeSection(
                        afe_id=afe.id,
                        sequence=sec_input.sequence or (idx + 1),
                        hole_section_id=sec_input.hole_section_id,
                        phase=sec_input.phase,
                        planned_days=sec_input.planned_days,
                        planned_depth_from=sec_input.planned_depth_from,
                        planned_depth_to=sec_input.planned_depth_to,
                        depth_unit_id=sec_input.depth_unit_id or afe.depth_unit_id,
                        notes=sec_input.notes,
                        is_active=sec_input.is_active,
                        created_by=self.actor_id,
                        updated_by=self.actor_id,
                    )
                    self.session.add(sec)
                self.session.flush()

            audit_entry = AfeAuditLog(
                afe_id=afe.id,
                action="created",
                previous_status=None,
                new_status="draft",
                remarks="AFE created",
                actor_id=self.actor_id,
            )
            self.session.add(audit_entry)
            self.session.flush()
            _audit(self.session, self.actor_id, "create", "afe", afe.id, afe.code, {"well_id": str(afe.well_id), "title": afe.title})

            if commit:
                self.session.commit()
                self.session.refresh(afe)
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError("AFE code/revision already exists for this well") from exc
        return self._read(afe, include_items=False)

    def update(self, afe_id: UUID, payload: AfeUpdate, commit: bool = True) -> AfeRead:
        afe = self._draft(afe_id)
        values = payload.model_dump(exclude_unset=True, exclude={"sections"})
        if values.get("well_id"):
            well = self.session.get(Well, values["well_id"])
            if well is None or not well.is_active:
                raise BusinessValidationError("well_id must reference an active well")
        if values.get("code"):
            values["code"] = str(values["code"]).strip().upper()
        if values.get("title"):
            values["title"] = str(values["title"]).strip()

        sections_input = payload.sections
        if sections_input is not None:
            # Replace existing sections
            for old_sec in list(afe.sections):
                self.session.delete(old_sec)
            self.session.flush()
            for idx, sec_input in enumerate(sections_input):
                sec = AfeSection(
                    afe_id=afe.id,
                    sequence=sec_input.sequence or (idx + 1),
                    hole_section_id=sec_input.hole_section_id,
                    phase=sec_input.phase,
                    planned_days=sec_input.planned_days,
                    planned_depth_from=sec_input.planned_depth_from,
                    planned_depth_to=sec_input.planned_depth_to,
                    depth_unit_id=sec_input.depth_unit_id or values.get("depth_unit_id", afe.depth_unit_id),
                    notes=sec_input.notes,
                    is_active=sec_input.is_active,
                    created_by=self.actor_id,
                    updated_by=self.actor_id,
                )
                self.session.add(sec)
            if "total_planned_days" not in values or values["total_planned_days"] is None:
                values["total_planned_days"] = sum((s.planned_days for s in sections_input), Decimal("0"))
            if "total_planned_depth" not in values or values["total_planned_depth"] is None:
                values["total_planned_depth"] = max(
                    (s.planned_depth_to for s in sections_input if s.planned_depth_to is not None),
                    default=Decimal("0"),
                )

        for field, value in values.items():
            setattr(afe, field, value)
        afe.updated_by = self.actor_id
        self.session.flush()
        _audit(self.session, self.actor_id, "update", "afe", afe.id, afe.code, values)
        if commit:
            self.session.commit()
            self.session.refresh(afe)
        return self._read(afe, include_items=True)

    def reopen(self, afe_id: UUID, remarks: str) -> AfeRead:
        """Reopen a submitted AFE for editing with an audited reason."""
        if not remarks or not remarks.strip():
            raise BusinessValidationError("Remarks are mandatory when reopening a submitted AFE")
        afe = self.repository.get(afe_id)
        if afe is None or not afe.is_active:
            raise NotFoundError("AFE not found")
        if afe.status != "submitted":
            raise BusinessValidationError("Only submitted AFEs can be reopened for editing")

        previous_status = afe.status
        afe.status = "draft"
        afe.reopen_remarks = remarks.strip()
        afe.reopened_at = datetime.now(UTC)
        afe.reopened_by = self.actor_id
        afe.updated_by = self.actor_id

        audit_entry = AfeAuditLog(
            afe_id=afe.id,
            action="reopened",
            previous_status=previous_status,
            new_status="draft",
            remarks=remarks.strip(),
            actor_id=self.actor_id,
        )
        self.session.add(audit_entry)
        self.session.flush()
        _audit(self.session, self.actor_id, "reopen", "afe", afe.id, afe.code, {"remarks": remarks.strip()})
        self.session.commit()
        self.session.refresh(afe)
        self.session.expire(afe, ["items", "sections", "audit_logs"])
        return self._read(afe, include_items=True)

    def bulk_update(self, rows: list[tuple[UUID, AfeUpdate]]) -> list[AfeRead]:
        try:
            result = [self.update(item_id, payload, commit=False) for item_id, payload in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def submit(self, afe_id: UUID, remarks: str | None = None) -> AfeRead:
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
            raise BusinessValidationError("An AFE needs at least one active item before submission")

        previous_status = afe.status
        afe.status = "submitted"
        afe.submitted_at = datetime.now(UTC)
        afe.updated_by = self.actor_id

        action_name = "resubmitted" if afe.reopened_at else "submitted"
        audit_entry = AfeAuditLog(
            afe_id=afe.id,
            action=action_name,
            previous_status=previous_status,
            new_status="submitted",
            remarks=remarks.strip() if remarks else ("Resubmitted after edits" if afe.reopened_at else "Initial submission"),
            actor_id=self.actor_id,
        )
        self.session.add(audit_entry)
        self.session.flush()
        _audit(self.session, self.actor_id, action_name, "afe", afe.id, afe.code, None)

        self.session.commit()
        self.session.refresh(afe)
        self.session.expire(afe, ["items", "sections", "audit_logs"])
        return self._read(afe, include_items=True)

    def deactivate(self, afe_id: UUID) -> None:
        """Soft-delete an AFE (draft or submitted) — moves to deleted AFEs."""
        afe = self.repository.get(afe_id)
        if afe is None:
            raise NotFoundError("AFE not found")
        if not afe.is_active:
            raise BusinessValidationError("AFE is already deleted")
        # Soft delete regardless of status (draft or submitted)
        afe.is_active = False
        afe.deleted_at = datetime.now(UTC)
        afe.deleted_by = self.actor_id
        afe.updated_by = self.actor_id

        audit_entry = AfeAuditLog(
            afe_id=afe.id,
            action="soft_deleted",
            previous_status=afe.status,
            new_status=afe.status,
            remarks=f"AFE soft-deleted (status was {afe.status})",
            actor_id=self.actor_id,
        )
        self.session.add(audit_entry)
        self.session.flush()
        _audit(self.session, self.actor_id, "soft_delete", "afe", afe.id, afe.code, {"previous_status": afe.status})
        self.session.commit()

    def recover(self, afe_id: UUID) -> AfeRead:
        """Recover a soft-deleted AFE. Fails if another active AFE exists."""
        afe = self.repository.get(afe_id)
        if afe is None:
            raise NotFoundError("AFE not found")
        if afe.is_active:
            raise BusinessValidationError("AFE is not deleted and cannot be recovered")

        # Business rule: if any active AFE exists, recover should not work
        active_count = self.session.scalar(select(func.count()).select_from(Afe).where(Afe.is_active.is_(True))) or 0
        if active_count > 0:
            raise BusinessValidationError("Cannot recover: another active AFE already exists at the AFE page. Delete the existing AFE before recovery.")

        # Also check duplicate code/well/revision conflict
        conflict = self.session.scalar(
            select(Afe).where(
                Afe.is_active.is_(True),
                Afe.well_id == afe.well_id,
                Afe.code == afe.code,
                Afe.revision_number == afe.revision_number,
                Afe.id != afe.id,
            )
        )
        if conflict:
            raise ConflictError(f"Cannot recover: an active AFE with code '{afe.code}' already exists for this well")

        afe.is_active = True
        afe.deleted_at = None
        afe.deleted_by = None
        afe.updated_by = self.actor_id

        audit_entry = AfeAuditLog(
            afe_id=afe.id,
            action="recovered",
            previous_status=afe.status,
            new_status=afe.status,
            remarks="AFE recovered from deleted",
            actor_id=self.actor_id,
        )
        self.session.add(audit_entry)
        self.session.flush()
        _audit(self.session, self.actor_id, "recover", "afe", afe.id, afe.code, None)
        self.session.commit()
        self.session.refresh(afe)
        self.session.expire(afe, ["items", "sections", "audit_logs"])
        return self._read(afe, include_items=True)

    def hard_delete(self, afe_id: UUID) -> None:
        """Permanently delete a soft-deleted AFE.

        The AFE's own sections, lines, and audit trail are removed with it. A
        clear conflict is raised when other records (cost estimates built in the
        Cost Builder) still reference the AFE, instead of an unhandled database
        error.
        """

        afe = self.repository.get(afe_id)
        if afe is None:
            raise NotFoundError("AFE not found")
        if afe.is_active:
            raise BusinessValidationError("AFE must be soft-deleted before permanent deletion. Soft-delete it first.")
        from app.models.estimates import CostEstimate

        estimate_count = int(
            self.session.scalar(
                select(func.count()).select_from(CostEstimate).where(CostEstimate.afe_id == afe.id)
            )
            or 0
        )
        if estimate_count:
            raise ConflictError(
                f"AFE '{afe.code}' still has {estimate_count} cost estimate(s) built from it "
                "in the Cost Builder. Delete those estimates first (Cost Builder → Delete → "
                "Delete forever), then permanently delete the AFE."
            )
        # Keep code for audit before deletion
        code = afe.code
        try:
            self.session.delete(afe)
            self.session.flush()
            _audit(self.session, self.actor_id, "hard_delete", "afe", afe_id, code, None)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ConflictError(
                "This AFE is referenced by other records and cannot be permanently deleted. "
                "Delete the referencing records first."
            ) from exc

    def bulk_create(self, rows: list[AfeCreate]) -> list[AfeRead]:
        try:
            result = [self.create(row, commit=False) for row in rows]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def create_revision(self, afe_id: UUID) -> Never:
        del afe_id
        raise NotImplementedError(
            "Business rule to be confirmed during Excel/business-rule discovery."
        )

    def _draft(self, afe_id: UUID) -> Afe:
        afe = self.repository.get(afe_id)
        if afe is None or not afe.is_active:
            raise NotFoundError("AFE not found")
        if afe.status != "draft":
            raise BusinessValidationError(
                "Submitted AFEs are read-only. Use 'Reopen AFE' with remarks to make changes."
            )
        return afe

    @staticmethod
    def _read(afe: Afe, include_items: bool) -> AfeRead:
        active_items = [item for item in (afe.items or []) if item.is_active]
        items = [AfeLineService.read(item) for item in active_items] if include_items else []
        sections = [
            AfeSectionRead(
                id=s.id,
                afe_id=s.afe_id,
                sequence=s.sequence,
                hole_section_id=s.hole_section_id,
                hole_section_code=s.hole_section.code if s.hole_section else None,
                hole_section_name=s.hole_section.name if s.hole_section else None,
                phase=s.phase,
                planned_days=s.planned_days,
                planned_depth_from=s.planned_depth_from,
                planned_depth_to=s.planned_depth_to,
                depth_unit_id=s.depth_unit_id,
                depth_unit_code=s.depth_unit.code if s.depth_unit else None,
                notes=s.notes,
                is_active=s.is_active,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in (afe.sections or [])
            if s.is_active
        ]
        sorted_logs = sorted(
            afe.audit_logs or [],
            key=lambda a: (a.created_at, str(a.id)),
            reverse=True,
        )
        audit_logs = [
            AfeAuditLogRead(
                id=a.id,
                afe_id=a.afe_id,
                action=a.action,
                previous_status=a.previous_status,
                new_status=a.new_status,
                remarks=a.remarks,
                actor_id=a.actor_id,
                created_at=a.created_at,
            )
            for a in sorted_logs
        ]
        return AfeRead.model_validate(
            {
                **{
                    field: getattr(afe, field)
                    for field in AfeRead.model_fields
                    if field
                    not in {
                        "well_code",
                        "project_id",
                        "project_code",
                        "item_count",
                        "items",
                        "sections",
                        "audit_logs",
                        "depth_unit_code",
                    }
                },
                "well_code": afe.well.code if afe.well else None,
                "project_id": afe.well.project_id if afe.well else None,
                "project_code": (
                    afe.well.project.code if afe.well and afe.well.project else None
                ),
                "depth_unit_code": afe.depth_unit.code if afe.depth_unit else None,
                "item_count": len(active_items),
                "sections": sections,
                "items": items,
                "audit_logs": audit_logs,
            }
        )


class AfeLineService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.repository = AfeLineRepository(session)

    def list_items(self, afe_id: UUID) -> list[AfeLineRead]:
        self._afe(afe_id)
        return [self.read(item) for item in self.repository.list_for_afe(afe_id) if item.is_active]

    def list_removed_items(self, afe_id: UUID) -> list[AfeLineRead]:
        """Soft-deleted lines of an AFE, for recovery in the lines workspace."""
        self._afe(afe_id)
        return [
            self.read(item)
            for item in self.repository.list_for_afe(afe_id)
            if not item.is_active
        ]

    def create(self, afe_id: UUID, payload: AfeLineCreate, commit: bool = True) -> AfeLineRead:
        afe = self._afe(afe_id, must_be_draft=True)
        values = payload.model_dump()
        self._validate_references(values)
        self._apply_rate_basis(afe, values)
        item = AfeLine(
            **values,
            afe_id=afe.id,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        self.session.add(item)
        try:
            self.session.flush()
            _audit(self.session, self.actor_id, "create", "afe_line", item.id, f"{afe.code}:{values.get('line_number')}", values)
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
        afe = self._afe(item.afe_id, must_be_draft=True)
        values = payload.model_dump(exclude_unset=True)
        self._validate_references(values)
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
        self._apply_rate_basis(afe, merged)
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
        _audit(self.session, self.actor_id, "update", "afe_line", item.id, str(item.line_number), values)
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
        self.session.flush()
        _audit(self.session, self.actor_id, "soft_delete", "afe_line", item.id, str(item.line_number), None)
        self.session.commit()

    def recover(self, item_id: UUID) -> AfeLineRead:
        """Restore a removed (soft-deleted) AFE line on a draft AFE."""
        item = self.repository.get(item_id)
        if item is None:
            raise NotFoundError("AFE item not found")
        afe = self._afe(item.afe_id, must_be_draft=True)
        if item.is_active:
            raise BusinessValidationError("AFE line is not deleted and cannot be recovered")
        clash = self.session.scalar(
            select(AfeLine).where(
                AfeLine.afe_id == afe.id,
                AfeLine.line_number == item.line_number,
                AfeLine.is_active.is_(True),
                AfeLine.id != item.id,
            )
        )
        if clash:
            raise ConflictError(
                f"Line number {item.line_number} is already in use on this AFE. "
                "Edit the line numbers first, then recover the removed line."
            )
        item.is_active, item.updated_by = True, self.actor_id
        self.session.flush()
        _audit(
            self.session,
            self.actor_id,
            "recover",
            "afe_line",
            item.id,
            str(item.line_number),
            None,
        )
        self.session.commit()
        self.session.refresh(item)
        return self.read(item)

    def validate_bulk(self, afe_id: UUID, rows: list[AfeLineCreate]) -> BulkValidationResult:
        afe = self._afe(afe_id, must_be_draft=True)
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
                self._apply_rate_basis(afe, values)
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
            raise BusinessValidationError("Submitted AFE items are read-only. Reopen the AFE to edit.")
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

    def _apply_rate_basis(self, afe: Afe, values: dict[str, Any]) -> None:
        item = self.session.get(CatalogItem, values["catalog_item_id"])
        if item is None:
            raise BusinessValidationError("catalog_item_id must reference an active record")
        catalogue_basis = getattr(item, "rate_basis", None)

        # Derive planned duration days from section if not explicitly given
        planned_duration = values.get("planned_duration_days")
        if (planned_duration is None or planned_duration == 0) and values.get("hole_section_id"):
            # Check AFE sections
            for sec in afe.sections:
                if sec.hole_section_id == values["hole_section_id"] and sec.is_active:
                    planned_duration = sec.planned_days
                    break
        if planned_duration is None or planned_duration == 0:
            planned_duration = afe.total_planned_days if afe.total_planned_days > 0 else Decimal("1")

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
                planned_duration_days=planned_duration,
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
        catalog_item = item.catalog_item
        cost_code = item.cost_code
        unit = item.unit
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
                "catalog_item_code": catalog_item.code if catalog_item else None,
                "catalog_item_name": catalog_item.name if catalog_item else None,
                "item_type": catalog_item.item_type if catalog_item else None,
                "cost_code": cost_code.code if cost_code else None,
                "unit_code": unit.code if unit else None,
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
