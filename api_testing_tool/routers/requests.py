"""
Request management API routes.

Provides CRUD operations for HTTP request configurations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models.request import Request
from ..schemas.request import RequestCreate, RequestUpdate, RequestResponse


router = APIRouter(prefix="/api/requests", tags=["requests"])


class ReorderRequest(BaseModel):
    """Schema for reordering requests."""
    request_ids: list[int]


@router.post("/reorder", status_code=status.HTTP_200_OK)
def reorder_requests(reorder_data: ReorderRequest, db: Session = Depends(get_db)):
    """
    Reorder requests by updating their sort_order.
    
    Args:
        reorder_data: List of request IDs in the desired order
        db: Database session
    """
    for index, request_id in enumerate(reorder_data.request_ids):
        db_request = db.query(Request).filter(Request.id == request_id).first()
        if db_request:
            db_request.sort_order = index
    db.commit()
    return {"message": "Requests reordered successfully"}


@router.post("", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
def create_request(request_data: RequestCreate, db: Session = Depends(get_db)):
    """
    Create a new HTTP request configuration.
    
    Args:
        request_data: Request configuration data
        db: Database session
        
    Returns:
        The created request with assigned ID and timestamps
    """
    db_request = Request(
        name=request_data.name,
        method=request_data.method,
        url=request_data.url,
        headers=request_data.headers,
        query_params=request_data.query_params,
        body_type=request_data.body_type,
        body=request_data.body,
        folder_id=request_data.folder_id,
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request


@router.get("", response_model=list[RequestResponse])
def list_requests(db: Session = Depends(get_db)):
    """
    List all saved HTTP requests.
    
    Args:
        db: Database session
        
    Returns:
        List of all request configurations
    """
    return db.query(Request).order_by(Request.sort_order, Request.id).all()



@router.get("/{request_id}", response_model=RequestResponse)
def get_request(request_id: int, db: Session = Depends(get_db)):
    """
    Get a single request by ID.
    
    Args:
        request_id: The unique identifier of the request
        db: Database session
        
    Returns:
        The request configuration
        
    Raises:
        HTTPException: 404 if request not found
    """
    db_request = db.query(Request).filter(Request.id == request_id).first()
    if db_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request with id {request_id} not found"
        )
    return db_request


@router.put("/{request_id}", response_model=RequestResponse)
def update_request(
    request_id: int, 
    request_data: RequestUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update an existing request.
    
    Args:
        request_id: The unique identifier of the request to update
        request_data: Fields to update (only provided fields are updated)
        db: Database session
        
    Returns:
        The updated request configuration
        
    Raises:
        HTTPException: 404 if request not found
    """
    db_request = db.query(Request).filter(Request.id == request_id).first()
    if db_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request with id {request_id} not found"
        )
    
    # Update only provided fields
    update_data = request_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_request, field, value)
    
    db.commit()
    db.refresh(db_request)
    return db_request


@router.delete("/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_request(request_id: int, db: Session = Depends(get_db)):
    """
    Delete a request by ID.
    
    Args:
        request_id: The unique identifier of the request to delete
        db: Database session
        
    Raises:
        HTTPException: 404 if request not found
    """
    db_request = db.query(Request).filter(Request.id == request_id).first()
    if db_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request with id {request_id} not found"
        )
    
    db.delete(db_request)
    db.commit()
    return None
