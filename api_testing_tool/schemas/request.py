"""
Pydantic schemas for HTTP request configurations.

Defines schemas for creating, updating, and returning request data
with HTTP method validation.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


# HTTP methods supported by the system
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]

# Body types supported for requests
BodyType = Literal["json", "form", "raw"]


class RequestBase(BaseModel):
    """Base schema with common request fields."""
    name: str
    method: HttpMethod
    url: str
    headers: dict[str, str] = {}
    query_params: dict[str, str] = {}
    body_type: BodyType | None = None
    body: str | None = None


class RequestCreate(RequestBase):
    """Schema for creating a new request."""
    folder_id: int | None = None


class RequestUpdate(BaseModel):
    """Schema for updating an existing request. All fields are optional."""
    name: str | None = None
    method: HttpMethod | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    query_params: dict[str, str] | None = None
    body_type: BodyType | None = None
    body: str | None = None
    folder_id: int | None = None
    sort_order: int | None = None


class RequestResponse(RequestBase):
    """Schema for request response with all fields including system-generated ones."""
    id: int
    folder_id: int | None
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
