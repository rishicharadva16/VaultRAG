"""
Inspect stored chunks in Qdrant (read helper for verification and debugging).

Usage: python scripts/inspect_chunks.py [--doc-id <slug>] [--limit 5] [--collection <name>]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
        page = payload.get("page", "N/A")
        source_name = payload.get("source_name", "N/A")
        roles = payload.get("allowed_roles", [])
        roles_str = ",".join(roles) if roles else "(none)"
        classification = payload.get("classification", "N/A")
        is_public = payload.get("is_public", False)
        text = payload.get("text", "")
        snippet = text.replace("\n", " ").strip()[:80] + ("..." if len(text) > 80 else "")

        print(f"[{idx}] Chunk ID: {chunk_id}")
        print(f"    Page: {page} | Source: {source_name} | Clr: {classification} | Public: {is_public}")
        print(f"    Allowed Roles: {roles_str}")
        print(f"    Text Preview: {snippet}")
        print()


if __name__ == "__main__":
    main()
