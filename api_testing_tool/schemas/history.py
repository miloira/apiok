"""
Pydantic schemas for request execution history.

Defines schemas for returning history records.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class HistoryResponse(BaseModel):
    """Schema for history record response with all fields."""
    id: int
    request_id: int | None
    method: str
    url: str
    request_headers: dict[str, str]
    request_body: str | None
    status_code: int
    status_text: str
    response_headers: dict[str, str]
    response_body: str | None
    response_time_ms: int
    response_size: int
    executed_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class HistoryListResponse(BaseModel):
    """Schema for paginated history list response."""
    items: list[HistoryResponse]
    total: int
