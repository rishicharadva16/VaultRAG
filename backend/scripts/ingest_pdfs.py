"""
Ingest PDF documents into VaultRAG vector store with ACL tagging.

Usage: python scripts/ingest_pdfs.py [--folder <path>] [--collection <name>]
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.db.session import SessionLocal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.store import SecureStore
from app.ingestion.pipeline import ingest_folder


def main():
    parser = argparse.ArgumentParser(description="Ingest PDF documents into VaultRAG")
    parser.add_argument(
        "--folder",
        default=str(Path(__file__).resolve().parent.parent.parent / "data" / "pdfs"),
        help="Folder containing PDF files",
    )
    parser.add_argument("--collection", default=None, help="Target Qdrant collection")
    args = parser.parse_args()

    folder_path = Path(args.folder)
    if not folder_path.exists():
        print(f"ERROR: Folder {folder_path} does not exist. Run scripts/make_demo_pdfs.py first.")
        sys.exit(1)

    print(f"Starting ingestion from: {folder_path}")
    store = SecureStore()
    embedder = DenseEmbedder()
    sparse = SparseEmbedder()
    db = SessionLocal()

    try:
        # Ensure collection exists before ingestion
        store.ensure_collection(dense_size=embedder.dense_size, collection=args.collection)

        results = ingest_folder(
            folder_path=folder_path,
            store=store,
            embedder=embedder,
            sparse=sparse,
            collection=args.collection,
            db=db,
        )

        if not results:
            print(f"No PDF files found in {folder_path}")
            return

        print()
        print(f"  {'Doc ID':<24} {'Pages':>5} {'Text':>5} {'Table':>6} {'Clr':>3} {'Roles':<20} {'Empty Pages'}")
        print(f"  {'-'*24} {'-'*5} {'-'*5} {'-'*6} {'-'*3} {'-'*20} {'-'*11}")

        total_chunks = 0
        for r in results:
            roles_str = ",".join(r["allowed_roles"]) if r["allowed_roles"] else "(none)"
            empty_str = str(r["empty_pages"]) if r["empty_pages"] else "None"
            total_chunks += r["total_chunks"]
            print(
                f"  {r['doc_id']:<24} {r['pages']:>5} {r['text_chunks']:>5} "
                f"{r['table_chunks']:>6} {r['classification']:>3} {roles_str:<20} {empty_str}"
            )

        print(f"\nIngested {len(results)} document(s), {total_chunks} total chunk(s) stored.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
