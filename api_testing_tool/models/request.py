"""
Request model for storing HTTP request configurations.

Supports all HTTP methods and flexible parameter configuration including
headers, query parameters, and various body types.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Request(Base):
    """
    SQLAlchemy model for HTTP request configurations.

    Attributes:
        id: Unique identifier for the request
        name: Human-readable name for the request
        method: HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
        url: Target URL, may contain variable placeholders like {{variable}}
        headers: Key-value pairs for HTTP headers
        query_params: Key-value pairs for URL query parameters
        body_type: Type of request body (json, form, raw, or None)
        body: Request body content
        folder_id: Optional reference to parent folder
        sort_order: Order within sibling requests
        created_at: Timestamp when the request was created
        updated_at: Timestamp when the request was last updated
    """
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    method: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(Text)
    headers: Mapped[dict] = mapped_column(JSON, default=dict)
    query_params: Mapped[dict] = mapped_column(JSON, default=dict)
    body_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    folder_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True
    )
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
