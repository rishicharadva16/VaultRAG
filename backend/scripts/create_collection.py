"""
Create / ensure the VaultRAG Qdrant collection with named dense + sparse vectors and payload indexes.

Usage: python scripts/create_collection.py [--collection <name>]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.index.embedder import DenseEmbedder
from app.index.store import SecureStore


def main():
    parser = argparse.ArgumentParser(description="Create / ensure Qdrant collection for VaultRAG")
    parser.add_argument("--collection", default=None, help="Collection name (default: from config)")
    args = parser.parse_args()

    coll_name = args.collection or settings.QDRANT_COLLECTION
    print(f"Connecting to Qdrant at {settings.QDRANT_URL} ...")
    store = SecureStore()
    health = store.health()
    if health.get("status") != "ok":
        print(f"ERROR: Qdrant health check failed: {health.get('detail')}")
        sys.exit(1)

    print(f"Loading embedding model '{settings.EMBED_MODEL}' to determine dimension...")
    embedder = DenseEmbedder()
    dense_size = embedder.dense_size
    print(f"Dense vector dimension: {dense_size}")

    print(f"Ensuring collection {coll_name!r} with dense size {dense_size} and sparse BM25 vectors...")
    store.ensure_collection(dense_size=dense_size, collection=coll_name)
    print(f"Collection {coll_name!r} created / verified successfully with all payload indexes.")


if __name__ == "__main__":
    main()
