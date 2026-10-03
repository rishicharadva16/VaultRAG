"""Create all database tables (idempotent)."""

import sys
import os

# Add backend to path so `app` is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.models import Base
from app.db.session import engine


def create_tables():
    print("Creating tables …")
    Base.metadata.create_all(bind=engine)
    print("Done.")


if __name__ == "__main__":
    create_tables()
