"""Excel round-trip workflow for Phase 4 estimate line builds."""

import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.integrations.excel.exporter import ExcelExporter
from app.integrations.excel.mapper import ExcelMapper
from app.integrations.excel.reader import ExcelReader
from app.integrations.excel.templates import ExcelTemplateService
from app.models.estimates import EstimateVersion
from app.models.import_tracking import ImportBatch, ImportError
from app.models.master_data import Rate, Unit, Vendor
from app.repositories.imports import ImportBatchRepository
from app.schemas.estimates import EstimateItemUpdate
from app.schemas.imports import ImportCommitResponse, ImportPreviewResponse
from app.schemas.master_data import BulkRowError
from app.services.audit import log_entity_action
from app.services.estimates import CostEstimateService


class EstimateExcelService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session, self.actor_id = session, actor_id
        self.batches = ImportBatchRepository(session)

    def preview(self, version_id: UUID, filename: str, content: bytes) -> ImportPreviewResponse:
        version = self.version(version_id)
        workbook = ExcelReader().read(content, filename)
        mapped = ExcelMapper().map("estimate-items", workbook.columns, workbook.rows)
        by_line = {item.line_number: item for item in version.items}
        staged: list[dict[str, Any]] = []
        errors: list[BulkRowError] = []
        for index, source in enumerate(mapped.rows):
            try:
                line = int(source["line_number"])
                item = by_line.get(line)
                if item is None:
                    raise ValueError(f"Line {line} does not exist in this estimate version")
                values: dict[str, Any] = {"id": str(item.id)}
                try:
                    values["quantity"] = Decimal(str(source["quantity"]))
                except InvalidOperation as exc:
                    raise ValueError("quantity must be numeric") from exc
                unit_code = str(source["unit_code"]).strip().upper()
                unit = self.session.scalar(
                    select(Unit).where(Unit.code == unit_code, Unit.is_active.is_(True))
                )
                if unit is None:
                    raise ValueError(f"Active unit '{unit_code}' does not exist")
                values["unit_id"] = str(unit.id)
                vendor_code = source.get("vendor_code")
                if vendor_code not in (None, ""):
                    vendor = self.session.scalar(
                        select(Vendor).where(
                            Vendor.code == str(vendor_code).strip().upper(),
                            Vendor.is_active.is_(True),
                        )
                    )
                    if vendor is None:
                        raise ValueError(f"Active vendor '{vendor_code}' does not exist")
                    values["vendor_id"] = str(vendor.id)
                if source.get("rate_id") not in (None, ""):
                    rate = self.session.get(Rate, UUID(str(source["rate_id"])))
                    if rate is None or not rate.is_active or rate.item_id != item.catalog_item_id:
                        raise ValueError("rate_id is inactive, missing, or belongs to another item")
                    values["rate_id"] = str(rate.id)
                    values["vendor_id"] = str(rate.vendor_id)
                if source.get("notes") not in (None, ""):
                    values["notes"] = str(source["notes"])
                staged.append(values)
            except (ValueError, TypeError) as exc:
                errors.append(
                    BulkRowError(
                        row_index=index + 2,
                        code="row_validation_error",
                        message=str(exc),
                    )
                )
        batch = ImportBatch(
            entity_type=f"estimate-items:{version_id}",
            filename=Path(filename).name[:255],
            file_sha256=hashlib.sha256(content).hexdigest(),
            mapping_profile=mapped.profile.name,
            mapping_version=mapped.profile.version,
            status="invalid" if errors else "validated",
            total_rows=len(mapped.rows),
            valid_rows=len(staged),
            error_rows=len(errors),
            imported_rows=0,
            staged_rows=jsonable_encoder(staged),
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        for error in errors:
            batch.errors.append(
                ImportError(
                    row_number=error.row_index,
                    error_code=error.code,
                    message=error.message,
                    created_by=self.actor_id,
                    updated_by=self.actor_id,
                )
            )
        self.batches.add(batch)
        self.session.flush()
        log_entity_action(
            self.session,
            self.actor_id,
            "import_preview",
            "estimate_import_batch",
            entity_id=batch.id,
            entity_code=str(version_id),
            details={
                "estimate_version_id": str(version_id),
                "filename": batch.filename,
                "total_rows": batch.total_rows,
                "valid_rows": batch.valid_rows,
                "error_rows": batch.error_rows,
                "status": batch.status,
            },
        )
        self.session.commit()
        return ImportPreviewResponse(
            batch_id=batch.id,
            entity_type="estimate-items",
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

    def commit(self, version_id: UUID, batch_id: UUID) -> ImportCommitResponse:
        self.version(version_id)
        batch = self.batches.get(batch_id)
        if batch is None or batch.entity_type != f"estimate-items:{version_id}":
            raise NotFoundError("Estimate import batch not found")
        if batch.status != "validated" or batch.error_rows:
            raise BusinessValidationError("Only a fully validated estimate batch can be committed")
        rows = [
            (UUID(str(row["id"])), EstimateItemUpdate.model_validate(row))
            for row in batch.staged_rows
        ]
        CostEstimateService(self.session, self.actor_id).bulk_update_items(rows)
        batch.status = "committed"
        batch.imported_rows = len(rows)
        batch.updated_by = self.actor_id
        self.session.flush()
        log_entity_action(
            self.session,
            self.actor_id,
            "import_commit",
            "estimate_import_batch",
            entity_id=batch.id,
            entity_code=str(version_id),
            details={
                "estimate_version_id": str(version_id),
                "imported_rows": batch.imported_rows,
                "status": batch.status,
            },
        )
        self.session.commit()
        return ImportCommitResponse(
            batch_id=batch.id, status=batch.status, imported_rows=batch.imported_rows
        )

    @staticmethod
    def template() -> bytes:
        return ExcelTemplateService().create_blank("estimate-items")

    def export(self, version_id: UUID) -> bytes:
        version = self.version(version_id)
        rows = [
            {
                "line_number": item.line_number,
                "item_code": item.catalog_item.code if item.catalog_item else None,
                "item_type": item.catalog_item.item_type if item.catalog_item else None,
                "cost_code": item.cost_code.code if item.cost_code else None,
                "vendor_code": item.vendor.code if item.vendor else None,
                "rate_id": str(item.rate_id) if item.rate_id else None,
                "quantity": item.quantity,
                "unit_code": item.unit.code if item.unit else None,
                "notes": item.notes,
            }
            for item in version.items
        ]
        return ExcelExporter().export("estimate-items", rows)

    def version(self, version_id: UUID) -> EstimateVersion:
        version = self.session.get(EstimateVersion, version_id)
        if version is None:
            raise NotFoundError("Estimate version not found")
        return version
