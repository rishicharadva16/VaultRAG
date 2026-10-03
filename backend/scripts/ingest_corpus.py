"""
Ingest corpus documents (PDFs and optional poison files) into Qdrant.

Usage:
  python scripts/ingest_corpus.py
  python scripts/ingest_corpus.py --include-poison
  python scripts/ingest_corpus.py --only hr_policy.pdf
"""

import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.index.store import SecureStore
from app.ingestion.pipeline import ingest_corpus


def main():
    parser = argparse.ArgumentParser(description="Ingest Northwind corpus into Qdrant")
    parser.add_argument("--include-poison", action="store_true", help="Include poisoned test files")
    parser.add_argument("--only", default=None, help="Ingest only a specific file (e.g. hr_policy.pdf)")
    parser.add_argument("--collection", default=None, help="Target Qdrant collection")
    parser.add_argument("--corpus-dir", default=None, help="Custom corpus directory path")
    args = parser.parse_args()

    coll = args.collection or settings.QDRANT_COLLECTION
    store = SecureStore()

    print(f"Ensuring Qdrant collection {coll} (dense=1024, sparse=BM25)...")
    store.ensure_collection(dense_size=1024, collection=coll)

    print(f"Starting corpus ingestion (include_poison={args.include_poison}, only={args.only})...")
    results = ingest_corpus(
        root=args.corpus_dir,
        store=store,
        collection=coll,
        include_poison=args.include_poison,
        only=args.only,
    )

    print(f"\nIngested {len(results)} document(s):")
    total_chunks = 0
    for r in results:
        total_chunks += r["total_chunks"]
        print(f"  • {r['file_name']:<42} [{r['corpus']}] chunks: {r['total_chunks']} (text: {r['text_chunks']}, table: {r['table_chunks']})")
        print(f"    ACL tokens: {', '.join(r['acl_tokens'])}")

    qdrant_total = store.count(collection=coll)
    print(f"\nTotal chunks ingested this run: {total_chunks}")
    print(f"Total points in collection {coll}: {qdrant_total}")


if __name__ == "__main__":
    main()
