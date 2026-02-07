"""
Database configuration and initialization for API Testing Tool.

Uses SQLite as the data storage backend with SQLAlchemy ORM.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# SQLite database URL - file-based storage
DATABASE_URL = "sqlite:///./api_testing_tool.db"

# Create engine with SQLite-specific settings
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite with FastAPI
    echo=False  # Set to True for SQL query logging
)


# Enable foreign key support for SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key constraints for SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


def init_db():
    """
    Initialize the database by creating all tables.
    
    This function should be called at application startup to ensure
    the database schema exists. It will create tables if they don't exist.
    """
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    Dependency function for FastAPI to get database sessions.
    
    Yields a database session and ensures it's closed after use.
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
