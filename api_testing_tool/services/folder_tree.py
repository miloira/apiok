"""
Folder tree service for building recursive folder structures and validation.

Provides functions for:
- Building recursive folder trees from flat lists
- Computing folder depth in the tree
- Computing subtree depth
- Detecting circular references
- Enforcing maximum nesting depth
"""

from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from ..models.collection import Folder
from ..models.request import Request

# Maximum allowed nesting depth for folders (root level = depth 1)
MAX_NESTING_DEPTH = 5


def build_folder_tree(
    folders: list[Folder],
    requests: list[Request],
) -> list[dict]:
    """
    Build a recursive folder tree from flat lists of folders and requests.

    Args:
        folders: Flat list of Folder ORM objects from the database.
        requests: Flat list of Request ORM objects from the database.

    Returns:
        A list of root-level folder dictionaries with nested children and requests.
    """
    children_map: dict[Optional[int], list[Folder]] = defaultdict(list)
    for folder in folders:
        children_map[folder.parent_folder_id].append(folder)

    for parent_id in children_map:
        children_map[parent_id].sort(key=lambda f: (f.sort_order, f.id))

    request_map: dict[Optional[int], list[Request]] = defaultdict(list)
    for request in requests:
        if request.folder_id is not None:
            request_map[request.folder_id].append(request)

    def _build_subtree(parent_id: Optional[int]) -> list[dict]:
        result = []
        for folder in children_map.get(parent_id, []):
            folder_dict = {
                "id": folder.id,
                "name": folder.name,
                "parent_folder_id": folder.parent_folder_id,
                "sort_order": folder.sort_order,
                "created_at": folder.created_at,
                "updated_at": folder.updated_at,
                "children": _build_subtree(folder.id),
                "requests": [
                    {
                        "id": req.id,
                        "name": req.name,
                        "method": req.method,
                        "url": req.url,
                        "headers": req.headers,
                        "query_params": req.query_params,
                        "body_type": req.body_type,
                        "body": req.body,
                        "folder_id": req.folder_id,
                        "sort_order": req.sort_order,
                        "created_at": req.created_at,
                        "updated_at": req.updated_at,
                    }
                    for req in request_map.get(folder.id, [])
                ],
            }
            result.append(folder_dict)
        return result

    return _build_subtree(None)


def get_folder_depth(folder_id: int, db: Session) -> int:
    """
    Compute the depth of a folder in the tree (1-based).
    """
    depth = 0
    current_id: Optional[int] = folder_id

    while current_id is not None:
        folder = db.query(Folder).filter(Folder.id == current_id).first()
        if folder is None:
            raise ValueError(f"Folder with id {current_id} not found")
        depth += 1
        current_id = folder.parent_folder_id

    return depth


def get_subtree_depth(folder_id: int, db: Session) -> int:
    """
    Compute the maximum depth of a folder's subtree.
    """
    children = db.query(Folder).filter(Folder.parent_folder_id == folder_id).all()

    if not children:
        return 1

    max_child_depth = max(get_subtree_depth(child.id, db) for child in children)
    return 1 + max_child_depth


def detect_circular_reference(
    folder_id: int,
    new_parent_id: int,
    db: Session,
) -> bool:
    """
    Detect if moving a folder under a new parent would create a circular reference.
    """
    if new_parent_id == folder_id:
        return True

    current_id: Optional[int] = new_parent_id

    while current_id is not None:
        folder = db.query(Folder).filter(Folder.id == current_id).first()
        if folder is None:
            return False
        if folder.parent_folder_id == folder_id:
            return True
        current_id = folder.parent_folder_id

    return False
