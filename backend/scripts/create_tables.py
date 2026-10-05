"""Create all database tables and apply migrations (idempotent)."""

import os
import sys

# Add backend to path so `app` is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.db.models import Base
from app.db.session import engine


def create_tables():
    print("Creating tables …")
    Base.metadata.create_all(bind=engine)

    # Idempotent migration for Northwind user attributes
    print("Applying migrations for Northwind employee fields …")
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_id VARCHAR;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS external_id VARCHAR;"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_external_id ON users (external_id);"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS clearance;"))
        conn.commit()

    print("Done.")


if __name__ == "__main__":
    create_tables()
