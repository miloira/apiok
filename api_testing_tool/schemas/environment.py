"""
Pydantic schemas for environments and variables.

Defines schemas for creating, updating, and returning environment/variable data.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# Variable schemas

class VariableBase(BaseModel):
    """Base schema with common variable fields."""
    key: str
    value: str


class VariableCreate(VariableBase):
    """Schema for creating a new variable."""
    pass


class VariableUpdate(BaseModel):
    """Schema for updating an existing variable. All fields are optional."""
    key: str | None = None
    value: str | None = None


class VariableResponse(VariableBase):
    """Schema for variable response with all fields."""
    id: int
    environment_id: int
    
    model_config = ConfigDict(from_attributes=True)


# Environment schemas

class EnvironmentBase(BaseModel):
    """Base schema with common environment fields."""
    name: str
    base_url: str = ""


class EnvironmentCreate(EnvironmentBase):
    """Schema for creating a new environment."""
    is_active: bool = False
    variables: list[VariableCreate] = []


class EnvironmentUpdate(BaseModel):
    """Schema for updating an existing environment. All fields are optional."""
    name: str | None = None
    base_url: str | None = None
    is_active: bool | None = None


class EnvironmentResponse(EnvironmentBase):
    """Schema for environment response with all fields."""
    id: int
    is_active: bool
    base_url: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class EnvironmentWithVariables(EnvironmentResponse):
    """Schema for environment response including all variables."""
    variables: list[VariableResponse] = []
