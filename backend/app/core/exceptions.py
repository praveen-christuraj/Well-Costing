"""Application exception hierarchy and normalized FastAPI handlers."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import Settings

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


class BusinessValidationError(AppException):
    """A well-formed request violates confirmed structural validation."""

    status_code = 422
    code = "business_validation_error"


class BusinessRulePendingError(AppException):
    """A requested calculation depends on rules not yet confirmed."""

    status_code = 422
    code = "business_rule_pending"


class WorkflowProfilePendingError(AppException):
    """A requested transition depends on an unpublished workflow policy."""

    status_code = 422
    code = "workflow_profile_pending"


class AfePolicyPendingError(AppException):
    """AFE issuance depends on eligibility and snapshot rules not yet confirmed."""

    status_code = 422
    code = "afe_policy_pending"


class CostStatePolicyPendingError(AppException):
    """Cost-state posting depends on definitions and allocation rules not yet confirmed."""

    status_code = 422
    code = "cost_state_policy_pending"


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
            message=exc.detail,
            details=None,
        )

    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
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
    app.add_exception_handler(Exception, unhandled_exception_handler)


ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]
