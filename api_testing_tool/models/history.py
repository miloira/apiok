"""
History model for storing executed request records.

Each execution of a request creates a history entry containing
the full request details, response details, and timing information.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, JSON, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class History(Base):
    """
    SQLAlchemy model for request execution history.
    
    Stores complete details of each request execution including
    the request configuration, response data, and performance metrics.
    
    Attributes:
        id: Unique identifier for the history entry
        request_id: Optional reference to the original saved request
        method: HTTP method used
        url: Target URL (after variable substitution)
        request_headers: Headers sent with the request
        request_body: Body sent with the request
        status_code: HTTP response status code
        status_text: HTTP response status text
        response_headers: Headers received in the response
        response_body: Body received in the response
        response_time_ms: Request execution time in milliseconds
        response_size: Response body size in bytes
        executed_at: Timestamp when the request was executed
    """
    __tablename__ = "history"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("requests.id", ondelete="SET NULL"),
        nullable=True
    )
    method: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(Text)
    request_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    request_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer)
    status_text: Mapped[str] = mapped_column(String(50))
    response_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[int] = mapped_column(Integer)
    response_size: Mapped[int] = mapped_column(Integer)
    executed_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
