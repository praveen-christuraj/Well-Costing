"""Authentication routes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import CurrentUser
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Issue a bearer token for valid credentials."""

    return AuthService(UserRepository(session), settings).login(
        email=str(payload.email), password=payload.password
    )


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> UserRead:
    """Return the authenticated user's safe profile."""

    return UserRead.model_validate(current_user)
