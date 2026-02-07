"""
Property-based tests for Environment management operations.

Tests Properties 8-9 from the design document.
**Validates: Requirements 4.1, 4.2, 4.4, 4.5**
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
TEST_DATABASE_URL = "sqlite:///./test_environment_properties.db"
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


# Strategies for generating valid environment/variable data
environment_name_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-"),
    min_size=1,
    max_size=50
)

variable_key_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"),
    min_size=1,
    max_size=30
)

variable_value_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:/.?=&_-"),
    min_size=1,
    max_size=100
)

variable_strategy = st.fixed_dictionaries({
    "key": variable_key_strategy,
    "value": variable_value_strategy
})

variables_list_strategy = st.lists(variable_strategy, min_size=0, max_size=5)


class TestProperty8EnvironmentVariableCRUDRoundTrip:
    """
    Property 8: 环境变量 CRUD 往返一致性
    
    *对于任意*有效的环境数据和变量，创建环境并添加变量后获取该环境，
    应该返回包含所有变量的环境数据。
    
    **Validates: Requirements 4.1, 4.2, 4.5**
    """

    @given(
        env_name=environment_name_strategy,
        variables=variables_list_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_create_environment_with_variables_roundtrip(
        self, env_name: str, variables: list[dict]
    ):
        """
        Property: Creating an environment with variables and getting it returns all data.
        """
        with get_test_client() as client:
            # Create environment with initial variables
            create_response = client.post("/api/environments", json={
                "name": env_name,
                "is_active": False,
                "variables": variables
            })
            assert create_response.status_code == 201
            created = create_response.json()
            env_id = created["id"]
            
            # Get the environment by ID
            get_response = client.get(f"/api/environments/{env_id}")
            assert get_response.status_code == 200
            retrieved = get_response.json()
            
            # Verify environment data matches
            assert retrieved["name"] == env_name
            assert retrieved["id"] == env_id
            
            # Verify all variables are present
            assert len(retrieved["variables"]) == len(variables)
            
            # Create sets of (key, value) tuples for comparison
            expected_vars = {(v["key"], v["value"]) for v in variables}
            retrieved_vars = {(v["key"], v["value"]) for v in retrieved["variables"]}
            assert retrieved_vars == expected_vars

    @given(
        env_name=environment_name_strategy,
        var_key=variable_key_strategy,
        var_value=variable_value_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_add_variable_to_environment_roundtrip(
        self, env_name: str, var_key: str, var_value: str
    ):
        """
        Property: Adding a variable to an environment persists correctly.
        """
        with get_test_client() as client:
            # Create environment without variables
            create_response = client.post("/api/environments", json={
                "name": env_name,
                "is_active": False,
                "variables": []
            })
            assert create_response.status_code == 201
            env_id = create_response.json()["id"]
            
            # Add a variable
            add_var_response = client.post(
                f"/api/environments/{env_id}/variables",
                json={"key": var_key, "value": var_value}
            )
            assert add_var_response.status_code == 201
            
            # Get the environment and verify variable is present
            get_response = client.get(f"/api/environments/{env_id}")
            assert get_response.status_code == 200
            retrieved = get_response.json()
            
            assert len(retrieved["variables"]) == 1
            assert retrieved["variables"][0]["key"] == var_key
            assert retrieved["variables"][0]["value"] == var_value

    @given(
        env_name=environment_name_strategy,
        initial_variables=st.lists(variable_strategy, min_size=1, max_size=3),
        additional_variables=st.lists(variable_strategy, min_size=1, max_size=2)
    )
    @settings(max_examples=50, deadline=None)
    def test_list_environments_returns_all_with_variables(
        self, env_name: str, initial_variables: list[dict], additional_variables: list[dict]
    ):
        """
        Property: Listing environments returns all environments with their variables.
        """
        with get_test_client() as client:
            # Create environment with initial variables
            create_response = client.post("/api/environments", json={
                "name": env_name,
                "is_active": False,
                "variables": initial_variables
            })
            assert create_response.status_code == 201
            env_id = create_response.json()["id"]
            
            # Add additional variables
            for var in additional_variables:
                add_response = client.post(
                    f"/api/environments/{env_id}/variables",
                    json=var
                )
                assert add_response.status_code == 201
            
            # List all environments
            list_response = client.get("/api/environments")
            assert list_response.status_code == 200
            environments = list_response.json()
            
            # Find our environment
            our_env = next((e for e in environments if e["id"] == env_id), None)
            assert our_env is not None
            
            # Verify all variables are present
            total_vars = len(initial_variables) + len(additional_variables)
            assert len(our_env["variables"]) == total_vars


class TestProperty9EnvironmentCascadeDelete:
    """
    Property 9: 环境级联删除
    
    *对于任意*包含变量的环境，删除该环境后，其所有变量都应该被删除。
    
    **Validates: Requirements 4.4**
    """

    @given(
        env_name=environment_name_strategy,
        variables=st.lists(variable_strategy, min_size=1, max_size=5)
    )
    @settings(max_examples=100, deadline=None)
    def test_deleting_environment_cascades_to_variables(
        self, env_name: str, variables: list[dict]
    ):
        """
        Property: Deleting an environment removes all its variables.
        """
        with get_test_client() as client:
            # Create environment with variables
            create_response = client.post("/api/environments", json={
                "name": env_name,
                "is_active": False,
                "variables": variables
            })
            assert create_response.status_code == 201
            env_id = create_response.json()["id"]
            variable_ids = [v["id"] for v in create_response.json()["variables"]]
            
            # Verify environment exists
            get_response = client.get(f"/api/environments/{env_id}")
            assert get_response.status_code == 200
            
            # Delete the environment
            delete_response = client.delete(f"/api/environments/{env_id}")
            assert delete_response.status_code == 204
            
            # Verify environment is deleted
            get_response = client.get(f"/api/environments/{env_id}")
            assert get_response.status_code == 404
            
            # Verify variables are also deleted by checking they can't be updated
            for var_id in variable_ids:
                update_response = client.put(
                    f"/api/environments/variables/{var_id}",
                    json={"value": "new_value"}
                )
                assert update_response.status_code == 404

    @given(
        env_name=environment_name_strategy,
        initial_vars=st.lists(variable_strategy, min_size=1, max_size=2),
        added_vars=st.lists(variable_strategy, min_size=1, max_size=2)
    )
    @settings(max_examples=50, deadline=None)
    def test_cascade_delete_includes_dynamically_added_variables(
        self, env_name: str, initial_vars: list[dict], added_vars: list[dict]
    ):
        """
        Property: Cascade delete removes both initial and dynamically added variables.
        """
        with get_test_client() as client:
            # Create environment with initial variables
            create_response = client.post("/api/environments", json={
                "name": env_name,
                "is_active": False,
                "variables": initial_vars
            })
            assert create_response.status_code == 201
            env_id = create_response.json()["id"]
            initial_var_ids = [v["id"] for v in create_response.json()["variables"]]
            
            # Add more variables dynamically
            added_var_ids = []
            for var in added_vars:
                add_response = client.post(
                    f"/api/environments/{env_id}/variables",
                    json=var
                )
                assert add_response.status_code == 201
                added_var_ids.append(add_response.json()["id"])
            
            all_var_ids = initial_var_ids + added_var_ids
            
            # Delete the environment
            delete_response = client.delete(f"/api/environments/{env_id}")
            assert delete_response.status_code == 204
            
            # Verify all variables are deleted
            for var_id in all_var_ids:
                update_response = client.put(
                    f"/api/environments/variables/{var_id}",
                    json={"value": "test"}
                )
                assert update_response.status_code == 404
