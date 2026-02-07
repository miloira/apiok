"""
History record API routes.

Provides endpoints for viewing and managing request execution history.
History records are automatically created when requests are executed.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.history import History
from ..schemas.history import HistoryResponse, HistoryListResponse


router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("", response_model=HistoryListResponse)
def list_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get history records list ordered by execution time (descending).
    
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        db: Database session
        
    Returns:
        HistoryListResponse with items and total count
    """
    total = db.query(History).count()
    items = (
        db.query(History)
        .order_by(History.executed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return HistoryListResponse(items=items, total=total)


@router.get("/{history_id}", response_model=HistoryResponse)
def get_history(history_id: int, db: Session = Depends(get_db)):
    """
    Get a single history record by ID.
    
    Args:
        history_id: The unique identifier of the history record
        db: Database session
        
    Returns:
        The history record
        
    Raises:
        HTTPException: 404 if history record not found
    """
    db_history = db.query(History).filter(History.id == history_id).first()
    if db_history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"History record with id {history_id} not found"
        )
    return db_history


@router.delete("/{history_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(history_id: int, db: Session = Depends(get_db)):
    """
    Delete a single history record by ID.
    
    Args:
        history_id: The unique identifier of the history record to delete
        db: Database session
        
    Raises:
        HTTPException: 404 if history record not found
    """
    db_history = db.query(History).filter(History.id == history_id).first()
    if db_history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"History record with id {history_id} not found"
        )
    
    db.delete(db_history)
    db.commit()
    return None


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_all_history(db: Session = Depends(get_db)):
    """
    Clear all history records.
    
    Args:
        db: Database session
    """
    db.query(History).delete()
    db.commit()
    return None
