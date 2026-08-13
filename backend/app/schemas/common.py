"""Common response schema building blocks."""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Stable error content returned by global exception handlers."""

    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    """Stable top-level API error envelope."""

    error: ErrorDetail
