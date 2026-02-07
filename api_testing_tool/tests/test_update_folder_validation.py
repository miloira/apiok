"""
Unit tests for update_folder endpoint validation.

Tests cover circular reference detection, nesting depth validation,
and folder move operations via the PUT /api/folders/{id} endpoint.

Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 5.2, 5.3
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api_testing_tool.main import app
from api_testing_tool.database import Base, get_db
from api_testing_tool.services.folder_tree import MAX_NESTING_DEPTH


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_update_folder_validation.db"
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


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    """Create a test client with a fresh database for each test."""
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        Base.metadata.drop_all(bind=test_engine)
        app.dependency_overrides.clear()


def _create_collection(client, name="Test Collection"):
    """Helper to create a collection via API."""
    response = client.post("/api/collections", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _create_folder(client, collection_id, name="Folder", parent_folder_id=None):
    """Helper to create a folder via API."""
    data = {"name": name}
    if parent_folder_id is not None:
        data["parent_folder_id"] = parent_folder_id
    response = client.post(f"/api/collections/{collection_id}/folders", json=data)
    assert response.status_code == 201
    return response.json()


class TestUpdateFolderNotFound:
    """Tests for updating a non-existent folder."""

    def test_update_nonexistent_folder_returns_404(self, client):
        """Updating a folder that doesn't exist returns 404."""
        response = client.put("/api/folders/99999", json={"name": "New Name"})
        assert response.status_code == 404
        assert "Folder with id 99999 not found" in response.json()["detail"]


class TestUpdateFolderSelfReference:
    """Tests for self-reference detection (Requirement 3.2)."""

    def test_self_reference_returns_400(self, client):
        """Setting a folder as its own parent returns 400."""
        coll = _create_collection(client)
        folder = _create_folder(client, coll["id"], "Folder A")

        response = client.put(f"/api/folders/{folder['id']}", json={
            "parent_folder_id": folder["id"]
        })
        assert response.status_code == 400
        assert response.json()["detail"] == "A folder cannot be its own parent"


class TestUpdateFolderCircularReference:
    """Tests for circular reference detection (Requirements 3.1, 3.3)."""

    def test_move_parent_under_child_returns_400(self, client):
        """Moving a parent folder under its child creates a circular reference."""
        coll = _create_collection(client)
        parent = _create_folder(client, coll["id"], "Parent")
        child = _create_folder(client, coll["id"], "Child", parent["id"])

        response = client.put(f"/api/folders/{parent['id']}", json={
            "parent_folder_id": child["id"]
        })
        assert response.status_code == 400
        assert response.json()["detail"] == "Moving this folder would create a circular reference"

    def test_move_grandparent_under_grandchild_returns_400(self, client):
        """Moving a grandparent under its grandchild creates a circular reference."""
        coll = _create_collection(client)
        gp = _create_folder(client, coll["id"], "Grandparent")
        parent = _create_folder(client, coll["id"], "Parent", gp["id"])
        child = _create_folder(client, coll["id"], "Child", parent["id"])

        response = client.put(f"/api/folders/{gp['id']}", json={
            "parent_folder_id": child["id"]
        })
        assert response.status_code == 400
        assert response.json()["detail"] == "Moving this folder would create a circular reference"

    def test_move_to_sibling_is_allowed(self, client):
        """Moving a folder under its sibling is not circular and should succeed."""
        coll = _create_collection(client)
        root = _create_folder(client, coll["id"], "Root")
        sibling_a = _create_folder(client, coll["id"], "Sibling A", root["id"])
        sibling_b = _create_folder(client, coll["id"], "Sibling B", root["id"])

        response = client.put(f"/api/folders/{sibling_a['id']}", json={
            "parent_folder_id": sibling_b["id"]
        })
        assert response.status_code == 200
        assert response.json()["parent_folder_id"] == sibling_b["id"]


class TestUpdateFolderDepthValidation:
    """Tests for nesting depth validation (Requirements 5.2, 5.3)."""

    def test_move_exceeds_max_depth_returns_400(self, client):
        """Moving a folder with subtree that would exceed max depth returns 400."""
        coll = _create_collection(client)
        # Build a chain of depth 4: L1 -> L2 -> L3 -> L4
        l1 = _create_folder(client, coll["id"], "L1")
        l2 = _create_folder(client, coll["id"], "L2", l1["id"])
        l3 = _create_folder(client, coll["id"], "L3", l2["id"])
        l4 = _create_folder(client, coll["id"], "L4", l3["id"])

        # Create another chain: A1 -> A2
        a1 = _create_folder(client, coll["id"], "A1")
        a2 = _create_folder(client, coll["id"], "A2", a1["id"])

        # Moving L1 (subtree depth=4) under A2 (depth=2) would make total = 3 + 4 - 1 = 6 > 5
        response = client.put(f"/api/folders/{l1['id']}", json={
            "parent_folder_id": a2["id"]
        })
        assert response.status_code == 400
        assert response.json()["detail"] == f"Maximum nesting depth of {MAX_NESTING_DEPTH} exceeded"

    def test_move_at_exact_max_depth_succeeds(self, client):
        """Moving a folder that results in exactly max depth should succeed."""
        coll = _create_collection(client)
        # Build a chain of depth 3: L1 -> L2 -> L3
        l1 = _create_folder(client, coll["id"], "L1")
        l2 = _create_folder(client, coll["id"], "L2", l1["id"])
        l3 = _create_folder(client, coll["id"], "L3", l2["id"])

        # Create target: A1 (depth=1)
        a1 = _create_folder(client, coll["id"], "A1")

        # Moving L1 (subtree depth=3) under A1 (depth=1) -> target_depth=2, total = 2 + 3 - 1 = 4 <= 5
        response = client.put(f"/api/folders/{l1['id']}", json={
            "parent_folder_id": a1["id"]
        })
        assert response.status_code == 200
        assert response.json()["parent_folder_id"] == a1["id"]

    def test_move_leaf_folder_deep_succeeds(self, client):
        """Moving a leaf folder (subtree depth=1) to depth 5 should succeed."""
        coll = _create_collection(client)
        # Build chain: L1 -> L2 -> L3 -> L4 (depth 4)
        l1 = _create_folder(client, coll["id"], "L1")
        l2 = _create_folder(client, coll["id"], "L2", l1["id"])
        l3 = _create_folder(client, coll["id"], "L3", l2["id"])
        l4 = _create_folder(client, coll["id"], "L4", l3["id"])

        # Create a standalone leaf folder
        leaf = _create_folder(client, coll["id"], "Leaf")

        # Moving leaf (subtree depth=1) under L4 (depth=4) -> target_depth=5, total = 5 + 1 - 1 = 5 <= 5
        response = client.put(f"/api/folders/{leaf['id']}", json={
            "parent_folder_id": l4["id"]
        })
        assert response.status_code == 200
        assert response.json()["parent_folder_id"] == l4["id"]

    def test_move_leaf_folder_beyond_max_depth_returns_400(self, client):
        """Moving a leaf folder to depth 6 should fail."""
        coll = _create_collection(client)
        # Build chain of depth 5: L1 -> L2 -> L3 -> L4 -> L5
        l1 = _create_folder(client, coll["id"], "L1")
        l2 = _create_folder(client, coll["id"], "L2", l1["id"])
        l3 = _create_folder(client, coll["id"], "L3", l2["id"])
        l4 = _create_folder(client, coll["id"], "L4", l3["id"])
        l5 = _create_folder(client, coll["id"], "L5", l4["id"])

        # Create a standalone leaf folder
        leaf = _create_folder(client, coll["id"], "Leaf")

        # Moving leaf (subtree depth=1) under L5 (depth=5) -> target_depth=6, total = 6 + 1 - 1 = 6 > 5
        response = client.put(f"/api/folders/{leaf['id']}", json={
            "parent_folder_id": l5["id"]
        })
        assert response.status_code == 400
        assert response.json()["detail"] == f"Maximum nesting depth of {MAX_NESTING_DEPTH} exceeded"


class TestUpdateFolderMoveToRoot:
    """Tests for moving folders to root level (Requirements 4.2)."""

    def test_move_to_root_succeeds(self, client):
        """Setting parent_folder_id to null moves folder to root level."""
        coll = _create_collection(client)
        parent = _create_folder(client, coll["id"], "Parent")
        child = _create_folder(client, coll["id"], "Child", parent["id"])

        response = client.put(f"/api/folders/{child['id']}", json={
            "parent_folder_id": None
        })
        assert response.status_code == 200
        assert response.json()["parent_folder_id"] is None

    def test_move_deep_subtree_to_root_succeeds(self, client):
        """Moving a folder with deep subtree to root always succeeds for depth."""
        coll = _create_collection(client)
        # Build: Root -> L1 -> L2 -> L3 -> L4
        root = _create_folder(client, coll["id"], "Root")
        l1 = _create_folder(client, coll["id"], "L1", root["id"])
        l2 = _create_folder(client, coll["id"], "L2", l1["id"])
        l3 = _create_folder(client, coll["id"], "L3", l2["id"])
        l4 = _create_folder(client, coll["id"], "L4", l3["id"])

        # Move L1 (which has subtree depth 4) to root - should succeed since root depth=1
        response = client.put(f"/api/folders/{l1['id']}", json={
            "parent_folder_id": None
        })
        assert response.status_code == 200
        assert response.json()["parent_folder_id"] is None


class TestUpdateFolderParentNotFound:
    """Tests for non-existent parent folder."""

    def test_move_to_nonexistent_parent_returns_404(self, client):
        """Moving a folder to a non-existent parent returns 404."""
        coll = _create_collection(client)
        folder = _create_folder(client, coll["id"], "Folder")

        response = client.put(f"/api/folders/{folder['id']}", json={
            "parent_folder_id": 99999
        })
        assert response.status_code == 404
        assert "not found in collection" in response.json()["detail"]


class TestUpdateFolderSubtreePreservation:
    """Tests for subtree preservation after move (Requirements 4.1, 4.3)."""

    def test_children_follow_moved_folder(self, client):
        """When a folder is moved, its children remain attached to it."""
        coll = _create_collection(client)
        parent = _create_folder(client, coll["id"], "Parent")
        child = _create_folder(client, coll["id"], "Child", parent["id"])
        grandchild = _create_folder(client, coll["id"], "Grandchild", child["id"])

        # Create a new target
        target = _create_folder(client, coll["id"], "Target")

        # Move child (with grandchild) under target
        response = client.put(f"/api/folders/{child['id']}", json={
            "parent_folder_id": target["id"]
        })
        assert response.status_code == 200

        # Verify the tree structure via get_collection
        coll_response = client.get(f"/api/collections/{coll['id']}")
        assert coll_response.status_code == 200
        data = coll_response.json()

        # Find the target folder in the tree
        target_folder = next(f for f in data["folders"] if f["id"] == target["id"])
        # Child should be under target
        assert len(target_folder["children"]) == 1
        assert target_folder["children"][0]["id"] == child["id"]
        # Grandchild should be under child
        assert len(target_folder["children"][0]["children"]) == 1
        assert target_folder["children"][0]["children"][0]["id"] == grandchild["id"]

    def test_name_update_without_parent_change(self, client):
        """Updating only the name should not trigger parent validation."""
        coll = _create_collection(client)
        folder = _create_folder(client, coll["id"], "Original Name")

        response = client.put(f"/api/folders/{folder['id']}", json={
            "name": "Updated Name"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"
