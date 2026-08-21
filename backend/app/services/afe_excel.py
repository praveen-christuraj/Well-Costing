"""Excel import/export workflow for AFE lines."""

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
from app.models.afe import Afe, AfeLine
from app.models.import_tracking import ImportBatch, ImportError
from app.models.master_data import CatalogItem, CostCode, HoleSection, Unit
from app.repositories.imports import ImportBatchRepository
from app.schemas.afe import AfeLineCreate
from app.schemas.imports import ImportCommitResponse, ImportPreviewResponse
from app.schemas.master_data import BulkRowError
from app.services.afe import AfeLineService


class AfeExcelService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.batches = ImportBatchRepository(session)

    def preview(
        self,
        afe_id: UUID,
        filename: str,
        content: bytes,
        mapping_overrides: dict[str, str] | None = None,
    ) -> ImportPreviewResponse:
        self.draft_afe(afe_id)
        workbook = ExcelReader().read(content, filename)
        mapped = ExcelMapper().map("afe-lines", workbook.columns, workbook.rows, mapping_overrides)
        valid_rows: list[dict[str, Any]] = []
        errors: list[BulkRowError] = []
        seen: set[int] = set()
        existing = {
            item.line_number
            for item in self.session.scalars(select(AfeLine).where(AfeLine.afe_id == afe_id))
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
            entity_type=f"afe-lines:{afe_id}",
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
            entity_type="afe-lines",
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

    def commit(self, afe_id: UUID, batch_id: UUID) -> ImportCommitResponse:
        self.draft_afe(afe_id)
        batch = self.batches.get(batch_id)
        if batch is None or batch.entity_type != f"afe-lines:{afe_id}":
            raise NotFoundError("AFE import batch not found")
        if batch.status == "committed":
            return ImportCommitResponse(
                batch_id=batch.id, status=batch.status, imported_rows=batch.imported_rows
            )
        if batch.status != "validated" or batch.error_rows:
            raise BusinessValidationError("Only a fully validated batch can be committed")
        service = AfeLineService(self.session, self.actor_id)
        try:
            for row in batch.staged_rows:
                service.create(afe_id, AfeLineCreate.model_validate(row), commit=False)
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
        return ExcelTemplateService().create_blank("afe-lines")

    def export(self, afe_id: UUID) -> bytes:
        afe = self.session.get(Afe, afe_id)
        if afe is None:
            raise NotFoundError("AFE not found")
        rows: list[dict[str, Any]] = []
        for item in afe.items:
            rows.append(
                {
                    "line_number": item.line_number,
                    "catalog_item_code": item.catalog_item.code,
                    "item_type": item.catalog_item.item_type,
                    "cost_code": item.cost_code.code,
                    "quantity": item.quantity,
                    "unit_code": item.unit.code,
                    "hole_section_code": item.hole_section.code if item.hole_section else None,
                    "rate_basis": item.rate_basis,
                    "daily_consumption": item.daily_consumption,
                    "quantity_override_reason": item.quantity_override_reason,
                    "planned_duration_days": item.planned_duration_days,
                    "planned_depth_from": item.planned_depth_from,
                    "planned_depth_to": item.planned_depth_to,
                    "depth_unit_code": item.depth_unit.code if item.depth_unit else None,
                    "notes": item.notes,
                    "is_active": item.is_active,
                }
            )
        return ExcelExporter().export("afe-lines", rows)

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
            ("hole_section_code", "hole_section_id", HoleSection),
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
                "daily_consumption",
                "planned_duration_days",
                "planned_depth_from",
                "planned_depth_to",
            ):
                if field in values:
                    values[field] = Decimal(str(values[field]))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(
                "Line, quantity, consumption, duration, and depth values must be numeric"
            ) from exc
        if "is_active" in values:
            values["is_active"] = str(values["is_active"]).strip().lower() not in {
                "false",
                "no",
                "0",
                "inactive",
            }
        return AfeLineCreate.model_validate(values).model_dump(mode="json", exclude_none=True)

    def draft_afe(self, afe_id: UUID) -> Afe:
        afe = self.session.get(Afe, afe_id)
        if afe is None or not afe.is_active:
            raise NotFoundError("AFE not found")
        if afe.status != "draft":
            raise BusinessValidationError("Only draft AFEs can be imported")
        return afe
