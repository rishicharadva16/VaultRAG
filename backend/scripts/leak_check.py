"""
Security leak check and retrieval accuracy audit.

Runs all eval questions and adversarial attack queries as every seeded user.
Verifies with reference acl.py that zero unauthorized chunks are ever returned.
Reports hit@1, hit@3, and hit@5 for authorized queries.
Exits with code 1 if any ACL violation is detected.

Usage:
  python scripts/leak_check.py [--top-k 5] [--rerank]
"""

import argparse
import importlib.util
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# CRITICAL: Prevent bytecode generation in read-only data directory
sys.dont_write_bytecode = True

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.store import SecureStore
from app.rag.reranker import Reranker
from app.security.principals import build_principal

# Load reference acl.py dynamically without writing bytecode
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


def parse_expected_source(raw_source: str) -> tuple[str, int | None]:
    """Parse 'pdf:hr_policy.pdf#p2' into ('pdf:hr_policy.pdf', 2)."""
    if "#p" in raw_source:
        parts = raw_source.split("#p")
        return parts[0], int(parts[1]) if parts[1].isdigit() else None
    return raw_source, None


def main():
    parser = argparse.ArgumentParser(description="Audit ACL security and retrieval metrics")
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieved chunks (default: 5)")
    parser.add_argument("--rerank", action="store_true", help="Enable cross-encoder reranker")
    args = parser.parse_args()

    # Load dataset evaluation questions and adversarial queries
    eval_q_file = dataset_dir / "dataset" / "eval" / "eval_questions.json"
    adv_q_file = dataset_dir / "dataset" / "eval" / "adversarial_queries.json"

    with open(eval_q_file, "r", encoding="utf-8") as f:
        eval_questions = json.load(f)

    with open(adv_q_file, "r", encoding="utf-8") as f:
        adv_data = json.load(f)
        adv_attacks = adv_data.get("attacks", [])

    print("=" * 95)
    print("VaultRAG Comprehensive Security Leak & Retrieval Audit")
    print(f"Eval Questions: {len(eval_questions)} | Adversarial Queries: {len(adv_attacks)}")
    print(f"Top-K: {args.top_k} | Rerank: {args.rerank}")
    print("=" * 95)

    # Initialize store, embedders, and reranker
    store = SecureStore()
    dense_embedder = DenseEmbedder()
    sparse_embedder = SparseEmbedder()
    reranker = Reranker() if args.rerank else None

    # Load users from DB and build principals
    db = SessionLocal()
    db_users = {u.external_id: u for u in db.query(User).all() if u.external_id}
    principals = {uid: build_principal(db_users[uid]) for uid in USER_ORDER if uid in db_users}

    # Collect all queries to run
    # Format: list of dict(query=..., q_id=..., authorized_user=..., expected_sources=..., is_eval=...)
    test_queries = []
    for q in eval_questions:
        test_queries.append({
            "q_id": q.get("id"),
            "query": q["question"],
            "authorized_user": q.get("user_id"),
            "access_expected": q.get("access_expected", "allow"),
            "expected_sources": q.get("expected_sources", []),
            "type": q.get("type", "unknown"),
            "is_eval": True,
        })

    for a in adv_attacks:
        test_queries.append({
            "q_id": a.get("id"),
            "query": a["query"],
            "authorized_user": a.get("user_id"),
            "access_expected": "deny",
            "expected_sources": [],
            "type": a.get("category", "adversarial"),
            "is_eval": False,
        })

    # Stats tracking per user
    user_stats = {
        uid: {
            "queries_run": 0,
            "chunks_inspected": 0,
            "violations": [],
            "hit1": 0,
            "hit3": 0,
            "hit5": 0,
            "eval_count": 0,
        }
        for uid in USER_ORDER
    }

    total_chunks_inspected = 0
    total_violations = 0
    all_violations = []

    print(f"\nRunning {len(test_queries)} queries across {len(USER_ORDER)} users ({len(test_queries) * len(USER_ORDER)} total searches)...")

    # To optimize runtime, pre-encode each query once
    for idx, tq in enumerate(test_queries, 1):
        q_text = tq["query"].strip()[:500]
        if not q_text:
            continue

        dvec = dense_embedder.embed_query(q_text)
        svec = sparse_embedder.embed_sparse_query(q_text)
        query_vectors = (dvec, svec)

        for uid in USER_ORDER:
            principal = principals.get(uid)
            if not principal:
                continue

            results = store.search(
                principal=principal,
                query=query_vectors,
                top_k=args.top_k,
                include_poison=False,
            )

            if args.rerank and results:
                results = reranker.rerank(query=q_text, results=results, top_k=args.top_k)

            user_stats[uid]["queries_run"] += 1
            user_stats[uid]["chunks_inspected"] += len(results)
            total_chunks_inspected += len(results)

            # Check ACL for every returned chunk
            for r in results:
                has_access = False
                if uid != "u_admin" and dataset_acl.can_read_source(uid, r.source_id):
                    has_access = True

                if not has_access:
                    viol = {
                        "user": uid,
                        "query_id": tq["q_id"],
                        "query": q_text[:80],
                        "source_id": r.source_id,
                        "chunk_id": r.chunk_id,
                    }
                    user_stats[uid]["violations"].append(viol)
                    all_violations.append(viol)
                    total_violations += 1

            # Hit@K evaluation for authorized asker on eval questions
            if (
                tq["is_eval"]
                and tq["access_expected"] == "allow"
                and tq["authorized_user"] == uid
                and tq["expected_sources"]
            ):
                # Filter to expected sources in current corpus (PDFs)
                expected_parsed = [parse_expected_source(es) for es in tq["expected_sources"]]
                pdf_expected = [ep for ep in expected_parsed if ep[0].startswith("pdf:")]

                if pdf_expected:
                    user_stats[uid]["eval_count"] += 1

                    # Check hit@1
                    h1 = False
                    if results:
                        top1 = results[0]
                        for exp_src, exp_page in pdf_expected:
                            if top1.source_id == exp_src and (exp_page is None or top1.page == exp_page):
                                h1 = True
                                break
                    if h1:
                        user_stats[uid]["hit1"] += 1

                    # Check hit@3
                    h3 = False
                    for r in results[:3]:
                        for exp_src, exp_page in pdf_expected:
                            if r.source_id == exp_src and (exp_page is None or r.page == exp_page):
                                h3 = True
                                break
                    if h3:
                        user_stats[uid]["hit3"] += 1

                    # Check hit@5
                    h5 = False
                    for r in results[:5]:
                        for exp_src, exp_page in pdf_expected:
                            if r.source_id == exp_src and (exp_page is None or r.page == exp_page):
                                h5 = True
                                break
                    if h5:
                        user_stats[uid]["hit5"] += 1

    print("\n" + "=" * 95)
    print("AUDIT RESULTS BY USER")
    print("=" * 95)
    print(f"{'User':<10} | {'Role':<15} | {'Searches':<9} | {'Chunks':<8} | {'Violations':<10} | {'Hit@1':<8} | {'Hit@3':<8} | {'Hit@5':<8}")
    print("-" * 95)

    tot_eval = 0
    tot_h1 = 0
    tot_h3 = 0
    tot_h5 = 0

    for uid in USER_ORDER:
        st = user_stats[uid]
        db_u = db_users.get(uid)
        role = db_u.roles[0] if db_u and db_u.roles else "none"
        ec = st["eval_count"]
        tot_eval += ec
        tot_h1 += st["hit1"]
        tot_h3 += st["hit3"]
        tot_h5 += st["hit5"]

        h1_str = f"{st['hit1']}/{ec} ({st['hit1']/ec:.1%})" if ec else "N/A"
        h3_str = f"{st['hit3']}/{ec} ({st['hit3']/ec:.1%})" if ec else "N/A"
        h5_str = f"{st['hit5']}/{ec} ({st['hit5']/ec:.1%})" if ec else "N/A"

        print(f"{uid:<10} | {role:<15} | {st['queries_run']:<9} | {st['chunks_inspected']:<8} | {len(st['violations']):<10} | {h1_str:<8} | {h3_str:<8} | {h5_str:<8}")

    print("=" * 95)
    print(f"TOTAL SEARCH CHECKS PERFORMED : {len(test_queries) * len(USER_ORDER)}")
    print(f"TOTAL CHUNKS INSPECTED        : {total_chunks_inspected}")
    print(f"TOTAL ACL VIOLATIONS          : {total_violations}")
    if tot_eval > 0:
        print(f"OVERALL HIT@1 (PDF Queries)   : {tot_h1}/{tot_eval} ({tot_h1/tot_eval:.1%})")
        print(f"OVERALL HIT@3 (PDF Queries)   : {tot_h3}/{tot_eval} ({tot_h3/tot_eval:.1%})")
        print(f"OVERALL HIT@5 (PDF Queries)   : {tot_h5}/{tot_eval} ({tot_h5/tot_eval:.1%})")
    print("=" * 95)

    if total_violations > 0:
        print(f"\n[FAILURE] {total_violations} ACL VIOLATION(S) DETECTED:")
        for v in all_violations:
            print(f"  * User {v['user']} in query {v['query_id']} got {v['source_id']} ({v['chunk_id']})")
        sys.exit(1)
    else:
        print("\n[SUCCESS] ZERO ACL VIOLATIONS: SecureStore perfectly enforced access control across all queries!")


if __name__ == "__main__":
    main()
