"""
Compare search results across seeded dataset users.

Demonstrates that different users receive different, authorized results
for the same question based on document-level access control.

Usage:
  python scripts/compare_users.py "question" [--top-k 5] [--rerank]
"""

import argparse
import importlib.util
import os
import sys
from pathlib import Path

# CRITICAL: Prevent bytecode generation in read-only data directory
sys.dont_write_bytecode = True

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.index.store import SecureStore
from app.rag.reranker import Reranker
from app.security.principals import build_principal

# Load reference acl.py for validation
dataset_dir = settings.dataset_path()
acl_py_path = dataset_dir / "acl.py"
if not acl_py_path.exists():
    raise FileNotFoundError(f"Reference acl.py not found at {acl_py_path}")

spec = importlib.util.spec_from_file_location("dataset_acl", str(acl_py_path))
dataset_acl = importlib.util.module_from_spec(spec)
sys.modules["dataset_acl"] = dataset_acl
if str(dataset_dir) not in sys.path:
    sys.path.insert(0, str(dataset_dir))
spec.loader.exec_module(dataset_acl)

USER_ORDER = ["u_asha", "u_neha", "u_ravi", "u_dev", "u_meera", "u_karan", "u_admin"]


def main():
    parser = argparse.ArgumentParser(description="Compare search results across users")
    parser.add_argument("question", help="Question or query string to search")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results (default: 5)")
    parser.add_argument("--rerank", action="store_true", help="Enable cross-encoder reranking")
    args = parser.parse_args()

    store = SecureStore()
    reranker = Reranker() if args.rerank else None

    db = SessionLocal()
    users_by_ext = {u.external_id: u for u in db.query(User).all() if u.external_id}

    print("=" * 105)
    print(f"Query: {args.question!r}")
    print(f"Top-K: {args.top_k} | Rerank: {args.rerank}")
    print("=" * 105)
    print(f"{'User':<10} | {'Role':<15} | {'Results':<7} | {'Top Sources (Source ID:Page)':<65}")
    print("-" * 105)

    violations = []

    for ext_id in USER_ORDER:
        user = users_by_ext.get(ext_id)
        if not user:
            print(f"{ext_id:<10} | {'MISSING IN DB':<15} | {0:<7} | -")
            continue

        role_str = user.roles[0] if user.roles else "none"
        principal = build_principal(user)

        results = store.search(
            principal=principal,
            query=args.question,
            top_k=args.top_k,
            include_poison=False,
        )

        if args.rerank and results:
            results = reranker.rerank(query=args.question, results=results, top_k=args.top_k)

        # Check for any ACL leaks against reference acl.py
        for r in results:
            if ext_id == "u_admin":
                violations.append((ext_id, r.source_id, r.chunk_id))
            elif not dataset_acl.can_read_source(ext_id, r.source_id):
                violations.append((ext_id, r.source_id, r.chunk_id))

        if results:
            src_parts = []
            for r in results:
                page_str = f"p{r.page}" if r.page else "?"
                src_parts.append(f"{r.source_id}:{page_str}")
            top_sources_str = ", ".join(src_parts)
            if len(top_sources_str) > 63:
                top_sources_str = top_sources_str[:60] + "..."
        else:
            top_sources_str = "(none)"

        print(f"{ext_id:<10} | {role_str:<15} | {len(results):<7} | {top_sources_str:<65}")

    print("=" * 105)
    if violations:
        print(f"\n[ERROR] FOUND {len(violations)} ACL VIOLATION(S):")
        for u, src, chk in violations:
            print(f"  - User {u} illegally retrieved {src} (chunk: {chk})")
        sys.exit(1)
    else:
        print("[SUCCESS] 0 ACL violations detected across all accounts.")


if __name__ == "__main__":
    main()
