"""
Unit tests for the Folder sort_order field.

Tests cover:
- sort_order field exists on Folder model with default value of 0
- sort_order can be set to custom values
- sort_order persists through database round-trip
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api_testing_tool.database import Base
from api_testing_tool.models.collection import Collection, Folder


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test_folder_sort_order.db"
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
    collection = Collection(name=name)
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection


class TestFolderSortOrderField:
    """Tests for the sort_order field on the Folder model."""

    def test_folder_sort_order_defaults_to_zero(self, db):
        """A new folder without explicit sort_order should default to 0."""
        collection = _create_collection(db)
        folder = Folder(name="Test Folder", collection_id=collection.id)
        db.add(folder)
        db.commit()
        db.refresh(folder)
        assert folder.sort_order == 0

    def test_folder_sort_order_can_be_set(self, db):
        """A folder can be created with a custom sort_order value."""
        collection = _create_collection(db)
        folder = Folder(name="Test Folder", collection_id=collection.id, sort_order=5)
        db.add(folder)
        db.commit()
        db.refresh(folder)
        assert folder.sort_order == 5

    def test_folder_sort_order_can_be_updated(self, db):
        """A folder's sort_order can be updated after creation."""
        collection = _create_collection(db)
        folder = Folder(name="Test Folder", collection_id=collection.id)
        db.add(folder)
        db.commit()
        db.refresh(folder)
        assert folder.sort_order == 0

        folder.sort_order = 10
        db.commit()
        db.refresh(folder)
        assert folder.sort_order == 10

    def test_multiple_folders_with_different_sort_orders(self, db):
        """Multiple folders can have different sort_order values."""
        collection = _create_collection(db)
        folders = []
        for i in range(3):
            f = Folder(name=f"Folder {i}", collection_id=collection.id, sort_order=i * 2)
            db.add(f)
            folders.append(f)
        db.commit()
        for f in folders:
            db.refresh(f)

        assert folders[0].sort_order == 0
        assert folders[1].sort_order == 2
        assert folders[2].sort_order == 4

    def test_folder_sort_order_persists_through_query(self, db):
        """sort_order value persists when queried from the database."""
        collection = _create_collection(db)
        folder = Folder(name="Persistent Folder", collection_id=collection.id, sort_order=42)
        db.add(folder)
        db.commit()

        queried_folder = db.query(Folder).filter(Folder.id == folder.id).first()
        assert queried_folder is not None
        assert queried_folder.sort_order == 42
