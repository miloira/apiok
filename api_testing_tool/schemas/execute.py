"""
Pydantic schemas for request execution.

Defines schemas for executing requests and returning execution results.
"""

from typing import Any, Literal

from pydantic import BaseModel

from .request import HttpMethod, BodyType


class ExecuteRequest(BaseModel):
    """Schema for executing a temporary (unsaved) request."""
    method: HttpMethod
    url: str
    headers: dict[str, str] = {}
    query_params: dict[str, str] = {}
    body_type: BodyType | None = None
    body: str | None = None


class ExecuteOptions(BaseModel):
    """Schema for execution options."""
    environment_id: int | None = None


class ExecuteResponse(BaseModel):
    """
    Schema for request execution response.
    
    Contains all response details including status, headers, body,
    timing information, and any warnings from variable substitution.
    """
    status_code: int
    status_text: str
    headers: dict[str, str]
    body: str | None
    body_json: Any | None = None
    response_time_ms: int
    response_size: int
    warnings: list[str] = []


class ExecuteErrorResponse(BaseModel):
    """Schema for execution error response."""
    error: str
    error_type: Literal["network_error", "timeout", "invalid_url", "unknown"]
    details: str | None = None
