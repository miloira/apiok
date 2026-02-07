"""
Folder management API routes.

Provides CRUD operations for folders to organize requests.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from ..database import get_db
from ..models.collection import Folder
from ..models.request import Request
from ..schemas.collection import (
    FolderCreate,
    FolderUpdate,
    FolderResponse,
    FolderWithChildren,
)
from ..services.folder_tree import (
    build_folder_tree,
    detect_circular_reference,
    get_folder_depth,
    get_subtree_depth,
    MAX_NESTING_DEPTH,
)


router = APIRouter(prefix="/api", tags=["folders"])


class ReorderFoldersRequest(BaseModel):
    """Schema for reordering folders."""
    folder_ids: list[int]


@router.post("/folders/reorder", status_code=status.HTTP_200_OK)
def reorder_folders(reorder_data: ReorderFoldersRequest, db: Session = Depends(get_db)):
    """Reorder folders by updating their sort_order."""
    for index, folder_id in enumerate(reorder_data.folder_ids):
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if folder:
            folder.sort_order = index
    db.commit()
    return {"message": "Folders reordered successfully"}


@router.get("/folders/tree", response_model=list[FolderWithChildren])
def get_folder_tree(db: Session = Depends(get_db)):
    """
    Get the full folder tree with nested folders and requests.

    Returns root-level folders with recursively nested children and requests.
    Also returns standalone requests (not in any folder) separately.
    """
    all_folders = db.query(Folder).all()
    all_requests = db.query(Request).filter(Request.folder_id.isnot(None)).all()
    tree = build_folder_tree(all_folders, all_requests)
    return tree


@router.get("/folders/standalone-requests")
def get_standalone_requests(db: Session = Depends(get_db)):
    """Get requests not in any folder."""
    reqs = db.query(Request).filter(Request.folder_id.is_(None)).order_by(Request.sort_order, Request.id).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "method": r.method,
            "url": r.url,
            "headers": r.headers,
            "query_params": r.query_params,
            "body_type": r.body_type,
            "body": r.body,
            "folder_id": r.folder_id,
            "sort_order": r.sort_order,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in reqs
    ]


# Folder CRUD endpoints

@router.post("/folders", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    folder_data: FolderCreate,
    db: Session = Depends(get_db)
):
    """Create a new folder."""
    if folder_data.parent_folder_id is not None:
        parent_folder = db.query(Folder).filter(
            Folder.id == folder_data.parent_folder_id
        ).first()
        if parent_folder is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent folder with id {folder_data.parent_folder_id} not found"
            )

        parent_depth = get_folder_depth(folder_data.parent_folder_id, db)
        if parent_depth + 1 > MAX_NESTING_DEPTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum nesting depth of {MAX_NESTING_DEPTH} exceeded"
            )

    max_sort_order = db.query(func.max(Folder.sort_order)).filter(
        Folder.parent_folder_id == folder_data.parent_folder_id,
    ).scalar()
    new_sort_order = (max_sort_order + 1) if max_sort_order is not None else 0

    db_folder = Folder(
        name=folder_data.name,
        parent_folder_id=folder_data.parent_folder_id,
        sort_order=new_sort_order,
    )
    db.add(db_folder)
    db.commit()
    db.refresh(db_folder)
    return db_folder


@router.put("/folders/{folder_id}", response_model=FolderResponse)
def update_folder(
    folder_id: int,
    folder_data: FolderUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing folder."""
    db_folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if db_folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder with id {folder_id} not found"
        )

    update_data = folder_data.model_dump(exclude_unset=True)

    if "parent_folder_id" in update_data:
        new_parent_id = update_data["parent_folder_id"]

        if new_parent_id == folder_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A folder cannot be its own parent"
            )

        if new_parent_id is not None:
            parent_folder = db.query(Folder).filter(
                Folder.id == new_parent_id,
            ).first()
            if parent_folder is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent folder with id {new_parent_id} not found"
                )

            if detect_circular_reference(folder_id, new_parent_id, db):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Moving this folder would create a circular reference"
                )

            target_depth = get_folder_depth(new_parent_id, db) + 1
            subtree_depth = get_subtree_depth(folder_id, db)
            if target_depth + subtree_depth - 1 > MAX_NESTING_DEPTH:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Maximum nesting depth of {MAX_NESTING_DEPTH} exceeded"
                )

    for field, value in update_data.items():
        setattr(db_folder, field, value)

    db.commit()
    db.refresh(db_folder)
    return db_folder


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(folder_id: int, db: Session = Depends(get_db)):
    """Delete a folder by ID. Cascades to all sub-folders and requests."""
    db_folder = db.query(Folder).filter(Folder.id == folder_id).first()
    if db_folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder with id {folder_id} not found"
        )

    db.delete(db_folder)
    db.commit()
    return None
