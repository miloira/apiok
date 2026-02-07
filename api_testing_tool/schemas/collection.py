"""
Pydantic schemas for folders.

Defines schemas for creating, updating, and returning folder data
with support for nested structure responses.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .request import RequestResponse


# Folder schemas

class FolderBase(BaseModel):
    """Base schema with common folder fields."""
    name: str


class FolderCreate(FolderBase):
    """Schema for creating a new folder."""
    parent_folder_id: int | None = None


class FolderUpdate(BaseModel):
    """Schema for updating an existing folder. All fields are optional."""
    name: str | None = None
    parent_folder_id: int | None = None


class FolderResponse(FolderBase):
    """Schema for folder response with all fields."""
    id: int
    parent_folder_id: int | None
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FolderWithRequests(FolderResponse):
    """Schema for folder response including nested requests."""
    requests: list[RequestResponse] = []


class FolderWithChildren(FolderResponse):
    """递归文件夹 schema，包含子文件夹和请求"""
    children: list["FolderWithChildren"] = []
    requests: list[RequestResponse] = []


FolderWithChildren.model_rebuild()
