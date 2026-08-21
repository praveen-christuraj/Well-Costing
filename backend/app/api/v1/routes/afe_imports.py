"""AFE-item Excel import, template, and export routes."""

import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.core.exceptions import BusinessValidationError
from app.db.session import get_db
from app.schemas.imports import (
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
    MappingOverride,
)
from app.services.afe_excel import AfeExcelService

router = APIRouter(prefix="/afes", tags=["AFE Excel"])


@router.post("/{afe_id}/import/preview", response_model=ImportPreviewResponse)
async def preview_afe_import(
    afe_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    mapping_json: Annotated[str | None, Form()] = None,
) -> ImportPreviewResponse:
    overrides = None
    if mapping_json:
        try:
            overrides = MappingOverride.model_validate(json.loads(mapping_json)).source_to_target
        except (json.JSONDecodeError, ValidationError) as exc:
            raise BusinessValidationError("mapping_json is invalid") from exc
    return AfeExcelService(session, current_user.id).preview(
        afe_id,
        file.filename or "afe-lines.xlsx",
        await file.read(),
        overrides,
    )


@router.post("/{afe_id}/import/commit", response_model=ImportCommitResponse)
def commit_afe_import(
    afe_id: UUID,
    payload: ImportCommitRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> ImportCommitResponse:
    return AfeExcelService(session, current_user.id).commit(afe_id, payload.batch_id)


@router.get("/{afe_id}/import/template")
def afe_template(
    afe_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    service = AfeExcelService(session, current_user.id)
    service.draft_afe(afe_id)
    return Response(
        content=service.template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="afe-lines-template.xlsx"'},
    )


@router.get("/{afe_id}/export")
def export_afe(
    afe_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    content = AfeExcelService(session, current_user.id).export(afe_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="afe-lines-export.xlsx"'},
    )
