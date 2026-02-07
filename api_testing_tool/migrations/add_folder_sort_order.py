"""
Migration: Add sort_order column to folders table.

This migration adds the sort_order integer column to the folders table
with a default value of 0, enabling custom ordering of folders.
"""

from sqlalchemy import inspect, text
from api_testing_tool.database import engine


def migrate():
    """Add sort_order column to folders table if it doesn't exist."""
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("folders")]
    
    if "sort_order" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE folders ADD COLUMN sort_order INTEGER DEFAULT 0 NOT NULL")
            )
        print("Migration complete: Added sort_order column to folders table.")
    else:
        print("Migration skipped: sort_order column already exists in folders table.")


if __name__ == "__main__":
    migrate()
