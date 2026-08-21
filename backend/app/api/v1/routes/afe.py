"""Phase 3 project, well, AFE, AFE sections, and bulk AFE-line routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.afe import (
    AfeCreate,
    AfeLineCreate,
    AfeLineRead,
    AfeLineUpdate,
    AfeRead,
    AfeReopenRequest,
    AfeUpdate,
    BulkAfeCreate,
    BulkAfeLinesCreate,
    BulkAfeLinesUpdate,
    BulkAfeUpdate,
    BulkProjectCreate,
    BulkProjectUpdate,
    BulkWellCreate,
    BulkWellUpdate,
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
from app.schemas.master_data import BulkValidationResult, PageResponse
from app.services.afe import (
    AfeLineService,
    AfeService,
    DrillingPhaseService,
    ProjectService,
    WellService,
)

router = APIRouter(tags=["AFE"])
DbSession = Annotated[Session, Depends(get_db)]


# ----------------------------------------------------------- Drilling Phases
@router.get("/drilling-phases", response_model=list[DrillingPhaseRead])
def list_drilling_phases(current_user: CurrentUser, session: DbSession) -> list[DrillingPhaseRead]:
    return DrillingPhaseService(session, current_user.id).list_all()


@router.post("/drilling-phases", response_model=DrillingPhaseRead, status_code=201)
def create_drilling_phase(
    payload: DrillingPhaseCreate, current_user: CurrentUser, session: DbSession
) -> DrillingPhaseRead:
    return DrillingPhaseService(session, current_user.id).create(payload)


@router.patch("/drilling-phases/{phase_id}", response_model=DrillingPhaseRead)
def update_drilling_phase(
    phase_id: UUID,
    payload: DrillingPhaseUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> DrillingPhaseRead:
    return DrillingPhaseService(session, current_user.id).update(phase_id, payload)


@router.delete("/drilling-phases/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_drilling_phase(
    phase_id: UUID, current_user: CurrentUser, session: DbSession
) -> Response:
    DrillingPhaseService(session, current_user.id).delete(phase_id)
    return Response(status_code=204)


# ------------------------------------------------------------------ Projects
@router.get("/projects", response_model=PageResponse)
def list_projects(
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    search: str | None = None,
    is_active: bool | None = None,
) -> PageResponse:
    return ProjectService(session, current_user.id).list_page(page, page_size, search, is_active)


@router.post("/projects", response_model=ProjectRead, status_code=201)
def create_project(
    payload: ProjectCreate, current_user: CurrentUser, session: DbSession
) -> ProjectRead:
    return ProjectService(session, current_user.id).create(payload)


@router.post("/projects/bulk/create", response_model=list[ProjectRead], status_code=201)
def bulk_create_projects(
    payload: BulkProjectCreate, current_user: CurrentUser, session: DbSession
) -> list[ProjectRead]:
    return ProjectService(session, current_user.id).bulk_create(payload.rows)


@router.patch("/projects/bulk/update", response_model=list[ProjectRead])
def bulk_update_projects(
    payload: BulkProjectUpdate, current_user: CurrentUser, session: DbSession
) -> list[ProjectRead]:
    rows = [
        (row.id, ProjectUpdate.model_validate(row.model_dump(exclude={"id"}, exclude_unset=True)))
        for row in payload.rows
    ]
    return ProjectService(session, current_user.id).bulk_update(rows)


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: UUID, current_user: CurrentUser, session: DbSession) -> ProjectRead:
    return ProjectService(session, current_user.id).get(project_id)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: UUID, payload: ProjectUpdate, current_user: CurrentUser, session: DbSession
) -> ProjectRead:
    return ProjectService(session, current_user.id).update(project_id, payload)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_project(project_id: UUID, current_user: CurrentUser, session: DbSession) -> Response:
    ProjectService(session, current_user.id).deactivate(project_id)
    return Response(status_code=204)


# --------------------------------------------------------------------- Wells
@router.get("/wells", response_model=PageResponse)
def list_wells(
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    search: str | None = None,
    project_id: UUID | None = None,
    is_active: bool | None = None,
) -> PageResponse:
    return WellService(session, current_user.id).list_page(
        page, page_size, search, project_id, is_active
    )


@router.post("/wells", response_model=WellRead, status_code=201)
def create_well(payload: WellCreate, current_user: CurrentUser, session: DbSession) -> WellRead:
    return WellService(session, current_user.id).create(payload)


@router.post("/wells/bulk/create", response_model=list[WellRead], status_code=201)
def bulk_create_wells(
    payload: BulkWellCreate, current_user: CurrentUser, session: DbSession
) -> list[WellRead]:
    return WellService(session, current_user.id).bulk_create(payload.rows)


@router.patch("/wells/bulk/update", response_model=list[WellRead])
def bulk_update_wells(
    payload: BulkWellUpdate, current_user: CurrentUser, session: DbSession
) -> list[WellRead]:
    rows = [
        (row.id, WellUpdate.model_validate(row.model_dump(exclude={"id"}, exclude_unset=True)))
        for row in payload.rows
    ]
    return WellService(session, current_user.id).bulk_update(rows)


@router.get("/wells/{well_id}", response_model=WellRead)
def get_well(well_id: UUID, current_user: CurrentUser, session: DbSession) -> WellRead:
    return WellService(session, current_user.id).get(well_id)


@router.patch("/wells/{well_id}", response_model=WellRead)
def update_well(
    well_id: UUID, payload: WellUpdate, current_user: CurrentUser, session: DbSession
) -> WellRead:
    return WellService(session, current_user.id).update(well_id, payload)


@router.delete("/wells/{well_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_well(well_id: UUID, current_user: CurrentUser, session: DbSession) -> Response:
    WellService(session, current_user.id).deactivate(well_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------- AFEs
@router.get("/afes", response_model=PageResponse)
def list_afes(
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    search: str | None = None,
    project_id: UUID | None = None,
    well_id: UUID | None = None,
    afe_status: Annotated[str | None, Query(alias="status")] = None,
    is_active: bool | None = None,
) -> PageResponse:
    return AfeService(session, current_user.id).list_page(
        page=page,
        page_size=page_size,
        search=search,
        project_id=project_id,
        well_id=well_id,
        status=afe_status,
        is_active=is_active,
    )


@router.post("/afes", response_model=AfeRead, status_code=201)
def create_afe(payload: AfeCreate, current_user: CurrentUser, session: DbSession) -> AfeRead:
    return AfeService(session, current_user.id).create(payload)


@router.post("/afes/bulk/create", response_model=list[AfeRead], status_code=201)
def bulk_create_afes(
    payload: BulkAfeCreate, current_user: CurrentUser, session: DbSession
) -> list[AfeRead]:
    return AfeService(session, current_user.id).bulk_create(payload.rows)


@router.patch("/afes/bulk/update", response_model=list[AfeRead])
def bulk_update_afes(
    payload: BulkAfeUpdate, current_user: CurrentUser, session: DbSession
) -> list[AfeRead]:
    rows = [
        (
            row.id,
            AfeUpdate.model_validate(row.model_dump(exclude={"id"}, exclude_unset=True)),
        )
        for row in payload.rows
    ]
    return AfeService(session, current_user.id).bulk_update(rows)


@router.post("/afes/{afe_id}/submit", response_model=AfeRead)
def submit_afe(afe_id: UUID, current_user: CurrentUser, session: DbSession) -> AfeRead:
    return AfeService(session, current_user.id).submit(afe_id)


@router.post("/afes/{afe_id}/reopen", response_model=AfeRead)
def reopen_afe(
    afe_id: UUID, payload: AfeReopenRequest, current_user: CurrentUser, session: DbSession
) -> AfeRead:
    return AfeService(session, current_user.id).reopen(afe_id, payload.remarks)


@router.post("/afes/{afe_id}/lines/bulk/validate", response_model=BulkValidationResult)
def validate_afe_lines(
    afe_id: UUID,
    payload: BulkAfeLinesCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> BulkValidationResult:
    return AfeLineService(session, current_user.id).validate_bulk(afe_id, payload.rows)


@router.post(
    "/afes/{afe_id}/lines/bulk/create",
    response_model=list[AfeLineRead],
    status_code=201,
)
def bulk_create_afe_lines(
    afe_id: UUID,
    payload: BulkAfeLinesCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> list[AfeLineRead]:
    return AfeLineService(session, current_user.id).bulk_create(afe_id, payload.rows)


@router.patch("/afe-lines/bulk/update", response_model=list[AfeLineRead])
def bulk_update_afe_lines(
    payload: BulkAfeLinesUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> list[AfeLineRead]:
    rows = [
        (
            row.id,
            AfeLineUpdate.model_validate(row.model_dump(exclude={"id"}, exclude_unset=True)),
        )
        for row in payload.rows
    ]
    return AfeLineService(session, current_user.id).bulk_update(rows)


@router.get("/afes/{afe_id}/lines", response_model=list[AfeLineRead])
def list_afe_lines(
    afe_id: UUID, current_user: CurrentUser, session: DbSession
) -> list[AfeLineRead]:
    return AfeLineService(session, current_user.id).list_items(afe_id)


@router.post("/afes/{afe_id}/lines", response_model=AfeLineRead, status_code=201)
def create_afe_line(
    afe_id: UUID,
    payload: AfeLineCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> AfeLineRead:
    return AfeLineService(session, current_user.id).create(afe_id, payload)


@router.patch("/afe-lines/{line_id}", response_model=AfeLineRead)
def update_afe_line(
    line_id: UUID,
    payload: AfeLineUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> AfeLineRead:
    return AfeLineService(session, current_user.id).update(line_id, payload)


@router.delete("/afe-lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_afe_line(line_id: UUID, current_user: CurrentUser, session: DbSession) -> Response:
    AfeLineService(session, current_user.id).deactivate(line_id)
    return Response(status_code=204)


@router.get("/afes/{afe_id}", response_model=AfeRead)
def get_afe(afe_id: UUID, current_user: CurrentUser, session: DbSession) -> AfeRead:
    return AfeService(session, current_user.id).get(afe_id)


@router.patch("/afes/{afe_id}", response_model=AfeRead)
def update_afe(
    afe_id: UUID,
    payload: AfeUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> AfeRead:
    return AfeService(session, current_user.id).update(afe_id, payload)


@router.delete("/afes/{afe_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_afe(afe_id: UUID, current_user: CurrentUser, session: DbSession) -> Response:
    AfeService(session, current_user.id).deactivate(afe_id)
    return Response(status_code=204)
