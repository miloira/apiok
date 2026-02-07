"""
Tests for create_folder endpoint auto-assigning sort_order.

Tests cover:
- First folder in a collection gets sort_order 0
- Subsequent folders get sort_order = max(sibling sort_order) + 1
- Folders in different parent folders get independent sort_order sequences
- Folders in different collections get independent sort_order sequences

**Validates: Requirements 1.2**
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from api_testing_tool.main import app
from api_testing_tool.database import Base, get_db


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_create_folder_sort_order.db"
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


class TestCreateFolderSortOrderAutoAssign:
    """Tests for auto-assigning sort_order when creating folders."""

    def test_first_folder_gets_sort_order_zero(self, client):
        """The first folder created in a collection should have sort_order 0."""
        coll = _create_collection(client)
        folder = _create_folder(client, coll["id"], "First Folder")
        assert folder["sort_order"] == 0

    def test_second_folder_gets_sort_order_one(self, client):
        """The second folder in the same collection should have sort_order 1."""
        coll = _create_collection(client)
        _create_folder(client, coll["id"], "First")
        second = _create_folder(client, coll["id"], "Second")
        assert second["sort_order"] == 1

    def test_sequential_folders_get_incrementing_sort_order(self, client):
        """Multiple folders created sequentially should get incrementing sort_order values."""
        coll = _create_collection(client)
        folders = []
        for i in range(5):
            f = _create_folder(client, coll["id"], f"Folder {i}")
            folders.append(f)

        for i, f in enumerate(folders):
            assert f["sort_order"] == i

    def test_child_folders_get_independent_sort_order(self, client):
        """Folders inside a parent folder should have their own sort_order sequence."""
        coll = _create_collection(client)
        parent = _create_folder(client, coll["id"], "Parent")
        # Parent is at root level with sort_order 0

        # Create children inside the parent
        child1 = _create_folder(client, coll["id"], "Child 1", parent["id"])
        child2 = _create_folder(client, coll["id"], "Child 2", parent["id"])

        assert child1["sort_order"] == 0
        assert child2["sort_order"] == 1

    def test_different_parents_have_independent_sort_orders(self, client):
        """Folders under different parents should have independent sort_order sequences."""
        coll = _create_collection(client)
        parent_a = _create_folder(client, coll["id"], "Parent A")
        parent_b = _create_folder(client, coll["id"], "Parent B")

        child_a1 = _create_folder(client, coll["id"], "Child A1", parent_a["id"])
        child_a2 = _create_folder(client, coll["id"], "Child A2", parent_a["id"])
        child_b1 = _create_folder(client, coll["id"], "Child B1", parent_b["id"])

        assert child_a1["sort_order"] == 0
        assert child_a2["sort_order"] == 1
        assert child_b1["sort_order"] == 0

    def test_different_collections_have_independent_sort_orders(self, client):
        """Folders in different collections should have independent sort_order sequences."""
        coll_a = _create_collection(client, "Collection A")
        coll_b = _create_collection(client, "Collection B")

        folder_a1 = _create_folder(client, coll_a["id"], "Folder A1")
        folder_a2 = _create_folder(client, coll_a["id"], "Folder A2")
        folder_b1 = _create_folder(client, coll_b["id"], "Folder B1")

        assert folder_a1["sort_order"] == 0
        assert folder_a2["sort_order"] == 1
        assert folder_b1["sort_order"] == 0

    def test_root_and_nested_sort_orders_are_independent(self, client):
        """Root-level folders and nested folders should have independent sort_order sequences."""
        coll = _create_collection(client)
        root1 = _create_folder(client, coll["id"], "Root 1")
        root2 = _create_folder(client, coll["id"], "Root 2")

        # Create a child under root1
        child = _create_folder(client, coll["id"], "Child", root1["id"])

        # Root folders: 0, 1
        assert root1["sort_order"] == 0
        assert root2["sort_order"] == 1
        # Child folder starts at 0 in its own scope
        assert child["sort_order"] == 0

        # Adding another root folder should continue from 2
        root3 = _create_folder(client, coll["id"], "Root 3")
        assert root3["sort_order"] == 2


class TestCreateFolderSortOrderProperty:
    """
    Property-based test for auto-assigning sort_order.

    **Feature: drag-sort-and-move, Property 1: 新建文件夹排序值自动分配**
    **Validates: Requirements 1.2**
    """

    @given(n_existing=st.integers(min_value=0, max_value=10))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_new_folder_sort_order_greater_than_all_siblings(self, client, n_existing):
        """
        For any collection with N existing sibling folders, a newly created folder's
        sort_order should be greater than all existing sibling folders' sort_order values.

        **Validates: Requirements 1.2**
        """
        # Create a fresh collection for this test iteration
        coll = _create_collection(client, f"Collection-{n_existing}")

        # Create N existing folders
        existing_folders = []
        for i in range(n_existing):
            f = _create_folder(client, coll["id"], f"Existing {i}")
            existing_folders.append(f)

        # Create the new folder
        new_folder = _create_folder(client, coll["id"], "New Folder")

        # The new folder's sort_order should be greater than all existing siblings
        for existing in existing_folders:
            assert new_folder["sort_order"] > existing["sort_order"], (
                f"New folder sort_order ({new_folder['sort_order']}) should be > "
                f"existing folder sort_order ({existing['sort_order']})"
            )

        # If there were no existing folders, sort_order should be 0
        if n_existing == 0:
            assert new_folder["sort_order"] == 0

    @given(n_existing=st.integers(min_value=0, max_value=8))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_new_nested_folder_sort_order_greater_than_siblings(self, client, n_existing):
        """
        For any parent folder with N existing child folders, a newly created child folder's
        sort_order should be greater than all existing child folders' sort_order values.

        **Validates: Requirements 1.2**
        """
        coll = _create_collection(client, f"Nested-{n_existing}")
        parent = _create_folder(client, coll["id"], "Parent")

        # Create N existing child folders
        existing_children = []
        for i in range(n_existing):
            f = _create_folder(client, coll["id"], f"Child {i}", parent["id"])
            existing_children.append(f)

        # Create the new child folder
        new_child = _create_folder(client, coll["id"], "New Child", parent["id"])

        # The new child's sort_order should be greater than all existing children
        for existing in existing_children:
            assert new_child["sort_order"] > existing["sort_order"], (
                f"New child sort_order ({new_child['sort_order']}) should be > "
                f"existing child sort_order ({existing['sort_order']})"
            )

        if n_existing == 0:
            assert new_child["sort_order"] == 0
