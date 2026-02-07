"""
Tests for the folder reorder endpoint POST /api/folders/reorder.

Tests cover:
- Reordering folders updates sort_order based on list index
- Skipping non-existent folder IDs
- Empty folder_ids list
- Single folder reorder
- Reordering a subset of folders

**Validates: Requirements 2.1, 2.2**
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api_testing_tool.main import app
from api_testing_tool.database import Base, get_db
from api_testing_tool.models.collection import Folder


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_reorder_folders.db"
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


@pytest.fixture(scope="function")
def db():
    """Provide a direct database session for verifying sort_order values."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


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


def _get_folder_sort_order(db, folder_id):
    """Helper to query a folder's sort_order directly from the database."""
    db.expire_all()
    folder = db.query(Folder).filter(Folder.id == folder_id).first()
    return folder.sort_order if folder else None


class TestReorderFoldersEndpoint:
    """Unit tests for POST /api/folders/reorder endpoint."""

    def test_reorder_reverses_folder_order(self, client, db):
        """Reordering with reversed IDs should reverse the sort_order values."""
        coll = _create_collection(client)
        f1 = _create_folder(client, coll["id"], "Folder A")
        f2 = _create_folder(client, coll["id"], "Folder B")
        f3 = _create_folder(client, coll["id"], "Folder C")

        # Original order: f1=0, f2=1, f3=2
        # Reverse the order
        response = client.post("/api/folders/reorder", json={
            "folder_ids": [f3["id"], f2["id"], f1["id"]]
        })
        assert response.status_code == 200
        assert response.json() == {"message": "Folders reordered successfully"}

        # Verify sort_order values directly from database
        assert _get_folder_sort_order(db, f3["id"]) == 0
        assert _get_folder_sort_order(db, f2["id"]) == 1
        assert _get_folder_sort_order(db, f1["id"]) == 2

    def test_reorder_with_empty_list(self, client, db):
        """Reordering with an empty list should succeed without changes."""
        coll = _create_collection(client)
        f1 = _create_folder(client, coll["id"], "Folder A")

        response = client.post("/api/folders/reorder", json={
            "folder_ids": []
        })
        assert response.status_code == 200

        # Verify original sort_order is unchanged
        assert _get_folder_sort_order(db, f1["id"]) == 0

    def test_reorder_single_folder(self, client, db):
        """Reordering a single folder should set its sort_order to 0."""
        coll = _create_collection(client)
        f1 = _create_folder(client, coll["id"], "Folder A")
        f2 = _create_folder(client, coll["id"], "Folder B")

        # Reorder only f2
        response = client.post("/api/folders/reorder", json={
            "folder_ids": [f2["id"]]
        })
        assert response.status_code == 200

        assert _get_folder_sort_order(db, f2["id"]) == 0
        # f1 should retain its original sort_order
        assert _get_folder_sort_order(db, f1["id"]) == 0

    def test_reorder_skips_nonexistent_ids(self, client, db):
        """Non-existent folder IDs should be skipped without error.

        **Validates: Requirements 2.2**
        """
        coll = _create_collection(client)
        f1 = _create_folder(client, coll["id"], "Folder A")
        f2 = _create_folder(client, coll["id"], "Folder B")

        # Include a non-existent ID (99999) in the list
        response = client.post("/api/folders/reorder", json={
            "folder_ids": [f2["id"], 99999, f1["id"]]
        })
        assert response.status_code == 200

        # f2 is at index 0, 99999 is skipped, f1 is at index 2
        assert _get_folder_sort_order(db, f2["id"]) == 0
        assert _get_folder_sort_order(db, f1["id"]) == 2

    def test_reorder_all_nonexistent_ids(self, client, db):
        """Reordering with all non-existent IDs should succeed without changes."""
        coll = _create_collection(client)
        f1 = _create_folder(client, coll["id"], "Folder A")

        response = client.post("/api/folders/reorder", json={
            "folder_ids": [99999, 88888]
        })
        assert response.status_code == 200

        # Original folder should be unchanged
        assert _get_folder_sort_order(db, f1["id"]) == 0

    def test_reorder_updates_sort_order_by_index(self, client, db):
        """Each folder's sort_order should equal its index in the submitted list.

        **Validates: Requirements 2.1**
        """
        coll = _create_collection(client)
        folders = []
        for i in range(5):
            f = _create_folder(client, coll["id"], f"Folder {i}")
            folders.append(f)

        # Shuffle the order: 4, 2, 0, 3, 1
        new_order = [folders[4]["id"], folders[2]["id"], folders[0]["id"],
                     folders[3]["id"], folders[1]["id"]]
        response = client.post("/api/folders/reorder", json={
            "folder_ids": new_order
        })
        assert response.status_code == 200

        for expected_index, folder_id in enumerate(new_order):
            assert _get_folder_sort_order(db, folder_id) == expected_index

    def test_reorder_preserves_other_folder_attributes(self, client, db):
        """Reordering should only change sort_order, not other attributes."""
        coll = _create_collection(client)
        f1 = _create_folder(client, coll["id"], "Folder Alpha")
        f2 = _create_folder(client, coll["id"], "Folder Beta")

        response = client.post("/api/folders/reorder", json={
            "folder_ids": [f2["id"], f1["id"]]
        })
        assert response.status_code == 200

        db.expire_all()
        folder1 = db.query(Folder).filter(Folder.id == f1["id"]).first()
        folder2 = db.query(Folder).filter(Folder.id == f2["id"]).first()
        assert folder1.name == "Folder Alpha"
        assert folder2.name == "Folder Beta"
        assert folder1.collection_id == coll["id"]
        assert folder2.collection_id == coll["id"]
