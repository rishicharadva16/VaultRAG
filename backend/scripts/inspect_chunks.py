"""
Inspect stored chunks in Qdrant (read helper for verification and debugging).

Usage:
  python scripts/inspect_chunks.py [--doc-id <slug>] [--limit 5] [--collection <name>]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.index.store import SecureStore


def main():
    parser = argparse.ArgumentParser(description="Inspect chunks stored in Qdrant")
    parser.add_argument("--doc-id", default=None, help="Filter by document id")
    parser.add_argument("--limit", type=int, default=5, help="Number of chunks to display (default: 5)")
    parser.add_argument("--collection", default=None, help="Target Qdrant collection")
    args = parser.parse_args()

    store = SecureStore()
    coll_name = args.collection or settings.QDRANT_COLLECTION

    total_count = store.count(doc_id=args.doc_id, collection=coll_name)
    print(f"Total chunks in {coll_name!r}" + (f" for doc_id={args.doc_id!r}" if args.doc_id else "") + f": {total_count}")

    if total_count == 0:
        print("No chunks found.")
        return

    points = store.admin_scroll(limit=args.limit, doc_id=args.doc_id, collection=coll_name)
    print(f"\nShowing {len(points)} chunk(s):\n")

    for idx, pt in enumerate(points, 1):
        payload = pt.payload or {}
        chunk_id = payload.get("chunk_id", "N/A")
        source_id = payload.get("source_id", "N/A")
        source_doc = payload.get("source_doc", "N/A")
        tokens = payload.get("acl_tokens", [])
        tokens_str = ", ".join(tokens) if tokens else "(none)"
        corpus = payload.get("corpus", "main")
        page = payload.get("page", "N/A")
        text = payload.get("text", "")
        snippet = text.replace("\n", " ").strip()[:80] + ("..." if len(text) > 80 else "")

        print(f"[{idx}] Chunk ID: {chunk_id}")
        print(f"    Source ID: {source_id} | File: {source_doc} | Corpus: {corpus} | Page: {page}")
        print(f"    ACL Tokens: {tokens_str}")
        print(f"    Text Preview: {snippet}")
        print()


if __name__ == "__main__":
    main()
