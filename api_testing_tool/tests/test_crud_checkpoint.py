"""
Checkpoint tests for CRUD API operations.

This test module verifies that all CRUD operations for requests,
collections, folders, and environments are working correctly.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api_testing_tool.main import app
from api_testing_tool.database import Base, get_db


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_crud_checkpoint.db"
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)


# Enable foreign key support for SQLite in test database
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


@pytest.fixture(scope="function")
def client():
    """Create a test client with fresh database for each test."""
    # Create tables
    Base.metadata.create_all(bind=test_engine)
    
    # Override dependency
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Cleanup
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()


# ============== Request CRUD Tests ==============

class TestRequestCRUD:
    """Tests for Request CRUD operations."""
    
    def test_create_request(self, client):
        """Test creating a new request."""
        request_data = {
            "name": "Test Request",
            "method": "GET",
            "url": "https://api.example.com/users",
            "headers": {"Authorization": "Bearer token"},
            "query_params": {"page": "1"}
        }
        
        response = client.post("/api/requests", json=request_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Request"
        assert data["method"] == "GET"
        assert data["url"] == "https://api.example.com/users"
        assert data["headers"] == {"Authorization": "Bearer token"}
        assert data["query_params"] == {"page": "1"}
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_list_requests(self, client):
        """Test listing all requests."""
        # Create multiple requests
        for i in range(3):
            client.post("/api/requests", json={
                "name": f"Request {i}",
                "method": "GET",
                "url": f"https://api.example.com/endpoint{i}"
            })
        
        response = client.get("/api/requests")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
    
    def test_get_request(self, client):
        """Test getting a single request by ID."""
        # Create a request
        create_response = client.post("/api/requests", json={
            "name": "Test Request",
            "method": "POST",
            "url": "https://api.example.com/users",
            "body_type": "json",
            "body": '{"name": "John"}'
        })
        request_id = create_response.json()["id"]
        
        response = client.get(f"/api/requests/{request_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == request_id
        assert data["name"] == "Test Request"
        assert data["method"] == "POST"
    
    def test_get_request_not_found(self, client):
        """Test getting a non-existent request returns 404."""
        response = client.get("/api/requests/99999")
        
        assert response.status_code == 404
    
    def test_update_request(self, client):
        """Test updating an existing request."""
        # Create a request
        create_response = client.post("/api/requests", json={
            "name": "Original Name",
            "method": "GET",
            "url": "https://api.example.com/original"
        })
        request_id = create_response.json()["id"]
        
        # Update the request
        response = client.put(f"/api/requests/{request_id}", json={
            "name": "Updated Name",
            "method": "POST"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["method"] == "POST"
        assert data["url"] == "https://api.example.com/original"  # Unchanged
    
    def test_delete_request(self, client):
        """Test deleting a request."""
        # Create a request
        create_response = client.post("/api/requests", json={
            "name": "To Delete",
            "method": "GET",
            "url": "https://api.example.com/delete"
        })
        request_id = create_response.json()["id"]
        
        # Delete the request
        response = client.delete(f"/api/requests/{request_id}")
        assert response.status_code == 204
        
        # Verify it's deleted
        get_response = client.get(f"/api/requests/{request_id}")
        assert get_response.status_code == 404
    
    def test_all_http_methods_supported(self, client):
        """Test that all HTTP methods are supported."""
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        
        for method in methods:
            response = client.post("/api/requests", json={
                "name": f"{method} Request",
                "method": method,
                "url": "https://api.example.com/test"
            })
            assert response.status_code == 201, f"Failed for method {method}"
            assert response.json()["method"] == method


# ============== Collection CRUD Tests ==============

class TestCollectionCRUD:
    """Tests for Collection CRUD operations."""
    
    def test_create_collection(self, client):
        """Test creating a new collection."""
        collection_data = {
            "name": "Test Collection",
            "description": "A test collection"
        }
        
        response = client.post("/api/collections", json=collection_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Collection"
        assert data["description"] == "A test collection"
        assert "id" in data
    
    def test_list_collections(self, client):
        """Test listing all collections."""
        # Create multiple collections
        for i in range(3):
            client.post("/api/collections", json={"name": f"Collection {i}"})
        
        response = client.get("/api/collections")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
    
    def test_get_collection_with_nested_structure(self, client):
        """Test getting a collection with its nested folders and requests."""
        # Create a collection
        collection_response = client.post("/api/collections", json={
            "name": "Test Collection"
        })
        collection_id = collection_response.json()["id"]
        
        # Create a folder in the collection
        folder_response = client.post(f"/api/collections/{collection_id}/folders", json={
            "name": "Test Folder"
        })
        folder_id = folder_response.json()["id"]
        
        # Create a request directly in the collection
        client.post("/api/requests", json={
            "name": "Direct Request",
            "method": "GET",
            "url": "https://api.example.com/direct",
            "collection_id": collection_id
        })
        
        # Create a request in the folder
        client.post("/api/requests", json={
            "name": "Folder Request",
            "method": "POST",
            "url": "https://api.example.com/folder",
            "collection_id": collection_id,
            "folder_id": folder_id
        })
        
        # Get the collection with nested structure
        response = client.get(f"/api/collections/{collection_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Collection"
        assert len(data["folders"]) == 1
        assert data["folders"][0]["name"] == "Test Folder"
        assert len(data["requests"]) == 1  # Only direct requests
        assert data["requests"][0]["name"] == "Direct Request"
    
    def test_update_collection(self, client):
        """Test updating a collection."""
        # Create a collection
        create_response = client.post("/api/collections", json={
            "name": "Original Name"
        })
        collection_id = create_response.json()["id"]
        
        # Update the collection
        response = client.put(f"/api/collections/{collection_id}", json={
            "name": "Updated Name",
            "description": "New description"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["description"] == "New description"
    
    def test_delete_collection_cascades(self, client):
        """Test that deleting a collection cascades to folders and requests."""
        # Create a collection
        collection_response = client.post("/api/collections", json={
            "name": "To Delete"
        })
        collection_id = collection_response.json()["id"]
        
        # Create a folder
        folder_response = client.post(f"/api/collections/{collection_id}/folders", json={
            "name": "Folder"
        })
        folder_id = folder_response.json()["id"]
        
        # Create a request
        request_response = client.post("/api/requests", json={
            "name": "Request",
            "method": "GET",
            "url": "https://api.example.com/test",
            "collection_id": collection_id
        })
        request_id = request_response.json()["id"]
        
        # Delete the collection
        response = client.delete(f"/api/collections/{collection_id}")
        assert response.status_code == 204
        
        # Verify collection is deleted
        assert client.get(f"/api/collections/{collection_id}").status_code == 404
        
        # Verify request is deleted (via cascade)
        assert client.get(f"/api/requests/{request_id}").status_code == 404
        
        # Verify folder is deleted by checking it can't be updated
        # (no GET endpoint for individual folders exists)
        update_response = client.put(f"/api/folders/{folder_id}", json={"name": "Test"})
        assert update_response.status_code == 404


# ============== Folder CRUD Tests ==============

class TestFolderCRUD:
    """Tests for Folder CRUD operations."""
    
    def test_create_folder(self, client):
        """Test creating a folder in a collection."""
        # Create a collection first
        collection_response = client.post("/api/collections", json={
            "name": "Test Collection"
        })
        collection_id = collection_response.json()["id"]
        
        # Create a folder
        response = client.post(f"/api/collections/{collection_id}/folders", json={
            "name": "Test Folder"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Folder"
        assert data["collection_id"] == collection_id
    
    def test_create_nested_folder(self, client):
        """Test creating a nested folder."""
        # Create a collection
        collection_response = client.post("/api/collections", json={
            "name": "Test Collection"
        })
        collection_id = collection_response.json()["id"]
        
        # Create a parent folder
        parent_response = client.post(f"/api/collections/{collection_id}/folders", json={
            "name": "Parent Folder"
        })
        parent_id = parent_response.json()["id"]
        
        # Create a child folder
        response = client.post(f"/api/collections/{collection_id}/folders", json={
            "name": "Child Folder",
            "parent_folder_id": parent_id
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Child Folder"
        assert data["parent_folder_id"] == parent_id
    
    def test_update_folder(self, client):
        """Test updating a folder."""
        # Create a collection and folder
        collection_response = client.post("/api/collections", json={
            "name": "Test Collection"
        })
        collection_id = collection_response.json()["id"]
        
        folder_response = client.post(f"/api/collections/{collection_id}/folders", json={
            "name": "Original Name"
        })
        folder_id = folder_response.json()["id"]
        
        # Update the folder
        response = client.put(f"/api/folders/{folder_id}", json={
            "name": "Updated Name"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
    
    def test_delete_folder(self, client):
        """Test deleting a folder."""
        # Create a collection and folder
        collection_response = client.post("/api/collections", json={
            "name": "Test Collection"
        })
        collection_id = collection_response.json()["id"]
        
        folder_response = client.post(f"/api/collections/{collection_id}/folders", json={
            "name": "To Delete"
        })
        folder_id = folder_response.json()["id"]
        
        # Delete the folder
        response = client.delete(f"/api/folders/{folder_id}")
        assert response.status_code == 204
        
        # Verify it's deleted by checking it can't be updated
        # (no GET endpoint for individual folders exists)
        update_response = client.put(f"/api/folders/{folder_id}", json={"name": "Test"})
        assert update_response.status_code == 404


# ============== Folder Nesting Validation Tests ==============

class TestFolderNestingValidation:
    """Tests for folder nesting depth and parent validation in create_folder."""

    def test_create_folder_parent_not_found(self, client):
        """Creating a folder with a non-existent parent_folder_id returns 404."""
        coll = client.post("/api/collections", json={"name": "C"}).json()
        response = client.post(
            f"/api/collections/{coll['id']}/folders",
            json={"name": "Child", "parent_folder_id": 99999},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_folder_parent_wrong_collection(self, client):
        """Creating a folder whose parent belongs to another collection returns 400."""
        coll1 = client.post("/api/collections", json={"name": "C1"}).json()
        coll2 = client.post("/api/collections", json={"name": "C2"}).json()
        parent = client.post(
            f"/api/collections/{coll1['id']}/folders",
            json={"name": "Parent"},
        ).json()

        response = client.post(
            f"/api/collections/{coll2['id']}/folders",
            json={"name": "Child", "parent_folder_id": parent["id"]},
        )
        assert response.status_code == 400
        assert "does not belong to the same collection" in response.json()["detail"]

    def test_create_folder_exceeds_max_nesting_depth(self, client):
        """Creating a folder that would exceed MAX_NESTING_DEPTH (5) returns 400."""
        coll = client.post("/api/collections", json={"name": "C"}).json()
        cid = coll["id"]

        # Build a chain of 5 folders (depth 1 through 5)
        parent_id = None
        for i in range(5):
            resp = client.post(
                f"/api/collections/{cid}/folders",
                json={"name": f"L{i+1}", "parent_folder_id": parent_id},
            )
            assert resp.status_code == 201, f"Failed creating folder at depth {i+1}"
            parent_id = resp.json()["id"]

        # Attempt to create a 6th level — should be rejected
        response = client.post(
            f"/api/collections/{cid}/folders",
            json={"name": "L6", "parent_folder_id": parent_id},
        )
        assert response.status_code == 400
        assert "Maximum nesting depth of 5 exceeded" in response.json()["detail"]

    def test_create_folder_at_max_depth_succeeds(self, client):
        """Creating a folder at exactly MAX_NESTING_DEPTH (5) succeeds."""
        coll = client.post("/api/collections", json={"name": "C"}).json()
        cid = coll["id"]

        # Build a chain of 4 folders (depth 1 through 4)
        parent_id = None
        for i in range(4):
            resp = client.post(
                f"/api/collections/{cid}/folders",
                json={"name": f"L{i+1}", "parent_folder_id": parent_id},
            )
            assert resp.status_code == 201
            parent_id = resp.json()["id"]

        # Creating at depth 5 should succeed
        response = client.post(
            f"/api/collections/{cid}/folders",
            json={"name": "L5", "parent_folder_id": parent_id},
        )
        assert response.status_code == 201
        assert response.json()["parent_folder_id"] == parent_id

    def test_create_root_folder_no_depth_check(self, client):
        """Creating a root folder (no parent) does not trigger depth validation."""
        coll = client.post("/api/collections", json={"name": "C"}).json()
        response = client.post(
            f"/api/collections/{coll['id']}/folders",
            json={"name": "Root"},
        )
        assert response.status_code == 201
        assert response.json()["parent_folder_id"] is None


# ============== Environment CRUD Tests ==============

class TestEnvironmentCRUD:
    """Tests for Environment CRUD operations."""
    
    def test_create_environment(self, client):
        """Test creating a new environment."""
        env_data = {
            "name": "Development",
            "is_active": True,
            "variables": [
                {"key": "base_url", "value": "http://localhost:3000"},
                {"key": "api_key", "value": "dev-key-123"}
            ]
        }
        
        response = client.post("/api/environments", json=env_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Development"
        assert data["is_active"] is True
        assert len(data["variables"]) == 2
    
    def test_list_environments(self, client):
        """Test listing all environments."""
        # Create multiple environments
        for i in range(3):
            client.post("/api/environments", json={
                "name": f"Environment {i}",
                "variables": []
            })
        
        response = client.get("/api/environments")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
    
    def test_get_environment(self, client):
        """Test getting a single environment."""
        # Create an environment
        create_response = client.post("/api/environments", json={
            "name": "Test Env",
            "variables": [{"key": "test_key", "value": "test_value"}]
        })
        env_id = create_response.json()["id"]
        
        response = client.get(f"/api/environments/{env_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Env"
        assert len(data["variables"]) == 1
    
    def test_update_environment(self, client):
        """Test updating an environment."""
        # Create an environment
        create_response = client.post("/api/environments", json={
            "name": "Original Name",
            "variables": []
        })
        env_id = create_response.json()["id"]
        
        # Update the environment
        response = client.put(f"/api/environments/{env_id}", json={
            "name": "Updated Name"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
    
    def test_delete_environment_cascades(self, client):
        """Test that deleting an environment cascades to variables."""
        # Create an environment with variables
        create_response = client.post("/api/environments", json={
            "name": "To Delete",
            "variables": [
                {"key": "key1", "value": "value1"},
                {"key": "key2", "value": "value2"}
            ]
        })
        env_id = create_response.json()["id"]
        
        # Delete the environment
        response = client.delete(f"/api/environments/{env_id}")
        assert response.status_code == 204
        
        # Verify it's deleted
        get_response = client.get(f"/api/environments/{env_id}")
        assert get_response.status_code == 404
    
    def test_activate_environment(self, client):
        """Test activating an environment."""
        # Create two environments
        env1_response = client.post("/api/environments", json={
            "name": "Env 1",
            "is_active": True,
            "variables": []
        })
        env1_id = env1_response.json()["id"]
        
        env2_response = client.post("/api/environments", json={
            "name": "Env 2",
            "is_active": False,
            "variables": []
        })
        env2_id = env2_response.json()["id"]
        
        # Activate env2
        response = client.post(f"/api/environments/{env2_id}/activate")
        
        assert response.status_code == 200
        assert response.json()["is_active"] is True
        
        # Verify env1 is now inactive
        env1_data = client.get(f"/api/environments/{env1_id}").json()
        assert env1_data["is_active"] is False
    
    def test_add_variable(self, client):
        """Test adding a variable to an environment."""
        # Create an environment
        create_response = client.post("/api/environments", json={
            "name": "Test Env",
            "variables": []
        })
        env_id = create_response.json()["id"]
        
        # Add a variable
        response = client.post(f"/api/environments/{env_id}/variables", json={
            "key": "new_key",
            "value": "new_value"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "new_key"
        assert data["value"] == "new_value"
    
    def test_update_variable(self, client):
        """Test updating a variable."""
        # Create an environment with a variable
        create_response = client.post("/api/environments", json={
            "name": "Test Env",
            "variables": [{"key": "test_key", "value": "original_value"}]
        })
        var_id = create_response.json()["variables"][0]["id"]
        
        # Update the variable
        response = client.put(f"/api/environments/variables/{var_id}", json={
            "value": "updated_value"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == "updated_value"
    
    def test_delete_variable(self, client):
        """Test deleting a variable."""
        # Create an environment with a variable
        create_response = client.post("/api/environments", json={
            "name": "Test Env",
            "variables": [{"key": "to_delete", "value": "value"}]
        })
        env_id = create_response.json()["id"]
        var_id = create_response.json()["variables"][0]["id"]
        
        # Delete the variable
        response = client.delete(f"/api/environments/variables/{var_id}")
        assert response.status_code == 204
        
        # Verify it's deleted
        env_data = client.get(f"/api/environments/{env_id}").json()
        assert len(env_data["variables"]) == 0
