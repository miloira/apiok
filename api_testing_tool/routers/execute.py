"""
Request execution API routes.

Provides endpoints for executing HTTP requests, both saved and temporary.
Integrates variable substitution and HTTP execution services.
Automatically saves execution history on successful requests.
"""

from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.request import Request
from ..schemas.execute import ExecuteRequest, ExecuteOptions, ExecuteResponse, ExecuteErrorResponse
from ..services.http_executor import execute_request
from ..services.history_service import save_history


router = APIRouter(prefix="/api/execute", tags=["execute"])


@router.post(
    "/{request_id}",
    response_model=Union[ExecuteResponse, ExecuteErrorResponse],
    responses={
        200: {"model": ExecuteResponse, "description": "Successful execution"},
        502: {"model": ExecuteErrorResponse, "description": "Network error"},
        504: {"model": ExecuteErrorResponse, "description": "Request timeout"},
    }
)
async def execute_saved_request(
    request_id: int,
    options: ExecuteOptions | None = None,
    db: Session = Depends(get_db)
):
    """
    Execute a saved HTTP request by ID.
    
    Fetches the request configuration from the database, applies variable
    substitution using the specified or active environment, and executes
    the HTTP request.
    
    Args:
        request_id: The unique identifier of the saved request
        options: Optional execution options (environment_id)
        db: Database session
        
    Returns:
        ExecuteResponse on success with status, headers, body, and timing info
        ExecuteErrorResponse on failure with error details
        
    Raises:
        HTTPException: 404 if request not found
    """
    # Fetch the saved request
    db_request = db.query(Request).filter(Request.id == request_id).first()
    if db_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Request with id {request_id} not found"
        )
    
    # Convert saved request to ExecuteRequest
    execute_req = ExecuteRequest(
        method=db_request.method,
        url=db_request.url,
        headers=db_request.headers or {},
        query_params=db_request.query_params or {},
        body_type=db_request.body_type,
        body=db_request.body
    )
    
    # Get environment_id from options if provided
    environment_id = options.environment_id if options else None
    
    # Execute the request
    result = await execute_request(
        request=execute_req,
        db=db,
        environment_id=environment_id
    )
    
    # Return appropriate response based on result type
    if isinstance(result, ExecuteErrorResponse):
        # Map error types to HTTP status codes
        if result.error_type == "timeout":
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"error": result.error, "error_type": result.error_type, "details": result.details}
            )
        elif result.error_type == "network_error":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": result.error, "error_type": result.error_type, "details": result.details}
            )
        elif result.error_type == "invalid_url":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": result.error, "error_type": result.error_type, "details": result.details}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": result.error, "error_type": result.error_type, "details": result.details}
            )
    
    # Save to history on successful execution
    save_history(db=db, request=execute_req, response=result, request_id=request_id)
    
    return result


@router.post(
    "",
    response_model=Union[ExecuteResponse, ExecuteErrorResponse],
    responses={
        200: {"model": ExecuteResponse, "description": "Successful execution"},
        502: {"model": ExecuteErrorResponse, "description": "Network error"},
        504: {"model": ExecuteErrorResponse, "description": "Request timeout"},
    }
)
async def execute_temporary_request(
    request: ExecuteRequest,
    environment_id: int | None = None,
    db: Session = Depends(get_db)
):
    """
    Execute a temporary (unsaved) HTTP request.
    
    Executes the provided request configuration directly without saving it.
    Variable substitution is applied using the specified or active environment.
    
    Args:
        request: The request configuration to execute
        environment_id: Optional environment ID for variable substitution
        db: Database session
        
    Returns:
        ExecuteResponse on success with status, headers, body, and timing info
        ExecuteErrorResponse on failure with error details
    """
    # Execute the request
    result = await execute_request(
        request=request,
        db=db,
        environment_id=environment_id
    )
    
    # Return appropriate response based on result type
    if isinstance(result, ExecuteErrorResponse):
        # Map error types to HTTP status codes
        if result.error_type == "timeout":
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"error": result.error, "error_type": result.error_type, "details": result.details}
            )
        elif result.error_type == "network_error":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error": result.error, "error_type": result.error_type, "details": result.details}
            )
        elif result.error_type == "invalid_url":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": result.error, "error_type": result.error_type, "details": result.details}
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": result.error, "error_type": result.error_type, "details": result.details}
            )
    
    # Save to history on successful execution (no request_id for temporary requests)
    save_history(db=db, request=request, response=result, request_id=None)
    
    return result
