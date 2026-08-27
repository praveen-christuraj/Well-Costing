"""Authentication routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services.audit import log_audit
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
) -> TokenResponse:
    """Issue a bearer token for valid credentials and record the sign-in."""

    users = UserRepository(session)
    token = AuthService(users, settings).login(email=str(payload.email), password=payload.password)
    user = users.get_by_email(str(payload.email).strip().lower())
    log_audit(
        session,
        user=user,
        action="LOGIN",
        module="Authentication",
        entity_id=str(user.id) if user is not None else None,
        entity_code=user.email if user is not None else None,
        details=f"Successful sign-in for {str(payload.email).strip().lower()}",
        request=request,
    )
    return token


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> UserRead:
    """Return the authenticated user's safe profile."""

    return UserRead.model_validate(current_user)
