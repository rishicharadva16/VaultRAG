"""
Standalone script to ingest Northwind database table rows into Qdrant.

Usage:
  python scripts/ingest_db.py
  python scripts/ingest_db.py --collection custom_coll
"""

import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.index.store import SecureStore
from app.ingestion.db_ingestion import ingest_database


def main():
    parser = argparse.ArgumentParser(description="Ingest database table rows into Qdrant")
    parser.add_argument("--collection", default=None, help="Target Qdrant collection")
    parser.add_argument("--db-path", default=None, help="Path to northwind.db")
    args = parser.parse_args()

    coll = args.collection or settings.QDRANT_COLLECTION
    store = SecureStore()

    print(f"Ensuring Qdrant collection {coll} (dense=1024, sparse=BM25)...")
    store.ensure_collection(dense_size=1024, collection=coll)

    print(f"Ingesting database table rows into collection {coll}...")
    results = ingest_database(db_path=args.db_path, store=store, collection=coll)

    print("\n" + "=" * 80)
    print("DATABASE INGESTION SUMMARY")
    print("=" * 80)
    print(f"{'Table':<15} | {'Rows':<6} | {'Base Chunks':<12} | {'Sensitive Chunks':<18} | {'Total Chunks':<12}")
    print("-" * 80)
    total_rows = 0
    total_base = 0
    total_sens = 0
    total_chunks = 0
    for r in results:
        total_rows += r["rows"]
        total_base += r["base_chunks"]
        total_sens += r["sensitive_chunks"]
        total_chunks += r["total_chunks"]
        print(f"{r['table']:<15} | {r['rows']:<6} | {r['base_chunks']:<12} | {r['sensitive_chunks']:<18} | {r['total_chunks']:<12}")
    print("-" * 80)
    print(f"{'TOTAL':<15} | {total_rows:<6} | {total_base:<12} | {total_sens:<18} | {total_chunks:<12}")
    print("=" * 80)

    qdrant_total = store.count(collection=coll)
    print(f"\nTotal points in collection '{coll}': {qdrant_total}")


if __name__ == "__main__":
    main()
