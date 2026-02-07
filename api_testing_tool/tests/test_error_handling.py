"""
Tests for global error handling and response format consistency.

Validates Property 17: Error response format consistency.
**Validates: Requirements 10.3**
"""

import pytest
from hypothesis import given, strategies as st, settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from ..main import app
from ..database import Base, get_db


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_error_handling.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@contextmanager
def get_test_client():
    """Context manager to create a test client with fresh database."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def client():
    """Create test client with test database."""
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


# Strategies for generating test data
resource_id_strategy = st.integers(min_value=90000, max_value=99999)

resource_type_strategy = st.sampled_from([
    ("requests", "Request"),
    ("collections", "Collection"),
    ("environments", "Environment"),
])

invalid_http_method_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    min_size=1,
    max_size=10
).filter(lambda m: m not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])


class TestErrorResponseFormat:
    """Tests for consistent error response format."""
    
    def test_404_error_format_request_not_found(self, client):
        """Test 404 error response format when request not found."""
        response = client.get("/api/requests/99999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "99999" in data["detail"]
    
    def test_404_error_format_collection_not_found(self, client):
        """Test 404 error response format when collection not found."""
        response = client.get("/api/collections/99999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "99999" in data["detail"]
    
    def test_404_error_format_environment_not_found(self, client):
        """Test 404 error response format when environment not found."""
        response = client.get("/api/environments/99999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "99999" in data["detail"]
    
    def test_404_error_format_folder_not_found(self, client):
        """Test 404 error response format when folder not found."""
        response = client.delete("/api/folders/99999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "99999" in data["detail"]
    
    def test_422_validation_error_format(self, client):
        """Test 422 validation error response format."""
        # Send invalid request data (missing required fields)
        response = client.post("/api/requests", json={})
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "error_code" in data
        assert data["error_code"] == "VALIDATION_ERROR"
    
    def test_422_validation_error_invalid_method(self, client):
        """Test 422 validation error for invalid HTTP method."""
        response = client.post("/api/requests", json={
            "name": "Test",
            "method": "INVALID",
            "url": "http://example.com"
        })
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "error_code" in data
        assert data["error_code"] == "VALIDATION_ERROR"
    
    def test_400_bad_request_circular_folder(self, client):
        """Test 400 error for circular folder reference."""
        # Create a collection first
        collection_response = client.post("/api/collections", json={
            "name": "Test Collection"
        })
        collection_id = collection_response.json()["id"]
        
        # Create a folder
        folder_response = client.post(f"/api/collections/{collection_id}/folders", json={
            "name": "Test Folder"
        })
        folder_id = folder_response.json()["id"]
        
        # Try to set folder as its own parent
        response = client.put(f"/api/folders/{folder_id}", json={
            "parent_folder_id": folder_id
        })
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    def test_error_response_has_detail_field(self, client):
        """Test that all error responses have a detail field."""
        # Test various error scenarios
        error_responses = [
            client.get("/api/requests/99999"),
            client.get("/api/collections/99999"),
            client.get("/api/environments/99999"),
            client.delete("/api/folders/99999"),
        ]
        
        for response in error_responses:
            assert response.status_code >= 400
            data = response.json()
            assert "detail" in data, f"Response missing 'detail' field: {data}"


class TestExceptionClasses:
    """Tests for custom exception classes."""
    
    def test_resource_not_found_error_message(self, client):
        """Test ResourceNotFoundError generates correct message."""
        response = client.get("/api/requests/12345")
        assert response.status_code == 404
        data = response.json()
        assert "Request" in data["detail"] or "request" in data["detail"].lower()
        assert "12345" in data["detail"]
    
    def test_validation_error_includes_field_info(self, client):
        """Test validation errors include field information."""
        response = client.post("/api/requests", json={
            "name": "Test",
            "method": "GET"
            # Missing required 'url' field
        })
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # The error should mention the missing field
        assert "url" in data["detail"].lower()


class TestProperty17ErrorResponseFormatConsistency:
    """
    Property 17: 错误响应格式一致性
    
    *对于任意*导致错误的请求（如资源不存在、参数无效），
    系统应该返回包含错误详情的 JSON 响应和适当的 HTTP 状态码。
    
    **Validates: Requirements 10.3**
    """

    @given(
        resource_id=resource_id_strategy,
        resource_info=resource_type_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_404_error_response_format_consistency(
        self, resource_id: int, resource_info: tuple[str, str]
    ):
        """
        Property: For any non-existent resource ID, the error response should have
        a consistent format with 'detail' field containing the resource ID.
        """
        endpoint, resource_name = resource_info
        
        with get_test_client() as client:
            response = client.get(f"/api/{endpoint}/{resource_id}")
            
            # Should return 404
            assert response.status_code == 404
            
            # Response should be valid JSON
            data = response.json()
            
            # Must have 'detail' field
            assert "detail" in data, f"Error response missing 'detail' field: {data}"
            
            # Detail should contain the resource ID
            assert str(resource_id) in data["detail"], \
                f"Error detail should contain resource ID {resource_id}: {data['detail']}"

    @given(invalid_method=invalid_http_method_strategy)
    @settings(max_examples=100, deadline=None)
    def test_422_validation_error_format_consistency(self, invalid_method: str):
        """
        Property: For any invalid HTTP method, the validation error response should
        have a consistent format with 'detail' and 'error_code' fields.
        """
        with get_test_client() as client:
            response = client.post("/api/requests", json={
                "name": "Test Request",
                "method": invalid_method,
                "url": "https://api.example.com/test"
            })
            
            # Should return 422 validation error
            assert response.status_code == 422
            
            # Response should be valid JSON
            data = response.json()
            
            # Must have 'detail' field
            assert "detail" in data, f"Validation error missing 'detail' field: {data}"
            
            # Must have 'error_code' field
            assert "error_code" in data, f"Validation error missing 'error_code' field: {data}"
            
            # Error code should be VALIDATION_ERROR
            assert data["error_code"] == "VALIDATION_ERROR"

    @given(resource_id=resource_id_strategy)
    @settings(max_examples=100, deadline=None)
    def test_error_response_is_valid_json(self, resource_id: int):
        """
        Property: For any error response, the body should be valid JSON
        with the required 'detail' field.
        """
        with get_test_client() as client:
            # Test multiple error scenarios
            error_endpoints = [
                f"/api/requests/{resource_id}",
                f"/api/collections/{resource_id}",
                f"/api/environments/{resource_id}",
            ]
            
            for endpoint in error_endpoints:
                response = client.get(endpoint)
                
                # Should be an error response
                assert response.status_code >= 400
                
                # Should be valid JSON
                try:
                    data = response.json()
                except Exception as e:
                    pytest.fail(f"Response is not valid JSON for {endpoint}: {e}")
                
                # Must have 'detail' field
                assert "detail" in data, \
                    f"Error response missing 'detail' for {endpoint}: {data}"
                
                # Detail should be a non-empty string
                assert isinstance(data["detail"], str) and len(data["detail"]) > 0, \
                    f"Error detail should be non-empty string for {endpoint}: {data}"
