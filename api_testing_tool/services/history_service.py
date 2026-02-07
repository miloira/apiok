"""
History service for saving request execution records.

This service handles the creation of history records when requests are executed.
"""

from sqlalchemy.orm import Session

from ..models.history import History
from ..schemas.execute import ExecuteRequest, ExecuteResponse


def save_history(
    db: Session,
    request: ExecuteRequest,
    response: ExecuteResponse,
    request_id: int | None = None
) -> History:
    """
    Save a request execution to history.
    
    Args:
        db: Database session
        request: The executed request configuration
        response: The response received
        request_id: Optional ID of the saved request (if executing a saved request)
        
    Returns:
        The created history record
    """
    history = History(
        request_id=request_id,
        method=request.method,
        url=request.url,
        request_headers=request.headers,
        request_body=request.body,
        status_code=response.status_code,
        status_text=response.status_text,
        response_headers=response.headers,
        response_body=response.body,
        response_time_ms=response.response_time_ms,
        response_size=response.response_size
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history
