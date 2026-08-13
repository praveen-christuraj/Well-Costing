"""Requirement-item Excel import, template, and export routes."""

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
from app.services.requirement_excel import RequirementExcelService

router = APIRouter(prefix="/requirements", tags=["requirement Excel"])


@router.post("/{requirement_id}/import/preview", response_model=ImportPreviewResponse)
async def preview_requirement_import(
    requirement_id: UUID,
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
    return RequirementExcelService(session, current_user.id).preview(
        requirement_id,
        file.filename or "requirement-items.xlsx",
        await file.read(),
        overrides,
    )


@router.post("/{requirement_id}/import/commit", response_model=ImportCommitResponse)
def commit_requirement_import(
    requirement_id: UUID,
    payload: ImportCommitRequest,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> ImportCommitResponse:
    return RequirementExcelService(session, current_user.id).commit(
        requirement_id, payload.batch_id
    )


@router.get("/{requirement_id}/import/template")
def requirement_template(
    requirement_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    service = RequirementExcelService(session, current_user.id)
    service.draft_requirement(requirement_id)
    return Response(
        content=service.template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="requirement-items-template.xlsx"'},
    )


@router.get("/{requirement_id}/export")
def export_requirement(
    requirement_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    content = RequirementExcelService(session, current_user.id).export(requirement_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="requirement-items-export.xlsx"'},
    )
