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
    parser.add_argument("--include-db", action="store_true", help="Include database table row ingestion")
    parser.add_argument("--include-images", action="store_true", help="Include corpus image OCR ingestion")
    parser.add_argument("--only", default=None, help="Ingest only a specific file (e.g. hr_policy.pdf)")
    parser.add_argument("--collection", default=None, help="Target Qdrant collection")
    parser.add_argument("--corpus-dir", default=None, help="Custom corpus directory path")
    args = parser.parse_args()

    coll = args.collection or settings.QDRANT_COLLECTION
    store = SecureStore()

    print(f"Ensuring Qdrant collection {coll} (dense=1024, sparse=BM25)...")
    store.ensure_collection(dense_size=1024, collection=coll)

    total_chunks = 0
    if not args.only or not args.only.startswith("db:"):
        print(f"Starting corpus ingestion (include_poison={args.include_poison}, only={args.only})...")
        results = ingest_corpus(
            root=args.corpus_dir,
            store=store,
            collection=coll,
            include_poison=args.include_poison,
            only=args.only,
        )

        print(f"\nIngested {len(results)} document(s):")
        for r in results:
            total_chunks += r["total_chunks"]
            print(f"  • {r['file_name']:<42} [{r['corpus']}] chunks: {r['total_chunks']} (text: {r['text_chunks']}, table: {r['table_chunks']})")
            print(f"    ACL tokens: {', '.join(r['acl_tokens'])}")

    if args.include_db:
        from app.ingestion.db_ingestion import ingest_database

        print(f"\nStarting database row ingestion into {coll}...")
        db_results = ingest_database(store=store, collection=coll)
        print(f"\nIngested {len(db_results)} database table(s):")
        for dr in db_results:
            total_chunks += dr["total_chunks"]
            print(
                f"  • {dr['table']:<15} rows: {dr['rows']}, chunks: {dr['total_chunks']} "
                f"(base: {dr['base_chunks']}, sensitive: {dr['sensitive_chunks']})"
            )

    if args.include_images or (args.only and (args.only.startswith("img:") or any(args.only.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")))):
        from app.ingestion.image_ingestion import ingest_images_corpus

        print(f"\nStarting image corpus OCR ingestion into {coll}...")
        img_results = ingest_images_corpus(store=store, collection=coll, only=args.only)
        print(f"\nIngested {len(img_results)} image(s):")
        for ir in img_results:
            total_chunks += ir["total_chunks"]
            print(
                f"  • {ir['file_name']:<35} lines: {ir['ocr_lines']:<2} "
                f"conf: {ir['mean_confidence']:<5.3f} chunks: {ir['total_chunks']} ({ir['elapsed_seconds']}s)"
            )
            print(f"    ACL tokens: {', '.join(ir['acl_tokens'])}")

    qdrant_total = store.count(collection=coll)
    print(f"\nTotal chunks ingested this run: {total_chunks}")
    print(f"Total points in collection {coll}: {qdrant_total}")


if __name__ == "__main__":
    main()
