"""
Unit tests for the folder tree service.

Tests cover:
- build_folder_tree: building recursive tree from flat lists
- get_folder_depth: computing folder depth in tree
- get_subtree_depth: computing max subtree depth
- detect_circular_reference: detecting circular references
- MAX_NESTING_DEPTH constant
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api_testing_tool.database import Base
from api_testing_tool.models.collection import Collection, Folder
from api_testing_tool.models.request import Request
from api_testing_tool.services.folder_tree import (
    MAX_NESTING_DEPTH,
    build_folder_tree,
    detect_circular_reference,
    get_folder_depth,
    get_subtree_depth,
)


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_folder_tree.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


def _create_collection(db, name="Test Collection") -> Collection:
    """Helper to create a collection in the database."""
    collection = Collection(name=name)
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


def _create_folder(db, collection_id, name="Folder", parent_folder_id=None, sort_order=0) -> Folder:
    """Helper to create a folder in the database."""
    folder = Folder(
        name=name,
        collection_id=collection_id,
        parent_folder_id=parent_folder_id,
        sort_order=sort_order,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def _create_request(db, name="Request", collection_id=None, folder_id=None) -> Request:
    """Helper to create a request in the database."""
    req = Request(
        name=name,
        method="GET",
        url="https://example.com",
        collection_id=collection_id,
        folder_id=folder_id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


# ============== MAX_NESTING_DEPTH Tests ==============


class TestMaxNestingDepth:
    def test_max_nesting_depth_is_five(self):
        assert MAX_NESTING_DEPTH == 5


# ============== build_folder_tree Tests ==============


class TestBuildFolderTree:
    def test_empty_folders_and_requests(self):
        """Empty inputs should return an empty tree."""
        result = build_folder_tree([], [])
        assert result == []

    def test_single_root_folder_no_requests(self, db):
        """A single root folder with no children or requests."""
        coll = _create_collection(db)
        folder = _create_folder(db, coll.id, "Root Folder")

        result = build_folder_tree([folder], [])
        assert len(result) == 1
        assert result[0]["id"] == folder.id
        assert result[0]["name"] == "Root Folder"
        assert result[0]["parent_folder_id"] is None
        assert result[0]["children"] == []
        assert result[0]["requests"] == []

    def test_single_root_folder_with_requests(self, db):
        """A root folder containing requests."""
        coll = _create_collection(db)
        folder = _create_folder(db, coll.id, "Root")
        req1 = _create_request(db, "Req1", coll.id, folder.id)
        req2 = _create_request(db, "Req2", coll.id, folder.id)

        result = build_folder_tree([folder], [req1, req2])
        assert len(result) == 1
        assert len(result[0]["requests"]) == 2
        req_names = {r["name"] for r in result[0]["requests"]}
        assert req_names == {"Req1", "Req2"}

    def test_nested_two_levels(self, db):
        """Parent folder with one child folder."""
        coll = _create_collection(db)
        parent = _create_folder(db, coll.id, "Parent")
        child = _create_folder(db, coll.id, "Child", parent.id)

        result = build_folder_tree([parent, child], [])
        assert len(result) == 1
        assert result[0]["name"] == "Parent"
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["name"] == "Child"
        assert result[0]["children"][0]["children"] == []

    def test_nested_three_levels(self, db):
        """Three levels of nesting: grandparent -> parent -> child."""
        coll = _create_collection(db)
        gp = _create_folder(db, coll.id, "Grandparent")
        p = _create_folder(db, coll.id, "Parent", gp.id)
        c = _create_folder(db, coll.id, "Child", p.id)

        result = build_folder_tree([gp, p, c], [])
        assert len(result) == 1
        assert result[0]["name"] == "Grandparent"
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["name"] == "Parent"
        assert len(result[0]["children"][0]["children"]) == 1
        assert result[0]["children"][0]["children"][0]["name"] == "Child"

    def test_multiple_root_folders(self, db):
        """Multiple root-level folders."""
        coll = _create_collection(db)
        f1 = _create_folder(db, coll.id, "Root1")
        f2 = _create_folder(db, coll.id, "Root2")

        result = build_folder_tree([f1, f2], [])
        assert len(result) == 2
        names = {r["name"] for r in result}
        assert names == {"Root1", "Root2"}

    def test_requests_distributed_across_folders(self, db):
        """Requests are correctly assigned to their respective folders."""
        coll = _create_collection(db)
        f1 = _create_folder(db, coll.id, "Folder1")
        f2 = _create_folder(db, coll.id, "Folder2", f1.id)
        req1 = _create_request(db, "Req1", coll.id, f1.id)
        req2 = _create_request(db, "Req2", coll.id, f2.id)

        result = build_folder_tree([f1, f2], [req1, req2])
        # Root folder has req1
        assert len(result[0]["requests"]) == 1
        assert result[0]["requests"][0]["name"] == "Req1"
        # Child folder has req2
        assert len(result[0]["children"][0]["requests"]) == 1
        assert result[0]["children"][0]["requests"][0]["name"] == "Req2"

    def test_requests_without_folder_are_excluded(self, db):
        """Requests with folder_id=None are not included in any folder's requests."""
        coll = _create_collection(db)
        folder = _create_folder(db, coll.id, "Folder")
        orphan_req = _create_request(db, "Orphan", coll.id, None)

        result = build_folder_tree([folder], [orphan_req])
        assert len(result) == 1
        assert result[0]["requests"] == []

    def test_root_folders_sorted_by_sort_order(self, db):
        """Root folders should be sorted by sort_order ascending."""
        coll = _create_collection(db)
        f1 = _create_folder(db, coll.id, "C-Folder", sort_order=2)
        f2 = _create_folder(db, coll.id, "A-Folder", sort_order=0)
        f3 = _create_folder(db, coll.id, "B-Folder", sort_order=1)

        result = build_folder_tree([f1, f2, f3], [])
        assert len(result) == 3
        assert result[0]["name"] == "A-Folder"
        assert result[1]["name"] == "B-Folder"
        assert result[2]["name"] == "C-Folder"

    def test_child_folders_sorted_by_sort_order(self, db):
        """Child folders within a parent should be sorted by sort_order ascending."""
        coll = _create_collection(db)
        parent = _create_folder(db, coll.id, "Parent")
        c1 = _create_folder(db, coll.id, "Third", parent.id, sort_order=2)
        c2 = _create_folder(db, coll.id, "First", parent.id, sort_order=0)
        c3 = _create_folder(db, coll.id, "Second", parent.id, sort_order=1)

        result = build_folder_tree([parent, c1, c2, c3], [])
        assert len(result) == 1
        children = result[0]["children"]
        assert len(children) == 3
        assert children[0]["name"] == "First"
        assert children[1]["name"] == "Second"
        assert children[2]["name"] == "Third"

    def test_sort_order_tiebreak_by_id(self, db):
        """When sort_order is equal, folders should be sorted by id."""
        coll = _create_collection(db)
        # All have same sort_order=0, so should be sorted by id
        f1 = _create_folder(db, coll.id, "Folder-A", sort_order=0)
        f2 = _create_folder(db, coll.id, "Folder-B", sort_order=0)
        f3 = _create_folder(db, coll.id, "Folder-C", sort_order=0)

        result = build_folder_tree([f3, f1, f2], [])
        assert len(result) == 3
        # Should be sorted by id (f1.id < f2.id < f3.id)
        assert result[0]["id"] == f1.id
        assert result[1]["id"] == f2.id
        assert result[2]["id"] == f3.id

    def test_sort_order_included_in_output(self, db):
        """The sort_order field should be included in the folder dict output."""
        coll = _create_collection(db)
        folder = _create_folder(db, coll.id, "Folder", sort_order=5)

        result = build_folder_tree([folder], [])
        assert len(result) == 1
        assert result[0]["sort_order"] == 5

    def test_nested_sort_order_at_multiple_levels(self, db):
        """Sort order should be applied independently at each nesting level."""
        coll = _create_collection(db)
        # Root level: r2 (sort_order=0) before r1 (sort_order=1)
        r1 = _create_folder(db, coll.id, "Root-B", sort_order=1)
        r2 = _create_folder(db, coll.id, "Root-A", sort_order=0)
        # Children of r1: c2 (sort_order=0) before c1 (sort_order=1)
        c1 = _create_folder(db, coll.id, "Child-B", r1.id, sort_order=1)
        c2 = _create_folder(db, coll.id, "Child-A", r1.id, sort_order=0)

        result = build_folder_tree([r1, r2, c1, c2], [])
        assert len(result) == 2
        assert result[0]["name"] == "Root-A"
        assert result[1]["name"] == "Root-B"
        children = result[1]["children"]
        assert len(children) == 2
        assert children[0]["name"] == "Child-A"
        assert children[1]["name"] == "Child-B"


# ============== get_folder_depth Tests ==============


class TestGetFolderDepth:
    def test_root_folder_depth_is_one(self, db):
        """A root-level folder has depth 1."""
        coll = _create_collection(db)
        folder = _create_folder(db, coll.id, "Root")
        assert get_folder_depth(folder.id, db) == 1

    def test_child_folder_depth_is_two(self, db):
        """A direct child of a root folder has depth 2."""
        coll = _create_collection(db)
        root = _create_folder(db, coll.id, "Root")
        child = _create_folder(db, coll.id, "Child", root.id)
        assert get_folder_depth(child.id, db) == 2

    def test_deeply_nested_folder_depth(self, db):
        """Depth is correctly computed for deeply nested folders."""
        coll = _create_collection(db)
        f1 = _create_folder(db, coll.id, "L1")
        f2 = _create_folder(db, coll.id, "L2", f1.id)
        f3 = _create_folder(db, coll.id, "L3", f2.id)
        f4 = _create_folder(db, coll.id, "L4", f3.id)
        f5 = _create_folder(db, coll.id, "L5", f4.id)

        assert get_folder_depth(f1.id, db) == 1
        assert get_folder_depth(f2.id, db) == 2
        assert get_folder_depth(f3.id, db) == 3
        assert get_folder_depth(f4.id, db) == 4
        assert get_folder_depth(f5.id, db) == 5

    def test_nonexistent_folder_raises_error(self, db):
        """Requesting depth of a non-existent folder raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            get_folder_depth(9999, db)


# ============== get_subtree_depth Tests ==============


class TestGetSubtreeDepth:
    def test_leaf_folder_subtree_depth_is_one(self, db):
        """A leaf folder (no children) has subtree depth 1."""
        coll = _create_collection(db)
        folder = _create_folder(db, coll.id, "Leaf")
        assert get_subtree_depth(folder.id, db) == 1

    def test_folder_with_one_child(self, db):
        """A folder with one child has subtree depth 2."""
        coll = _create_collection(db)
        parent = _create_folder(db, coll.id, "Parent")
        _create_folder(db, coll.id, "Child", parent.id)
        assert get_subtree_depth(parent.id, db) == 2

    def test_folder_with_deep_chain(self, db):
        """Subtree depth follows the longest chain."""
        coll = _create_collection(db)
        f1 = _create_folder(db, coll.id, "L1")
        f2 = _create_folder(db, coll.id, "L2", f1.id)
        f3 = _create_folder(db, coll.id, "L3", f2.id)
        assert get_subtree_depth(f1.id, db) == 3

    def test_folder_with_wide_children(self, db):
        """Subtree depth is max of all branches."""
        coll = _create_collection(db)
        root = _create_folder(db, coll.id, "Root")
        # Branch 1: depth 1
        _create_folder(db, coll.id, "B1", root.id)
        # Branch 2: depth 2
        b2 = _create_folder(db, coll.id, "B2", root.id)
        _create_folder(db, coll.id, "B2-child", b2.id)

        assert get_subtree_depth(root.id, db) == 3  # root -> B2 -> B2-child


# ============== detect_circular_reference Tests ==============


class TestDetectCircularReference:
    def test_self_reference(self, db):
        """Moving a folder to be its own parent is circular."""
        coll = _create_collection(db)
        folder = _create_folder(db, coll.id, "Folder")
        assert detect_circular_reference(folder.id, folder.id, db) is True

    def test_move_to_child_is_circular(self, db):
        """Moving a parent under its own child creates a cycle."""
        coll = _create_collection(db)
        parent = _create_folder(db, coll.id, "Parent")
        child = _create_folder(db, coll.id, "Child", parent.id)
        assert detect_circular_reference(parent.id, child.id, db) is True

    def test_move_to_grandchild_is_circular(self, db):
        """Moving a folder under its grandchild creates a cycle."""
        coll = _create_collection(db)
        gp = _create_folder(db, coll.id, "Grandparent")
        p = _create_folder(db, coll.id, "Parent", gp.id)
        c = _create_folder(db, coll.id, "Child", p.id)
        assert detect_circular_reference(gp.id, c.id, db) is True

    def test_move_to_sibling_is_not_circular(self, db):
        """Moving a folder under a sibling is not circular."""
        coll = _create_collection(db)
        root = _create_folder(db, coll.id, "Root")
        sibling1 = _create_folder(db, coll.id, "Sibling1", root.id)
        sibling2 = _create_folder(db, coll.id, "Sibling2", root.id)
        assert detect_circular_reference(sibling1.id, sibling2.id, db) is False

    def test_move_to_unrelated_folder_is_not_circular(self, db):
        """Moving a folder under an unrelated folder is not circular."""
        coll = _create_collection(db)
        f1 = _create_folder(db, coll.id, "Folder1")
        f2 = _create_folder(db, coll.id, "Folder2")
        assert detect_circular_reference(f1.id, f2.id, db) is False

    def test_move_child_to_another_root_is_not_circular(self, db):
        """Moving a child folder to another root folder is not circular."""
        coll = _create_collection(db)
        root1 = _create_folder(db, coll.id, "Root1")
        child = _create_folder(db, coll.id, "Child", root1.id)
        root2 = _create_folder(db, coll.id, "Root2")
        assert detect_circular_reference(child.id, root2.id, db) is False

    def test_nonexistent_parent_returns_false(self, db):
        """If the new parent doesn't exist, no circular reference."""
        coll = _create_collection(db)
        folder = _create_folder(db, coll.id, "Folder")
        assert detect_circular_reference(folder.id, 9999, db) is False
