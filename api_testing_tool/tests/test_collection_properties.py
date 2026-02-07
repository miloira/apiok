"""
Property-based tests for Collection management operations.

Tests Properties 6-7 from the design document.
**Validates: Requirements 3.4, 3.5**
"""

import pytest
from hypothesis import given, strategies as st, settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from api_testing_tool.main import app
from api_testing_tool.database import Base, get_db


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_collection_properties.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)


@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_test_client():
    """Context manager to create a test client with fresh database."""
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        Base.metadata.drop_all(bind=test_engine)
        app.dependency_overrides.clear()


# Strategies for generating valid collection/folder/request data
collection_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-"),
    min_size=1,
    max_size=50
)

folder_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-"),
    min_size=1,
    max_size=50
)

request_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-"),
    min_size=1,
    max_size=50
)

http_method_strategy = st.sampled_from(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])


class TestProperty6CollectionCascadeDelete:
    """
    Property 6: 集合级联删除
    
    *对于任意*包含文件夹和请求的集合，删除该集合后，
    其下的所有文件夹和请求都应该被删除。
    
    **Validates: Requirements 3.4**
    """

    @given(
        collection_name=collection_name_strategy,
        folder_names=st.lists(folder_name_strategy, min_size=1, max_size=2),
        request_names=st.lists(request_name_strategy, min_size=1, max_size=2)
    )
    @settings(max_examples=20, deadline=None)
    def test_deleting_collection_cascades_to_folders_and_requests(
        self, collection_name: str, folder_names: list[str], request_names: list[str]
    ):
        """
        Property: Deleting a collection removes all its folders and requests.
        """
        with get_test_client() as client:
            # Create a collection
            collection_response = client.post("/api/collections", json={
                "name": collection_name
            })
            assert collection_response.status_code == 201
            collection_id = collection_response.json()["id"]
            
            # Create folders in the collection
            folder_ids = []
            for folder_name in folder_names:
                folder_response = client.post(
                    f"/api/collections/{collection_id}/folders",
                    json={"name": folder_name}
                )
                assert folder_response.status_code == 201
                folder_ids.append(folder_response.json()["id"])
            
            # Create requests directly in the collection
            direct_request_ids = []
            for request_name in request_names:
                request_response = client.post("/api/requests", json={
                    "name": request_name,
                    "method": "GET",
                    "url": "https://api.example.com/test",
                    "collection_id": collection_id
                })
                assert request_response.status_code == 201
                direct_request_ids.append(request_response.json()["id"])
            
            # Create requests in folders
            folder_request_ids = []
            for folder_id in folder_ids:
                request_response = client.post("/api/requests", json={
                    "name": f"Request in folder {folder_id}",
                    "method": "POST",
                    "url": "https://api.example.com/folder-test",
                    "collection_id": collection_id,
                    "folder_id": folder_id
                })
                assert request_response.status_code == 201
                folder_request_ids.append(request_response.json()["id"])
            
            # Delete the collection
            delete_response = client.delete(f"/api/collections/{collection_id}")
            assert delete_response.status_code == 204
            
            # Verify collection is deleted
            get_collection_response = client.get(f"/api/collections/{collection_id}")
            assert get_collection_response.status_code == 404
            
            # Verify all direct requests are deleted
            for request_id in direct_request_ids:
                get_request_response = client.get(f"/api/requests/{request_id}")
                assert get_request_response.status_code == 404
            
            # Verify all folder requests are deleted
            for request_id in folder_request_ids:
                get_request_response = client.get(f"/api/requests/{request_id}")
                assert get_request_response.status_code == 404


class TestProperty7CollectionNestedStructureIntegrity:
    """
    Property 7: 集合嵌套结构完整性
    
    *对于任意*集合及其包含的文件夹和请求，
    获取集合详情应该返回完整的嵌套结构。
    
    **Validates: Requirements 3.5**
    """

    @given(
        collection_name=collection_name_strategy,
        folder_names=st.lists(folder_name_strategy, min_size=0, max_size=2),
        direct_request_count=st.integers(min_value=0, max_value=2),
        folder_request_count=st.integers(min_value=0, max_value=2)
    )
    @settings(max_examples=20, deadline=None)
    def test_get_collection_returns_complete_nested_structure(
        self, collection_name: str, folder_names: list[str],
        direct_request_count: int, folder_request_count: int
    ):
        """
        Property: Getting a collection returns all nested folders and requests.
        """
        with get_test_client() as client:
            # Create a collection
            collection_response = client.post("/api/collections", json={
                "name": collection_name,
                "description": "Test collection"
            })
            assert collection_response.status_code == 201
            collection_id = collection_response.json()["id"]
            
            # Create folders in the collection
            created_folders = []
            for folder_name in folder_names:
                folder_response = client.post(
                    f"/api/collections/{collection_id}/folders",
                    json={"name": folder_name}
                )
                assert folder_response.status_code == 201
                created_folders.append(folder_response.json())
            
            # Create direct requests (not in any folder)
            created_direct_requests = []
            for i in range(direct_request_count):
                request_response = client.post("/api/requests", json={
                    "name": f"Direct Request {i}",
                    "method": "GET",
                    "url": f"https://api.example.com/direct/{i}",
                    "collection_id": collection_id
                })
                assert request_response.status_code == 201
                created_direct_requests.append(request_response.json())
            
            # Create requests in each folder
            folder_requests_map = {}  # folder_id -> list of request ids
            for folder in created_folders:
                folder_id = folder["id"]
                folder_requests_map[folder_id] = []
                for i in range(folder_request_count):
                    request_response = client.post("/api/requests", json={
                        "name": f"Folder {folder_id} Request {i}",
                        "method": "POST",
                        "url": f"https://api.example.com/folder/{folder_id}/{i}",
                        "collection_id": collection_id,
                        "folder_id": folder_id
                    })
                    assert request_response.status_code == 201
                    folder_requests_map[folder_id].append(request_response.json()["id"])
            
            # Get the collection with nested structure
            get_response = client.get(f"/api/collections/{collection_id}")
            assert get_response.status_code == 200
            collection_data = get_response.json()
            
            # Verify collection basic data
            assert collection_data["name"] == collection_name
            assert collection_data["id"] == collection_id
            
            # Verify all folders are present
            assert len(collection_data["folders"]) == len(folder_names)
            returned_folder_ids = {f["id"] for f in collection_data["folders"]}
            expected_folder_ids = {f["id"] for f in created_folders}
            assert returned_folder_ids == expected_folder_ids
            
            # Verify all direct requests are present
            assert len(collection_data["requests"]) == direct_request_count
            returned_direct_request_ids = {r["id"] for r in collection_data["requests"]}
            expected_direct_request_ids = {r["id"] for r in created_direct_requests}
            assert returned_direct_request_ids == expected_direct_request_ids
            
            # Verify each folder contains its requests
            for folder_data in collection_data["folders"]:
                folder_id = folder_data["id"]
                expected_request_ids = set(folder_requests_map.get(folder_id, []))
                returned_request_ids = {r["id"] for r in folder_data.get("requests", [])}
                assert returned_request_ids == expected_request_ids
