"""
Custom exception classes and error handling for the API Testing Tool.

Provides consistent error responses across all API endpoints.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError


class ErrorResponse(BaseModel):
    """Standard error response format."""
    detail: str
    error_code: str | None = None


class APIException(Exception):
    """Base exception for API errors."""
    
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str | None = None
    ):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(detail)


class ResourceNotFoundError(APIException):
    """Exception raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: Any):
        super().__init__(
            detail=f"{resource_type} with id {resource_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND"
        )


class ValidationError(APIException):
    """Exception raised when request validation fails."""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR"
        )


class BadRequestError(APIException):
    """Exception raised for invalid request data."""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="BAD_REQUEST"
        )


class NetworkError(APIException):
    """Exception raised when a network error occurs during request execution."""
    
    def __init__(self, detail: str):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="NETWORK_ERROR"
        )


class TimeoutError(APIException):
    """Exception raised when a request times out."""
    
    def __init__(self, detail: str = "Request timed out"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            error_code="TIMEOUT"
        )


class DatabaseError(APIException):
    """Exception raised when a database error occurs."""
    
    def __init__(self, detail: str = "Database error occurred"):
        super().__init__(
            detail=detail,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR"
        )


async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handler for custom API exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code}
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handler for Pydantic validation errors."""
    errors = exc.errors()
    # Format validation errors into a readable message
    error_messages = []
    for error in errors:
        loc = " -> ".join(str(l) for l in error["loc"])
        msg = error["msg"]
        error_messages.append(f"{loc}: {msg}")
    
    detail = "; ".join(error_messages) if error_messages else "Validation error"
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": detail, "error_code": "VALIDATION_ERROR"}
    )


async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    """Handler for SQLAlchemy database errors."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error occurred", "error_code": "DATABASE_ERROR"}
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unhandled exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "error_code": "INTERNAL_ERROR"}
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI application."""
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    # Note: Generic exception handler is optional and can be enabled for production
    # app.add_exception_handler(Exception, generic_exception_handler)
