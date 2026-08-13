"""Transactional Excel preview, validation, commit, history, and export workflows."""

import hashlib
from math import ceil
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessValidationError, NotFoundError
from app.integrations.excel.exporter import ExcelExporter
from app.integrations.excel.importer import ExcelImportPipeline
from app.integrations.excel.templates import ExcelTemplateService
from app.models.import_tracking import ImportBatch, ImportError
from app.repositories.imports import ImportBatchRepository
from app.schemas.imports import (
    ImportBatchRead,
    ImportCommitResponse,
    ImportPreviewResponse,
)
from app.schemas.master_data import MasterDataCreate, PageResponse, RateCreate
from app.services.master_data import MasterDataService, RateService, get_entity_config


class ExcelImportService:
    def __init__(self, session: Session, actor_id: UUID) -> None:
        self.session = session
        self.actor_id = actor_id
        self.batches = ImportBatchRepository(session)

    def preview(
        self,
        *,
        entity: str,
        filename: str,
        content: bytes,
        sheet_name: str | None,
        mapping_overrides: dict[str, str] | None,
    ) -> ImportPreviewResponse:
        if entity != "rates":
            get_entity_config(entity)
        pipeline = ExcelImportPipeline(self.session).preview(
            entity=entity,
            filename=filename,
            content=content,
            sheet_name=sheet_name,
            mapping_overrides=mapping_overrides,
        )
        validation = pipeline.validation
        error_rows = len({error.row_index for error in validation.errors})
        batch = ImportBatch(
            entity_type=entity,
            filename=Path(filename).name[:255],
            file_sha256=hashlib.sha256(content).hexdigest(),
            mapping_profile=pipeline.profile.name,
            mapping_version=pipeline.profile.version,
            status="invalid" if validation.errors else "validated",
            total_rows=validation.total_rows,
            valid_rows=len(validation.valid_rows),
            error_rows=error_rows,
            imported_rows=0,
            staged_rows=jsonable_encoder(validation.valid_rows),
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        for issue in validation.errors:
            batch.errors.append(
                ImportError(
                    row_number=issue.row_index,
                    column_name=issue.column,
                    error_code=issue.code,
                    message=issue.message,
                    created_by=self.actor_id,
                    updated_by=self.actor_id,
                )
            )
        self.batches.add(batch)
        self.session.commit()
        return ImportPreviewResponse(
            batch_id=batch.id,
            entity_type=entity,
            status=batch.status,
            mapping_profile=batch.mapping_profile,
            mapping_version=batch.mapping_version,
            detected_columns=pipeline.detected_columns,
            applied_mapping=pipeline.applied_mapping,
            total_rows=batch.total_rows,
            valid_rows=batch.valid_rows,
            error_rows=batch.error_rows,
            errors=validation.errors,
            sample=batch.staged_rows[:20],
        )

    def commit(self, entity: str, batch_id: UUID) -> ImportCommitResponse:
        batch = self.batches.get(batch_id)
        if batch is None or batch.entity_type != entity:
            raise NotFoundError("Import batch not found")
        if batch.status == "committed":
            return ImportCommitResponse(
                batch_id=batch.id, status=batch.status, imported_rows=batch.imported_rows
            )
        if batch.status != "validated" or batch.error_rows:
            raise BusinessValidationError("Only a fully validated import batch can be committed")

        try:
            imported = 0
            if entity == "rates":
                service = RateService(self.session, self.actor_id)
                for staged in batch.staged_rows:
                    service.create(RateCreate.model_validate(staged), commit=False)
                    imported += 1
            else:
                service = MasterDataService(self.session, entity, self.actor_id)
                for staged in batch.staged_rows:
                    service.create(MasterDataCreate.model_validate(staged), commit=False)
                    imported += 1
            batch.status = "committed"
            batch.imported_rows = imported
            batch.updated_by = self.actor_id
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return ImportCommitResponse(
            batch_id=batch.id, status=batch.status, imported_rows=batch.imported_rows
        )

    def history(self, page: int, page_size: int) -> PageResponse:
        batches, total = self.batches.list(page, page_size)
        return PageResponse(
            items=[ImportBatchRead.model_validate(batch) for batch in batches],
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )

    def get_batch(self, batch_id: UUID) -> ImportBatchRead:
        batch = self.batches.get(batch_id)
        if batch is None:
            raise NotFoundError("Import batch not found")
        return ImportBatchRead.model_validate(batch)

    @staticmethod
    def template(entity: str) -> bytes:
        return ExcelTemplateService().create_blank(entity)

    def export(self, entity: str) -> bytes:
        if entity == "rates":
            page = RateService(self.session, self.actor_id).list_page(
                page=1,
                page_size=10_000,
                search=None,
                is_active=None,
                sort_by="effective_from",
                sort_order="asc",
            )
        else:
            page = MasterDataService(self.session, entity, self.actor_id).list_page(
                page=1,
                page_size=10_000,
                search=None,
                is_active=None,
                sort_by="code",
                sort_order="asc",
            )
        rows: list[dict[str, Any]] = []
        for item in page.items:
            if hasattr(item, "model_dump"):
                rows.append(item.model_dump(mode="json"))
            else:
                rows.append(dict(item))
        return ExcelExporter().export(entity, rows)
