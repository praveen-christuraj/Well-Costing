"""Application exception hierarchy and normalized FastAPI handlers."""

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, DBAPIError, IntegrityError

try:
    from fastapi.exceptions import ResponseValidationError
except ImportError:  # pragma: no cover - FastAPI < 0.100
    ResponseValidationError = None  # type: ignore[misc, assignment]

from app.core.config import Settings

# PostgreSQL and SQLite spell "the migration never ran" differently; both mean
# the database schema is behind the application code and every endpoint that
# touches the missing table/column will fail.
_MISSING_SCHEMA_PATTERNS = (
    re.compile(r'relation "[\w.]+" does not exist', re.IGNORECASE),
    re.compile(r"column [\w.\"]+ does not exist", re.IGNORECASE),
    re.compile(r"no such table", re.IGNORECASE),
    re.compile(r"no such column", re.IGNORECASE),
)

logger = logging.getLogger("app")


class AppException(Exception):
    """Base exception for expected application failures."""

    status_code = 400
    code = "application_error"

    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class AuthenticationError(AppException):
    """Authentication credentials are absent or invalid."""

    status_code = 401
    code = "authentication_failed"


class AuthServiceUnavailableError(AppException):
    """A configured external identity provider could not be reached."""

    status_code = 503
    code = "auth_service_unavailable"


class AuthorizationError(AppException):
    """The current actor lacks permission for an operation."""

    status_code = 403
    code = "authorization_failed"


class NotFoundError(AppException):
    """A requested resource does not exist."""

    status_code = 404
    code = "not_found"


class ConflictError(AppException):
    """A write conflicts with existing persisted state."""

    status_code = 409
    code = "conflict"


def _error_response(
    *, status_code: int, code: str, message: str, details: Any | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder({"error": {"code": code, "message": message, "details": details}}),
    )


def register_exception_handlers(app: FastAPI, settings: Settings) -> None:
    """Register global handlers with a stable error envelope."""

    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="validation_error",
            message="Request validation failed",
            details=exc.errors(),
        )

    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return _error_response(
            status_code=exc.status_code,
            code="http_error",
            message=str(exc.detail),
            details=None,
        )

    def _integrity_message(exc: IntegrityError) -> str:
        original = str(getattr(exc, "orig", exc)).lower()
        if "unique" in original or "duplicate" in original:
            return "A record with this code already exists"
        if "not null" in original or "not-null" in original or "null value" in original:
            return "A required field is missing"
        return "The data could not be saved because it conflicts with existing records"

    async def integrity_exception_handler(_request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Database integrity error", extra={"error": str(getattr(exc, "orig", exc))})
        return _error_response(
            status_code=409,
            code="conflict",
            message=_integrity_message(exc),
            details=str(getattr(exc, "orig", exc)) if settings.ENVIRONMENT == "development" else None,
        )

    async def data_exception_handler(_request: Request, exc: DataError) -> JSONResponse:
        logger.warning("Database data error", extra={"error": str(getattr(exc, "orig", exc))})
        return _error_response(
            status_code=400,
            code="validation_error",
            message="The submitted data is not valid for this field",
            details=str(getattr(exc, "orig", exc)) if settings.ENVIRONMENT == "development" else None,
        )

    async def response_validation_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Response validation failed")
        errors = getattr(exc, "errors", lambda: None)()
        return _error_response(
            status_code=500,
            code="internal_error",
            message="An unexpected error occurred",
            details=errors if settings.ENVIRONMENT == "development" else None,
        )

    def _is_schema_drift(exc: Exception) -> bool:
        """Whether a database error means missing tables/columns (pending migrations)."""
        if not isinstance(exc, DBAPIError):
            return False
        original = getattr(exc, "orig", None)
        return any(
            pattern.search(str(original) if original is not None else "")
            for pattern in _MISSING_SCHEMA_PATTERNS
        )

    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        original_error = str(getattr(exc, "orig", exc)) if isinstance(exc, DBAPIError) else None
        if _is_schema_drift(exc):
            logger.warning(
                "Database schema drift detected — the database is behind the application code",
                extra={"path": request.url.path, "method": request.method, "error": original_error},
            )
            return _error_response(
                status_code=503,
                code="database_schema_outdated",
                message=(
                    "The database schema is behind the application code. Apply the "
                    "pending migrations with `cd backend && python -m alembic upgrade "
                    "head` (the local dev servers do this automatically on startup) and "
                    "then reload the page."
                ),
                details=original_error,
            )
        logger.exception(
            "Unhandled application exception",
            extra={"path": request.url.path, "method": request.method},
        )
        details = repr(exc) if settings.ENVIRONMENT == "development" else None
        return _error_response(
            status_code=500,
            code="internal_error",
            message="An unexpected error occurred",
            details=details,
        )

    app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(IntegrityError, integrity_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DataError, data_exception_handler)  # type: ignore[arg-type]
    if ResponseValidationError is not None:
        app.add_exception_handler(ResponseValidationError, response_validation_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]
