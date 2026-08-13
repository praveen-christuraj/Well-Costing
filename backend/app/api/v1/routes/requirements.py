"""Phase 3 project, well, requirement, and bulk-item routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.master_data import BulkValidationResult, PageResponse
from app.schemas.requirements import (
    BulkProjectCreate,
    BulkProjectUpdate,
    BulkRequirementCreate,
    BulkRequirementItemsCreate,
    BulkRequirementItemsUpdate,
    BulkRequirementUpdate,
    BulkWellCreate,
    BulkWellUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    RequirementCreate,
    RequirementItemCreate,
    RequirementItemRead,
    RequirementItemUpdate,
    RequirementRead,
    RequirementUpdate,
    WellCreate,
    WellRead,
    WellUpdate,
)
from app.services.requirements import (
    ProjectService,
    RequirementItemService,
    RequirementService,
    WellService,
)

router = APIRouter(tags=["requirement intake"])
DbSession = Annotated[Session, Depends(get_db)]


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


@router.get("/requirements", response_model=PageResponse)
def list_requirements(
    current_user: CurrentUser,
    session: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    search: str | None = None,
    project_id: UUID | None = None,
    well_id: UUID | None = None,
    requirement_status: Annotated[str | None, Query(alias="status")] = None,
    is_active: bool | None = None,
) -> PageResponse:
    return RequirementService(session, current_user.id).list_page(
        page=page,
        page_size=page_size,
        search=search,
        project_id=project_id,
        well_id=well_id,
        status=requirement_status,
        is_active=is_active,
    )


@router.post("/requirements", response_model=RequirementRead, status_code=201)
def create_requirement(
    payload: RequirementCreate, current_user: CurrentUser, session: DbSession
) -> RequirementRead:
    return RequirementService(session, current_user.id).create(payload)


@router.post("/requirements/bulk/create", response_model=list[RequirementRead], status_code=201)
def bulk_create_requirements(
    payload: BulkRequirementCreate, current_user: CurrentUser, session: DbSession
) -> list[RequirementRead]:
    return RequirementService(session, current_user.id).bulk_create(payload.rows)


@router.patch("/requirements/bulk/update", response_model=list[RequirementRead])
def bulk_update_requirements(
    payload: BulkRequirementUpdate, current_user: CurrentUser, session: DbSession
) -> list[RequirementRead]:
    rows = [
        (
            row.id,
            RequirementUpdate.model_validate(row.model_dump(exclude={"id"}, exclude_unset=True)),
        )
        for row in payload.rows
    ]
    return RequirementService(session, current_user.id).bulk_update(rows)


@router.post("/requirements/{requirement_id}/submit", response_model=RequirementRead)
def submit_requirement(
    requirement_id: UUID, current_user: CurrentUser, session: DbSession
) -> RequirementRead:
    return RequirementService(session, current_user.id).submit(requirement_id)


@router.post(
    "/requirements/{requirement_id}/items/bulk/validate", response_model=BulkValidationResult
)
def validate_requirement_items(
    requirement_id: UUID,
    payload: BulkRequirementItemsCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> BulkValidationResult:
    return RequirementItemService(session, current_user.id).validate_bulk(
        requirement_id, payload.rows
    )


@router.post(
    "/requirements/{requirement_id}/items/bulk/create",
    response_model=list[RequirementItemRead],
    status_code=201,
)
def bulk_create_requirement_items(
    requirement_id: UUID,
    payload: BulkRequirementItemsCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> list[RequirementItemRead]:
    return RequirementItemService(session, current_user.id).bulk_create(
        requirement_id, payload.rows
    )


@router.patch("/requirement-items/bulk/update", response_model=list[RequirementItemRead])
def bulk_update_requirement_items(
    payload: BulkRequirementItemsUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> list[RequirementItemRead]:
    rows = [
        (
            row.id,
            RequirementItemUpdate.model_validate(
                row.model_dump(exclude={"id"}, exclude_unset=True)
            ),
        )
        for row in payload.rows
    ]
    return RequirementItemService(session, current_user.id).bulk_update(rows)


@router.get("/requirements/{requirement_id}/items", response_model=list[RequirementItemRead])
def list_requirement_items(
    requirement_id: UUID, current_user: CurrentUser, session: DbSession
) -> list[RequirementItemRead]:
    return RequirementItemService(session, current_user.id).list_items(requirement_id)


@router.post(
    "/requirements/{requirement_id}/items", response_model=RequirementItemRead, status_code=201
)
def create_requirement_item(
    requirement_id: UUID,
    payload: RequirementItemCreate,
    current_user: CurrentUser,
    session: DbSession,
) -> RequirementItemRead:
    return RequirementItemService(session, current_user.id).create(requirement_id, payload)


@router.patch("/requirement-items/{item_id}", response_model=RequirementItemRead)
def update_requirement_item(
    item_id: UUID,
    payload: RequirementItemUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> RequirementItemRead:
    return RequirementItemService(session, current_user.id).update(item_id, payload)


@router.delete("/requirement-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_requirement_item(
    item_id: UUID, current_user: CurrentUser, session: DbSession
) -> Response:
    RequirementItemService(session, current_user.id).deactivate(item_id)
    return Response(status_code=204)


@router.get("/requirements/{requirement_id}", response_model=RequirementRead)
def get_requirement(
    requirement_id: UUID, current_user: CurrentUser, session: DbSession
) -> RequirementRead:
    return RequirementService(session, current_user.id).get(requirement_id)


@router.patch("/requirements/{requirement_id}", response_model=RequirementRead)
def update_requirement(
    requirement_id: UUID,
    payload: RequirementUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> RequirementRead:
    return RequirementService(session, current_user.id).update(requirement_id, payload)


@router.delete("/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_requirement(
    requirement_id: UUID, current_user: CurrentUser, session: DbSession
) -> Response:
    RequirementService(session, current_user.id).deactivate(requirement_id)
    return Response(status_code=204)
