"""Phase 11 cross-module framework assurance status route."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.db.session import get_db
from app.schemas.assurance import AssuranceStatus
from app.services.assurance import AssuranceService

router = APIRouter(prefix="/assurance", tags=["assurance"])


@router.get("/status", response_model=AssuranceStatus)
def assurance_status(
    current_user: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
) -> AssuranceStatus:
    del current_user
    return AssuranceService(session).status()
