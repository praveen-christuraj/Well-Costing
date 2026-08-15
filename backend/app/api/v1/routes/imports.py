"""Excel preview/commit, templates, exports, and import-history routes."""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.core.exceptions import BusinessValidationError
from app.db.session import get_db
from app.schemas.imports import (
    ImportBatchRead,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    MappingOverride,
)
from app.schemas.master_data import PageResponse
from app.services.excel_import import ExcelImportService

router = APIRouter(tags=["Excel imports"])


@router.post("/import/{entity}/preview", response_model=ImportPreviewResponse)
async def preview_import(
    entity: str,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    sheet_name: Annotated[str | None, Form()] = None,
    mapping_json: Annotated[str | None, Form()] = None,
) -> ImportPreviewResponse:
    overrides: dict[str, str] | None = None
    if mapping_json:
        try:
            overrides = MappingOverride.model_validate(json.loads(mapping_json)).source_to_target
        except (json.JSONDecodeError, ValidationError) as exc:
            raise BusinessValidationError("mapping_json is invalid") from exc
    content = await file.read()
    return ExcelImportService(session, current_user.id).preview(
        entity=entity,
        filename=file.filename or "upload.xlsx",
        content=content,
        sheet_name=sheet_name,
        mapping_overrides=overrides,
    )


@router.post("/import/{entity}/commit", response_model=ImportCommitResponse)
def commit_import(
    entity: str,
    payload: ImportCommitRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> ImportCommitResponse:
    return ExcelImportService(session, current_user.id).commit(entity, payload.batch_id)


@router.get("/import/{entity}/template")
def download_template(
    entity: str,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    format: Annotated[str, Query(pattern="^(xlsx|csv)$")] = "xlsx",
) -> Response:
    service = ExcelImportService(session, current_user.id)
    if format == "csv":
        return Response(
            content=service.template_csv(entity),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{entity}-template.csv"'},
        )
    content = service.template(entity)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{entity}-template.xlsx"'},
    )


@router.get("/export/{entity}")
def export_entity(
    entity: str,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    content = ExcelImportService(session, current_user.id).export(entity)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{entity}-export.xlsx"'},
    )


@router.get("/imports/batches", response_model=PageResponse)
def import_history(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
) -> PageResponse:
    return ExcelImportService(session, current_user.id).history(page, page_size)


@router.get("/imports/batches/{batch_id}", response_model=ImportBatchRead)
def import_batch(
    batch_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> ImportBatchRead:
    return ExcelImportService(session, current_user.id).get_batch(batch_id)
