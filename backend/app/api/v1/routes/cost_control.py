"""Phase 8 bulk cost-state staging, Excel preview, and posting routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.domain.cost_control.types import CostState
from app.schemas.cost_control import (
    CostControlBatchCreate,
    CostControlBatchPage,
    CostControlBatchRead,
    CostControlImportPreview,
)
from app.services.cost_control import CostControlService

router = APIRouter(prefix="/cost-control", tags=["cost control"])


@router.get("/batches", response_model=CostControlBatchPage)
def list_cost_control_batches(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> CostControlBatchPage:
    return CostControlService(session, current_user).list_batches()


@router.post("/batches/validate", response_model=CostControlBatchRead)
def validate_manual_batch(
    request: CostControlBatchCreate,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> CostControlBatchRead:
    return CostControlService(session, current_user).stage_manual(request)


@router.post("/imports/preview", response_model=CostControlImportPreview)
async def preview_cost_control_import(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    estimate_version_id: Annotated[UUID, Form()],
    cost_state: Annotated[CostState, Form()],
    file: Annotated[UploadFile, File()],
    sheet_name: Annotated[str | None, Form()] = None,
) -> CostControlImportPreview:
    content = await file.read()
    return CostControlService(session, current_user).preview_excel(
        estimate_version_id=estimate_version_id,
        cost_state=cost_state,
        filename=file.filename or "cost-control.xlsx",
        content=content,
        sheet_name=sheet_name,
    )


@router.post("/batches/{batch_id}/post", response_model=CostControlBatchRead)
def post_cost_control_batch(
    batch_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> CostControlBatchRead:
    return CostControlService(session, current_user).post(batch_id)


@router.get("/batches/{batch_id}", response_model=CostControlBatchRead)
def get_cost_control_batch(
    batch_id: UUID,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> CostControlBatchRead:
    return CostControlService(session, current_user).get(batch_id)


@router.get("/template")
def download_cost_control_template(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> Response:
    del current_user, session
    return Response(
        content=CostControlService.template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="cost-control-template.xlsx"'},
    )
