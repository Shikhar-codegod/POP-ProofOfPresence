"""Standard error response schemas adhering to the POP API contract."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Structured error payload."""

    code: str = Field(..., description="Machine-readable error constant (e.g. UNAUTHORIZED, BAD_REQUEST)")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: Optional[Any] = Field(default=None, description="Optional granular diagnostics or field errors")


class ErrorResponse(BaseModel):
    """Enveloped error response model."""

    error: ErrorDetail
