"""
Folder model for organizing requests.

Folders provide hierarchical organization for requests.
Folders can be nested inside other folders.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .request import Request


class Folder(Base):
    """
    SQLAlchemy model for folders.

    Folders provide hierarchical organization for requests.
    Folders can be nested inside other folders.
    Deleting a folder cascades to all contained sub-folders and requests.

    Attributes:
        id: Unique identifier for the folder
        parent_folder_id: Optional reference to parent folder (for nesting)
        name: Human-readable name for the folder
        sort_order: Order within sibling folders
        created_at: Timestamp when the folder was created
        updated_at: Timestamp when the folder was last updated
        requests: List of requests in this folder
    """
    __tablename__ = "folders"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_folder_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("folders.id", ondelete="CASCADE"),
        nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    children: Mapped[List["Folder"]] = relationship(
        "Folder",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    requests: Mapped[List["Request"]] = relationship(
        "Request",
        backref="folder",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
