"""
Property-based tests for History record operations.

Tests Properties 15-16 from the design document.
**Validates: Requirements 8.1, 8.2, 8.3**
"""

import pytest
from hypothesis import given, strategies as st, settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from datetime import datetime
import time

from api_testing_tool.main import app
from api_testing_tool.database import Base, get_db
from api_testing_tool.models.history import History


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_history_properties.db"
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


def get_test_db():
    """Get a test database session for direct database operations."""
    return TestSessionLocal()


# Strategies for generating valid history data
http_method_strategy = st.sampled_from(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])

url_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789-._~:/?#[]@!$&'()*+,;="),
    min_size=10,
    max_size=100
).map(lambda s: f"https://example.com/{s}")

status_code_strategy = st.sampled_from([200, 201, 204, 400, 401, 403, 404, 500, 502, 503])

status_text_strategy = st.sampled_from(["OK", "Created", "No Content", "Bad Request", "Not Found", "Internal Server Error"])

response_time_strategy = st.integers(min_value=1, max_value=10000)

response_size_strategy = st.integers(min_value=0, max_value=100000)


def create_history_record_directly(db, method: str, url: str, status_code: int, 
                                    status_text: str, response_time_ms: int, 
                                    response_size: int) -> History:
    """Create a history record directly in the database."""
    history = History(
        method=method,
        url=url,
        request_headers={},
        request_body=None,
        status_code=status_code,
        status_text=status_text,
        response_headers={},
        response_body=None,
        response_time_ms=response_time_ms,
        response_size=response_size
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return history


class TestProperty15HistoryRecordSorting:
    """
    Property 15: 历史记录排序
    
    *对于任意*多次请求执行产生的历史记录，
    获取历史列表应该按执行时间降序排列。
    
    **Validates: Requirements 8.3**
    """

    @given(
        record_count=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=20, deadline=None)
    def test_history_list_ordered_by_execution_time_descending(self, record_count: int):
        """
        Property: History records are returned in descending order by executed_at.
        """
        with get_test_client() as client:
            # Create multiple history records with small delays to ensure different timestamps
            db = get_test_db()
            try:
                created_ids = []
                for i in range(record_count):
                    history = create_history_record_directly(
                        db=db,
                        method="GET",
                        url=f"https://example.com/test/{i}",
                        status_code=200,
                        status_text="OK",
                        response_time_ms=100 + i,
                        response_size=1000 + i
                    )
                    created_ids.append(history.id)
                    # Small delay to ensure different timestamps
                    time.sleep(0.01)
            finally:
                db.close()
            
            # Get history list
            response = client.get("/api/history")
            assert response.status_code == 200
            
            history_list = response.json()
            items = history_list["items"]
            
            # Verify we have all records
            assert len(items) == record_count
            
            # Verify ordering: each record's executed_at should be >= the next one
            for i in range(len(items) - 1):
                current_time = datetime.fromisoformat(items[i]["executed_at"].replace("Z", "+00:00"))
                next_time = datetime.fromisoformat(items[i + 1]["executed_at"].replace("Z", "+00:00"))
                assert current_time >= next_time, \
                    f"History records not in descending order: {items[i]['executed_at']} should be >= {items[i + 1]['executed_at']}"


class TestProperty16HistoryRecordCompleteness:
    """
    Property 16: 历史记录完整性
    
    *对于任意*请求执行，保存的历史记录应该包含
    完整的请求详情、响应详情和时间戳。
    
    **Validates: Requirements 8.1, 8.2**
    """

    @given(
        method=http_method_strategy,
        status_code=status_code_strategy,
        status_text=status_text_strategy,
        response_time_ms=response_time_strategy,
        response_size=response_size_strategy
    )
    @settings(max_examples=20, deadline=None)
    def test_history_record_contains_complete_details(
        self, method: str, status_code: int, status_text: str,
        response_time_ms: int, response_size: int
    ):
        """
        Property: History records contain all required request and response details.
        """
        with get_test_client() as client:
            # Create a history record directly
            db = get_test_db()
            try:
                url = f"https://example.com/api/{method.lower()}"
                request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
                request_body = '{"test": "data"}'
                response_headers = {"Content-Type": "application/json"}
                response_body = '{"result": "success"}'
                
                history = History(
                    method=method,
                    url=url,
                    request_headers=request_headers,
                    request_body=request_body,
                    status_code=status_code,
                    status_text=status_text,
                    response_headers=response_headers,
                    response_body=response_body,
                    response_time_ms=response_time_ms,
                    response_size=response_size
                )
                db.add(history)
                db.commit()
                db.refresh(history)
                history_id = history.id
            finally:
                db.close()
            
            # Get the history record via API
            response = client.get(f"/api/history/{history_id}")
            assert response.status_code == 200
            
            history_data = response.json()
            
            # Verify request details are complete
            assert history_data["method"] == method
            assert history_data["url"] == url
            assert history_data["request_headers"] == request_headers
            assert history_data["request_body"] == request_body
            
            # Verify response details are complete
            assert history_data["status_code"] == status_code
            assert history_data["status_text"] == status_text
            assert history_data["response_headers"] == response_headers
            assert history_data["response_body"] == response_body
            assert history_data["response_time_ms"] == response_time_ms
            assert history_data["response_size"] == response_size
            
            # Verify timestamp is present
            assert "executed_at" in history_data
            assert history_data["executed_at"] is not None
            # Verify timestamp is a valid ISO format datetime
            executed_at = datetime.fromisoformat(history_data["executed_at"].replace("Z", "+00:00"))
            assert executed_at is not None

