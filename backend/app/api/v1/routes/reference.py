"""Routes for the configurable dropdown registry.

Reading is open to any authenticated user — every screen resolves its pickers
here. Writing is restricted to the system administrator, because a binding
decides where the whole application reads its reference data from.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser, SystemAdministrator
from app.db.session import get_db
from app.schemas.reference import (
    DropdownBindingWrite,
    DropdownRegistryRead,
    DropdownSlotRead,
    ReferenceOptionsRead,
)
from app.services.reference_bindings import ReferenceBindingService

router = APIRouter(prefix="/reference", tags=["reference data"])


@router.get("/registry", response_model=DropdownRegistryRead)
def get_registry(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    module: str | None = None,
) -> DropdownRegistryRead:
    """Every dropdown slot, the sources available, and what is bound today."""

    return ReferenceBindingService(session, current_user.id).registry(module)


@router.get("/registry/usage", response_model=dict[str, int])
def get_registry_usage(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> dict[str, int]:
    """Row count behind each source, so an empty binding is obvious."""

    return ReferenceBindingService(session, current_user.id).usage_counts()


@router.get("/slots/{slot_code}", response_model=DropdownSlotRead)
def get_slot_binding(
    slot_code: str,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> DropdownSlotRead:
    return ReferenceBindingService(session, current_user.id).get_slot_read(slot_code)


@router.put("/slots/{slot_code}", response_model=DropdownSlotRead)
def set_slot_binding(
    slot_code: str,
    payload: DropdownBindingWrite,
    administrator: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> DropdownSlotRead:
    """Point a dropdown at another registered source. Super administrators only."""

    return ReferenceBindingService(session, administrator.id).set_binding(slot_code, payload)


@router.delete("/slots/{slot_code}", response_model=DropdownSlotRead)
def reset_slot_binding(
    slot_code: str,
    administrator: SystemAdministrator,
    session: Annotated[Session, Depends(get_db)],
) -> DropdownSlotRead:
    """Restore the source declared in code for this dropdown."""

    return ReferenceBindingService(session, administrator.id).reset_binding(slot_code)


@router.get("/options/{slot_code}", response_model=ReferenceOptionsRead)
def get_slot_options(
    slot_code: str,
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    parent_id: UUID | None = None,
    well_id: UUID | None = None,
    search: str | None = None,
    include_inactive: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> ReferenceOptionsRead:
    """Resolved options for one dropdown slot."""

    return ReferenceBindingService(session, current_user.id).resolve(
        slot_code,
        parent_id=parent_id,
        well_id=well_id,
        search=search,
        limit=limit,
        include_inactive=include_inactive,
    )
