"""
Property-based tests for Request CRUD operations.

Tests Properties 1-5 from the design document.
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from api_testing_tool.main import app
from api_testing_tool.database import Base, get_db


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_request_crud_properties.db"
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


# Strategies for generating valid request data
http_method_strategy = st.sampled_from(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])

request_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-"),
    min_size=1,
    max_size=50
)

url_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:/.?=&_-"),
    min_size=10,
    max_size=100
).map(lambda s: "https://api.example.com/" + s)

header_key_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"),
    min_size=1,
    max_size=30
)

header_value_strategy = st.text(min_size=1, max_size=50)

headers_strategy = st.dictionaries(
    keys=header_key_strategy,
    values=header_value_strategy,
    min_size=0,
    max_size=5
)

query_params_strategy = st.dictionaries(
    keys=st.text(alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz_"), min_size=1, max_size=20),
    values=st.text(min_size=1, max_size=30),
    min_size=0,
    max_size=5
)


class TestProperty1RequestCRUDRoundTrip:
    """
    Property 1: 请求 CRUD 往返一致性
    
    *对于任意*有效的请求数据，创建请求后通过 ID 获取该请求，
    应该返回与创建时相同的数据（除了系统生成的字段如 id、created_at、updated_at）。
    
    **Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5**
    """

    @given(
        name=request_name_strategy,
        method=http_method_strategy,
        url=url_strategy,
        headers=headers_strategy,
        query_params=query_params_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_create_and_get_returns_same_data(
        self, name: str, method: str, url: str, 
        headers: dict[str, str], query_params: dict[str, str]
    ):
        """
        Property: Creating a request and then getting it by ID returns the same data.
        """
        with get_test_client() as client:
            request_data = {
                "name": name,
                "method": method,
                "url": url,
                "headers": headers,
                "query_params": query_params
            }
            
            # Create the request
            create_response = client.post("/api/requests", json=request_data)
            assert create_response.status_code == 201
            created = create_response.json()
            
            # Get the request by ID
            get_response = client.get(f"/api/requests/{created['id']}")
            assert get_response.status_code == 200
            retrieved = get_response.json()
            
            # Verify data matches (excluding system-generated fields)
            assert retrieved["name"] == name
            assert retrieved["method"] == method
            assert retrieved["url"] == url
            assert retrieved["headers"] == headers
            assert retrieved["query_params"] == query_params


class TestProperty2RequestUpdatePersistence:
    """
    Property 2: 请求更新持久化
    
    *对于任意*已存在的请求和有效的更新数据，
    更新请求后再获取该请求，应该返回更新后的数据。
    
    **Validates: Requirements 1.3**
    """

    @given(
        original_name=request_name_strategy,
        updated_name=request_name_strategy,
        original_method=http_method_strategy,
        updated_method=http_method_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_update_persists_changes(
        self, original_name: str, updated_name: str,
        original_method: str, updated_method: str
    ):
        """
        Property: Updating a request persists the changes when retrieved.
        """
        with get_test_client() as client:
            # Create a request
            create_response = client.post("/api/requests", json={
                "name": original_name,
                "method": original_method,
                "url": "https://api.example.com/test"
            })
            assert create_response.status_code == 201
            request_id = create_response.json()["id"]
            
            # Update the request
            update_response = client.put(f"/api/requests/{request_id}", json={
                "name": updated_name,
                "method": updated_method
            })
            assert update_response.status_code == 200
            
            # Get the request and verify updates persisted
            get_response = client.get(f"/api/requests/{request_id}")
            assert get_response.status_code == 200
            retrieved = get_response.json()
            
            assert retrieved["name"] == updated_name
            assert retrieved["method"] == updated_method


class TestProperty3RequestDeleteValidity:
    """
    Property 3: 请求删除有效性
    
    *对于任意*已存在的请求，删除该请求后再尝试获取，应该返回 404 错误。
    
    **Validates: Requirements 1.4**
    """

    @given(
        name=request_name_strategy,
        method=http_method_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_deleted_request_returns_404(self, name: str, method: str):
        """
        Property: After deleting a request, getting it returns 404.
        """
        with get_test_client() as client:
            # Create a request
            create_response = client.post("/api/requests", json={
                "name": name,
                "method": method,
                "url": "https://api.example.com/test"
            })
            assert create_response.status_code == 201
            request_id = create_response.json()["id"]
            
            # Delete the request
            delete_response = client.delete(f"/api/requests/{request_id}")
            assert delete_response.status_code == 204
            
            # Try to get the deleted request
            get_response = client.get(f"/api/requests/{request_id}")
            assert get_response.status_code == 404


class TestProperty4RequestListCompleteness:
    """
    Property 4: 请求列表完整性
    
    *对于任意* N 个创建的请求，列出所有请求应该返回包含这 N 个请求的列表。
    
    **Validates: Requirements 1.5**
    """

    @given(
        request_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50, deadline=None)
    def test_list_contains_all_created_requests(self, request_count: int):
        """
        Property: Listing requests returns all created requests.
        """
        with get_test_client() as client:
            created_ids = []
            
            # Create N requests
            for i in range(request_count):
                response = client.post("/api/requests", json={
                    "name": f"Request {i}",
                    "method": "GET",
                    "url": f"https://api.example.com/endpoint{i}"
                })
                assert response.status_code == 201
                created_ids.append(response.json()["id"])
            
            # List all requests
            list_response = client.get("/api/requests")
            assert list_response.status_code == 200
            listed_requests = list_response.json()
            
            # Verify all created requests are in the list
            listed_ids = [r["id"] for r in listed_requests]
            for created_id in created_ids:
                assert created_id in listed_ids
            
            # Verify count matches
            assert len(listed_requests) == request_count


class TestProperty5HTTPMethodSupport:
    """
    Property 5: HTTP 方法支持
    
    *对于任意* HTTP 方法（GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS），
    创建使用该方法的请求应该成功。
    
    **Validates: Requirements 1.6**
    """

    @given(method=http_method_strategy)
    @settings(max_examples=100, deadline=None)
    def test_all_http_methods_can_be_created(self, method: str):
        """
        Property: Any valid HTTP method can be used to create a request.
        """
        with get_test_client() as client:
            response = client.post("/api/requests", json={
                "name": f"Test {method} Request",
                "method": method,
                "url": "https://api.example.com/test"
            })
            
            assert response.status_code == 201
            assert response.json()["method"] == method
