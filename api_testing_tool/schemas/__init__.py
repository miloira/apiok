"""
Pydantic schemas package.

Exports all schemas for API request/response validation.
"""

from .request import (
    HttpMethod,
    BodyType,
    RequestBase,
    RequestCreate,
    RequestUpdate,
    RequestResponse,
)

from .collection import (
    FolderBase,
    FolderCreate,
    FolderUpdate,
    FolderResponse,
    FolderWithRequests,
    FolderWithChildren,
)

from .environment import (
    VariableBase,
    VariableCreate,
    VariableUpdate,
    VariableResponse,
    EnvironmentBase,
    EnvironmentCreate,
    EnvironmentUpdate,
    EnvironmentResponse,
    EnvironmentWithVariables,
)

from .history import (
    HistoryResponse,
    HistoryListResponse,
)

from .execute import (
    ExecuteRequest,
    ExecuteOptions,
    ExecuteResponse,
    ExecuteErrorResponse,
)

__all__ = [
    # Request schemas
    "HttpMethod",
    "BodyType",
    "RequestBase",
    "RequestCreate",
    "RequestUpdate",
    "RequestResponse",
    # Folder schemas
    "FolderBase",
    "FolderCreate",
    "FolderUpdate",
    "FolderResponse",
    "FolderWithRequests",
    "FolderWithChildren",
    # Environment schemas
    "VariableBase",
    "VariableCreate",
    "VariableUpdate",
    "VariableResponse",
    "EnvironmentBase",
    "EnvironmentCreate",
    "EnvironmentUpdate",
    "EnvironmentResponse",
    "EnvironmentWithVariables",
    # History schemas
    "HistoryResponse",
    "HistoryListResponse",
    # Execute schemas
    "ExecuteRequest",
    "ExecuteOptions",
    "ExecuteResponse",
    "ExecuteErrorResponse",
]
