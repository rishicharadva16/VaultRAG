"""
Reset Qdrant collections.

Drops the main and test collections and recreates the main collection
with dense (1024-dim for bge-m3) and sparse vector configs plus payload indexes.

Usage:
  python scripts/reset_collection.py
"""

import sys
from pathlib import Path

# Add backend directory to sys.path so app can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.index.store import SecureStore
from app.index.embedder import DenseEmbedder


def main():
    store = SecureStore()
    print("Checking Qdrant connection...")
    h = store.health()
    if h.get("status") != "ok":
        print(f"Error connecting to Qdrant: {h}")
        sys.exit(1)

    print(f"Dropping collection {settings.QDRANT_COLLECTION}...")
    store.drop_collection(settings.QDRANT_COLLECTION)

    print(f"Dropping test collection {settings.QDRANT_TEST_COLLECTION}...")
    store.drop_collection(settings.QDRANT_TEST_COLLECTION)

    # bge-m3 is 1024 dims
    print(f"Recreating {settings.QDRANT_COLLECTION} with dense=1024 and sparse BM25...")
    store.ensure_collection(dense_size=1024, collection=settings.QDRANT_COLLECTION)

    info = store.get_collection_info(settings.QDRANT_COLLECTION)
    print(f"Collection {settings.QDRANT_COLLECTION} ready:")
    print(f"  Points count: {info.points_count}")
    print(f"  Payload indexes: {list(info.payload_schema.keys()) if info.payload_schema else []}")
    print("Done!")


if __name__ == "__main__":
    main()
