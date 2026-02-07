"""
Environment and Variable models for managing environment configurations.

Environments contain variables that can be substituted into requests,
allowing the same request templates to work across different environments
(e.g., development, staging, production).
"""

from datetime import datetime
from typing import List

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Environment(Base):
    """
    SQLAlchemy model for environments.
    
    An environment is a named configuration containing variables.
    Only one environment can be active at a time for variable substitution.
    Deleting an environment cascades to all its variables.
    
    Attributes:
        id: Unique identifier for the environment
        name: Human-readable name for the environment
        is_active: Whether this environment is currently active
        created_at: Timestamp when the environment was created
        updated_at: Timestamp when the environment was last updated
        variables: List of variables in this environment
    """
    __tablename__ = "environments"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str] = mapped_column(String(1000), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with cascade delete
    variables: Mapped[List["Variable"]] = relationship(
        "Variable",
        back_populates="environment",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class Variable(Base):
    """
    SQLAlchemy model for environment variables.
    
    Variables are key-value pairs that can be referenced in requests
    using the {{variable_name}} placeholder syntax.
    
    Attributes:
        id: Unique identifier for the variable
        environment_id: Reference to parent environment
        key: Variable name (used in {{key}} placeholders)
        value: Variable value to substitute
        environment: Parent environment relationship
    """
    __tablename__ = "variables"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    environment_id: Mapped[int] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(String(1000))
    
    # Relationship
    environment: Mapped["Environment"] = relationship(
        "Environment",
        back_populates="variables"
    )
