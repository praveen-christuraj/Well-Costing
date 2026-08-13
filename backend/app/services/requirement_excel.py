"""Excel import/export workflow for requirement line items."""

import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.integrations.excel.exporter import ExcelExporter
from app.integrations.excel.mapper import ExcelMapper
from app.integrations.excel.reader import ExcelReader
from app.integrations.excel.templates import ExcelTemplateService
from app.models.import_tracking import ImportBatch, ImportError
from app.models.master_data import CatalogItem, CostCode, Unit
from app.models.requirements import RequirementItem, WellRequirement
from app.repositories.imports import ImportBatchRepository
from app.schemas.imports import ImportCommitResponse, ImportPreviewResponse
from app.schemas.master_data import BulkRowError
from app.schemas.requirements import RequirementItemCreate
from app.services.requirements import RequirementItemService


class RequirementExcelService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.batches = ImportBatchRepository(session)

    def preview(
        self,
        requirement_id: UUID,
        filename: str,
        content: bytes,
        mapping_overrides: dict[str, str] | None = None,
    ) -> ImportPreviewResponse:
        self.draft_requirement(requirement_id)
        workbook = ExcelReader().read(content, filename)
        mapped = ExcelMapper().map(
            "requirement-items", workbook.columns, workbook.rows, mapping_overrides
        )
        valid_rows: list[dict[str, Any]] = []
        errors: list[BulkRowError] = []
        seen: set[int] = set()
        existing = {
            item.line_number
            for item in self.session.scalars(
                select(RequirementItem).where(RequirementItem.requirement_id == requirement_id)
            )
        }
        for index, row in enumerate(mapped.rows):
            excel_row = index + 2
            try:
                normalized = self._normalize(row)
                line = int(normalized["line_number"])
                if line in seen or line in existing:
                    raise ValueError(f"Line number {line} is duplicated or already exists")
                seen.add(line)
                valid_rows.append(normalized)
            except (ValueError, ValidationError) as exc:
                errors.append(
                    BulkRowError(
                        row_index=excel_row,
                        code="row_validation_error",
                        message=str(exc),
                    )
                )
        batch = ImportBatch(
            entity_type=f"requirement-items:{requirement_id}",
            filename=Path(filename).name[:255],
            file_sha256=hashlib.sha256(content).hexdigest(),
            mapping_profile=mapped.profile.name,
            mapping_version=mapped.profile.version,
            status="invalid" if errors else "validated",
            total_rows=len(mapped.rows),
            valid_rows=len(valid_rows),
            error_rows=len({error.row_index for error in errors}),
            imported_rows=0,
            staged_rows=jsonable_encoder(valid_rows),
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        for error in errors:
            batch.errors.append(
                ImportError(
                    row_number=error.row_index,
                    column_name=error.column,
                    error_code=error.code,
                    message=error.message,
                    created_by=self.actor_id,
                    updated_by=self.actor_id,
                )
            )
        self.batches.add(batch)
        self.session.commit()
        return ImportPreviewResponse(
            batch_id=batch.id,
            entity_type="requirement-items",
            status=batch.status,
            mapping_profile=batch.mapping_profile,
            mapping_version=batch.mapping_version,
            detected_columns=mapped.detected_columns,
            applied_mapping=mapped.applied_mapping,
            total_rows=batch.total_rows,
            valid_rows=batch.valid_rows,
            error_rows=batch.error_rows,
            errors=errors,
            sample=batch.staged_rows[:20],
        )

    def commit(self, requirement_id: UUID, batch_id: UUID) -> ImportCommitResponse:
        self.draft_requirement(requirement_id)
        batch = self.batches.get(batch_id)
        if batch is None or batch.entity_type != f"requirement-items:{requirement_id}":
            raise NotFoundError("Requirement import batch not found")
        if batch.status == "committed":
            return ImportCommitResponse(
                batch_id=batch.id, status=batch.status, imported_rows=batch.imported_rows
            )
        if batch.status != "validated" or batch.error_rows:
            raise BusinessValidationError("Only a fully validated batch can be committed")
        service = RequirementItemService(self.session, self.actor_id)
        try:
            for row in batch.staged_rows:
                service.create(
                    requirement_id, RequirementItemCreate.model_validate(row), commit=False
                )
            batch.status = "committed"
            batch.imported_rows = len(batch.staged_rows)
            batch.updated_by = self.actor_id
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return ImportCommitResponse(
            batch_id=batch.id, status=batch.status, imported_rows=batch.imported_rows
        )

    @staticmethod
    def template() -> bytes:
        return ExcelTemplateService().create_blank("requirement-items")

    def export(self, requirement_id: UUID) -> bytes:
        requirement = self.session.get(WellRequirement, requirement_id)
        if requirement is None:
            raise NotFoundError("Requirement not found")
        rows: list[dict[str, Any]] = []
        for item in requirement.items:
            rows.append(
                {
                    "line_number": item.line_number,
                    "catalog_item_code": item.catalog_item.code,
                    "item_type": item.catalog_item.item_type,
                    "cost_code": item.cost_code.code,
                    "quantity": item.quantity,
                    "unit_code": item.unit.code,
                    "section_name": item.section_name,
                    "planned_duration_days": item.planned_duration_days,
                    "planned_depth_from": item.planned_depth_from,
                    "planned_depth_to": item.planned_depth_to,
                    "depth_unit_code": item.depth_unit.code if item.depth_unit else None,
                    "notes": item.notes,
                    "is_active": item.is_active,
                }
            )
        return ExcelExporter().export("requirement-items", rows)

    def _normalize(self, source: dict[str, Any]) -> dict[str, Any]:
        values = {key: value for key, value in source.items() if value not in (None, "")}
        item_code = str(values.pop("catalog_item_code")).strip().upper()
        item_type = str(values.pop("item_type")).strip().lower()
        item = self.session.scalar(
            select(CatalogItem).where(
                CatalogItem.code == item_code,
                CatalogItem.item_type == item_type,
                CatalogItem.is_active.is_(True),
            )
        )
        if item is None:
            raise ValueError(f"Active {item_type} '{item_code}' does not exist")
        values["catalog_item_id"] = item.id
        for source_field, target_field, model in [
            ("cost_code", "cost_code_id", CostCode),
            ("unit_code", "unit_id", Unit),
            ("depth_unit_code", "depth_unit_id", Unit),
        ]:
            code = values.pop(source_field, None)
            if code in (None, ""):
                continue
            record = self.session.scalar(
                select(model).where(
                    model.code == str(code).strip().upper(), model.is_active.is_(True)
                )
            )
            if record is None:
                raise ValueError(f"Active {source_field} '{code}' does not exist")
            values[target_field] = record.id
        try:
            values["line_number"] = int(values["line_number"])
            for field in (
                "quantity",
                "planned_duration_days",
                "planned_depth_from",
                "planned_depth_to",
            ):
                if field in values:
                    values[field] = Decimal(str(values[field]))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("Line, quantity, duration, and depth values must be numeric") from exc
        if "is_active" in values:
            values["is_active"] = str(values["is_active"]).strip().lower() not in {
                "false",
                "no",
                "0",
                "inactive",
            }
        return RequirementItemCreate.model_validate(values).model_dump(
            mode="json", exclude_none=True
        )

    def draft_requirement(self, requirement_id: UUID) -> WellRequirement:
        requirement = self.session.get(WellRequirement, requirement_id)
        if requirement is None or not requirement.is_active:
            raise NotFoundError("Requirement not found")
        if requirement.status != "draft":
            raise BusinessValidationError("Only draft requirements can be imported")
        return requirement
