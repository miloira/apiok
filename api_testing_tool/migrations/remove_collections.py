"""
Migration: Remove collections table and collection_id from folders and requests.

Since SQLite doesn't support DROP COLUMN, we recreate the tables without collection_id.
"""

from sqlalchemy import inspect, text
from api_testing_tool.database import engine


def migrate():
    """Remove collection_id from folders and requests tables, drop collections table."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "collections" not in tables:
        print("Migration skipped: collections table does not exist.")
        return

    with engine.begin() as conn:
        # --- Recreate folders table without collection_id ---
        folder_columns = [col["name"] for col in inspector.get_columns("folders")]
        if "collection_id" in folder_columns:
            conn.execute(text("""
                CREATE TABLE folders_new (
                    id INTEGER PRIMARY KEY,
                    parent_folder_id INTEGER REFERENCES folders_new(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
                )
            """))
            conn.execute(text("""
                INSERT INTO folders_new (id, parent_folder_id, name, sort_order, created_at, updated_at)
                SELECT id, parent_folder_id, name, sort_order, created_at, updated_at FROM folders
            """))
            conn.execute(text("DROP TABLE folders"))
            conn.execute(text("ALTER TABLE folders_new RENAME TO folders"))
            print("Migration: Removed collection_id from folders table.")

        # --- Recreate requests table without collection_id ---
        request_columns = [col["name"] for col in inspector.get_columns("requests")]
        if "collection_id" in request_columns:
            conn.execute(text("""
                CREATE TABLE requests_new (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    method VARCHAR(10) NOT NULL,
                    url TEXT NOT NULL,
                    headers JSON DEFAULT '{}',
                    query_params JSON DEFAULT '{}',
                    body_type VARCHAR(20),
                    body TEXT,
                    folder_id INTEGER REFERENCES folders(id) ON DELETE CASCADE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                    updated_at DATETIME NOT NULL DEFAULT (CURRENT_TIMESTAMP)
                )
            """))
            conn.execute(text("""
                INSERT INTO requests_new (id, name, method, url, headers, query_params, body_type, body, folder_id, sort_order, created_at, updated_at)
                SELECT id, name, method, url, headers, query_params, body_type, body, folder_id, sort_order, created_at, updated_at FROM requests
            """))
            conn.execute(text("DROP TABLE requests"))
            conn.execute(text("ALTER TABLE requests_new RENAME TO requests"))
            print("Migration: Removed collection_id from requests table.")

        # --- Drop collections table ---
        conn.execute(text("DROP TABLE IF EXISTS collections"))
        print("Migration: Dropped collections table.")

    print("Migration complete: Collections removed.")


if __name__ == "__main__":
    migrate()
