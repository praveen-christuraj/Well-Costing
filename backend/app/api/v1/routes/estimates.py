"""Phase 4 cost-builder routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.estimates import (
    AssumptionUpsert,
    BulkAssignRequest,
    BulkEstimateItemUpdate,
    DuplicateItemsRequest,
    DuplicateVersionRequest,
    EstimateGenerateRequest,
    EstimateItemRead,
    EstimateItemUpdate,
    EstimateRead,
    EstimateVersionRead,
)
from app.schemas.imports import ImportCommitRequest, ImportCommitResponse, ImportPreviewResponse
from app.schemas.master_data import PageResponse
from app.services.estimate_excel import EstimateExcelService
from app.services.estimates import CostEstimateService

router = APIRouter(prefix="/estimates", tags=["bulk cost build"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=PageResponse)
def list_estimates(
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    search: str | None = None,
) -> PageResponse:
    return CostEstimateService(session, current_user.id).list_page(page, page_size, search)


@router.post("/from-requirement", response_model=EstimateRead, status_code=201)
def generate_estimate(
    payload: EstimateGenerateRequest, current_user: CurrentUser, session: DbSession
) -> EstimateRead:
    return CostEstimateService(session, current_user.id).generate(payload)


@router.patch("/items/bulk", response_model=list[EstimateItemRead])
def bulk_update_items(
    payload: BulkEstimateItemUpdate, current_user: CurrentUser, session: DbSession
) -> list[EstimateItemRead]:
    rows = [
        (
            row.id,
            EstimateItemUpdate.model_validate(row.model_dump(exclude={"id"}, exclude_unset=True)),
        )
        for row in payload.rows
    ]
    return CostEstimateService(session, current_user.id).bulk_update_items(rows)


@router.post("/versions/{version_id}/bulk-assign", response_model=list[EstimateItemRead])
def bulk_assign(
    version_id: UUID,
    payload: BulkAssignRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> list[EstimateItemRead]:
    return CostEstimateService(session, current_user.id).bulk_assign(version_id, payload)


@router.post(
    "/versions/{version_id}/duplicate-items", response_model=list[EstimateItemRead], status_code=201
)
def duplicate_items(
    version_id: UUID,
    payload: DuplicateItemsRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> list[EstimateItemRead]:
    return CostEstimateService(session, current_user.id).duplicate_items(
        version_id, payload.item_ids
    )


@router.put("/versions/{version_id}/assumptions", response_model=EstimateVersionRead)
def upsert_assumption(
    version_id: UUID,
    payload: AssumptionUpsert,
    current_user: CurrentUser,
    session: DbSession,
) -> EstimateVersionRead:
    return CostEstimateService(session, current_user.id).upsert_assumption(version_id, payload)


@router.post("/versions/{version_id}/import/preview", response_model=ImportPreviewResponse)
async def preview_import(
    version_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
) -> ImportPreviewResponse:
    return EstimateExcelService(session, current_user.id).preview(
        version_id, file.filename or "estimate-items.xlsx", await file.read()
    )


@router.post("/versions/{version_id}/import/commit", response_model=ImportCommitResponse)
def commit_import(
    version_id: UUID,
    payload: ImportCommitRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ImportCommitResponse:
    return EstimateExcelService(session, current_user.id).commit(version_id, payload.batch_id)


@router.get("/versions/{version_id}/template")
def download_template(version_id: UUID, current_user: CurrentUser, session: DbSession) -> Response:
    EstimateExcelService(session, current_user.id).version(version_id)
    return Response(
        content=EstimateExcelService.template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="estimate-items-template.xlsx"'},
    )


@router.get("/versions/{version_id}/export")
def exportversion(version_id: UUID, current_user: CurrentUser, session: DbSession) -> Response:
    return Response(
        content=EstimateExcelService(session, current_user.id).export(version_id),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="estimate-items-export.xlsx"'},
    )


@router.post("/{estimate_id}/versions", response_model=EstimateVersionRead, status_code=201)
def duplicate_version(
    estimate_id: UUID,
    payload: DuplicateVersionRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> EstimateVersionRead:
    return CostEstimateService(session, current_user.id).duplicate_version(
        estimate_id, payload.notes
    )


@router.get("/{estimate_id}", response_model=EstimateRead)
def get_estimate(estimate_id: UUID, current_user: CurrentUser, session: DbSession) -> EstimateRead:
    return CostEstimateService(session, current_user.id).get(estimate_id)
