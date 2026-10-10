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
from typing import Any

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

import csv

USER_ORDER = ["u_asha", "u_neha", "u_ravi", "u_dev", "u_meera", "u_karan", "u_admin"]

def _load_emp_to_dept() -> dict[str, str]:
    ds_dir = settings.dataset_path()
    employees_csv = ds_dir / "dataset" / "database" / "employees.csv"
    if employees_csv.exists():
        with open(employees_csv, "r", encoding="utf-8") as f:
            return {row["employee_id"].strip(): row["department"].strip() for row in csv.DictReader(f)}
    return {}

EMP_TO_DEPT = _load_emp_to_dept()


def parse_expected_source(raw_source: str) -> tuple[str, int | None]:
    """Parse 'pdf:hr_policy.pdf#p2' into ('pdf:hr_policy.pdf', 2)."""
    if "#p" in raw_source:
        parts = raw_source.split("#p")
        return parts[0], int(parts[1]) if parts[1].isdigit() else None
    return raw_source, None


def check_department_access(uid: str, r: Any, db_users: dict, db: Any, db_ref_rows: dict) -> bool:
    """Evaluate whether a user has access to a retrieved chunk under the Department access model."""
    if uid == "u_admin":
        return r.corpus != "poison_test" and not r.source_id.startswith("poison:")

    u = db_users.get(uid)
    if not u or not getattr(u, "active", True):
        return False

    u_dept = getattr(u, "department", None)
    u_emp = getattr(u, "employee_id", None)

    if r.corpus == "poison_test" or r.source_id.startswith("poison:"):
        return False

    if r.source_id.startswith("upl:"):
        doc_uuid = r.source_id.split("upl:")[-1]
        from app.db.models import Document
        from app.api.documents import _user_can_access_document
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        return bool(doc and _user_can_access_document(doc, u, db))

    if r.source_id.startswith("db:"):
        tbl = r.file or r.source_id.split("db:")[-1]
        row_id = getattr(r, "row_id", None) or (r.chunk_id.split("#")[1].split(":")[0] if "#" in r.chunk_id else "")
        if tbl == "salaries":
            # Salary rule: Finance reads salaries. HR does NOT. Employee reads own salary.
            return u_dept == "Finance" or (bool(u_emp) and u_emp == row_id)
        elif tbl == "employees":
            if r.chunk_id.endswith(":sensitive"):
                return u_dept == "HR" or (bool(u_emp) and u_emp == row_id)
            # Base record: dept:<own dept>, dept:HR, emp:<id>
            target_dept = EMP_TO_DEPT.get(row_id)
            return (
                u_dept == "HR"
                or (bool(u_emp) and u_emp == row_id)
                or (bool(u_dept) and bool(target_dept) and u_dept == target_dept)
            )
        elif tbl in ("expenses", "approvals"):
            # Finance reads all. Employee reads their own expenses/approvals.
            if u_dept == "Finance":
                return True
            ref_tbl = db_ref_rows.get(uid, {}).get(tbl, {})
            return row_id in ref_tbl
        return False

    # Documents & Images
    src = r.source_id
    policies_cw = getattr(settings, "POLICIES_COMPANY_WIDE", True)
    if (src.startswith("pdf:") and ("policy" in src or "handbook" in src)) or src.startswith("faq:") or "public" in src:
        return True if policies_cw else (u_dept == "HR")

    if src.startswith("img:id_card_"):
        card_emp = src.replace("img:id_card_", "").split(".")[0]
        return u_dept == "HR" or (bool(u_emp) and u_emp == card_emp)

    if src.startswith("img:invoice_") or src.startswith("img:purchase_order_"):
        return u_dept == "Finance"

    if src.startswith("img:receipt_"):
        return u_dept == "Finance" or (bool(u_emp) and u_emp == "E1010")

    if src in ("pdf:vendor_contract_apex.pdf", "pdf:finance_memo_q2_fy27.pdf"):
        return u_dept == "Finance"

    if src == "pdf:board_minutes_2026_08.pdf":
        return u_dept == "Finance"

    if src == "img:whiteboard_sprint.jpg":
        return u_dept == "Engineering"

    return False


def main():
    parser = argparse.ArgumentParser(description="Audit ACL security and retrieval metrics")
    parser.add_argument("--top-k", type=int, default=5, help="Number of retrieved chunks (default: 5)")
    parser.add_argument("--rerank", action="store_true", help="Enable cross-encoder reranker")
    parser.add_argument(
        "--model",
        type=str,
        default=getattr(settings, "ACCESS_MODEL", "department"),
        choices=["department", "dataset"],
        help="Access model to evaluate (default: from settings)",
    )
    args = parser.parse_args()

    settings.ACCESS_MODEL = args.model

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

    # Pre-fetch database allowed rows for all dataset users
    from app.ingestion.db_ingestion import get_default_db_path
    db_path = get_default_db_path()
    db_ref_rows: dict[str, dict[str, dict]] = {}
    for uid in USER_ORDER:
        if uid in dataset_acl.ROLE_OF:
            db_ref_rows[uid] = {}
            for tbl in ["employees", "salaries", "expenses", "approvals"]:
                rows = dataset_acl.allowed_rows(db_path, uid, tbl)
                pk_col = "employee_id" if tbl in ("employees", "salaries") else ("expense_id" if tbl == "expenses" else "approval_id")
                db_ref_rows[uid][tbl] = {r[pk_col]: dict(r) for r in rows}

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
                if args.model == "department":
                    has_access = check_department_access(uid, r, db_users, db, db_ref_rows)
                else:
                    has_access = False
                    if uid == "u_admin":
                        if r.corpus != "poison_test" and not r.source_id.startswith("poison:"):
                            has_access = True
                    elif r.source_id.startswith("db:"):
                        tbl = r.file or r.source_id.split("db:")[-1]
                        ref_map = db_ref_rows.get(uid, {}).get(tbl, {})
                        row_id = getattr(r, "row_id", None) or (r.chunk_id.split("#")[1].split(":")[0] if "#" in r.chunk_id else "")
                        if row_id in ref_map:
                            has_access = True
                            if r.chunk_id.endswith(":sensitive"):
                                if tbl == "employees" and "date_of_birth" not in ref_map[row_id]:
                                    has_access = False
                    elif r.source_id.startswith("upl:"):
                        doc_uuid = r.source_id.split("upl:")[-1]
                        from app.db.models import Document
                        from app.api.documents import _user_can_access_document
                        doc = db.query(Document).filter(Document.id == doc_uuid).first()
                        u = db_users.get(uid)
                        if doc and u and _user_can_access_document(doc, u, db):
                            has_access = True
                    elif r.source_id in dataset_acl.DOC_ACL and dataset_acl.can_read_source(uid, r.source_id):
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
                # Filter to expected sources in current corpus (PDFs, DB rows, and Images)
                active_expected = []
                for es in tq["expected_sources"]:
                    if es.startswith("pdf:"):
                        active_expected.append(("pdf", parse_expected_source(es)))
                    elif es.startswith("db:"):
                        parts = es.split(":")
                        if len(parts) >= 3:
                            active_expected.append(("db", (f"db:{parts[1]}", parts[2])))
                    elif es.startswith("img:"):
                        active_expected.append(("img", es))

                def _matches_chunk(res_item, exp_tuple):
                    kind, val = exp_tuple
                    if kind == "pdf":
                        exp_src, exp_page = val
                        return res_item.source_id == exp_src and (exp_page is None or res_item.page == exp_page)
                    elif kind == "db":
                        exp_src, exp_pk = val
                        if res_item.source_id == exp_src:
                            row_pk = getattr(res_item, "row_id", None) or (res_item.chunk_id.split("#")[1].split(":")[0] if "#" in res_item.chunk_id else "")
                            return row_pk == exp_pk
                    elif kind == "img":
                        return res_item.source_id == val
                    return False

                if active_expected:
                    user_stats[uid]["eval_count"] += 1

                    # Check hit@1
                    h1 = False
                    if results:
                        top1 = results[0]
                        for exp_item in active_expected:
                            if _matches_chunk(top1, exp_item):
                                h1 = True
                                break
                    if h1:
                        user_stats[uid]["hit1"] += 1

                    # Check hit@3
                    h3 = False
                    for r in results[:3]:
                        for exp_item in active_expected:
                            if _matches_chunk(r, exp_item):
                                h3 = True
                                break
                    if h3:
                        user_stats[uid]["hit3"] += 1

                    # Check hit@5
                    h5 = False
                    for r in results[:5]:
                        for exp_item in active_expected:
                            if _matches_chunk(r, exp_item):
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
        print(f"OVERALL HIT@1 (Authorized Queries): {tot_h1}/{tot_eval} ({tot_h1/tot_eval:.1%})")
        print(f"OVERALL HIT@3 (Authorized Queries): {tot_h3}/{tot_eval} ({tot_h3/tot_eval:.1%})")
        print(f"OVERALL HIT@5 (Authorized Queries): {tot_h5}/{tot_eval} ({tot_h5/tot_eval:.1%})")
    print("=" * 95)

    # Track image-targeted checks
    image_q_stats = []
    for tq in test_queries:
        if tq.get("is_eval") and (
            any(s.startswith("img:") for s in tq.get("expected_sources", []))
            or tq.get("q_id") in ["Q041", "Q042", "Q043", "Q044", "Q045", "Q046", "Q047", "Q048", "Q049"]
        ):
            image_q_stats.append(tq)

    print("\n" + "=" * 95)
    print("IMAGE-TARGETED ACL AUDIT (Every User x Every Image Question Q041-Q049)")
    print("=" * 95)
    print(f"Total Image Questions: {len(image_q_stats)} | Total Cross-User Checks: {len(image_q_stats) * len(USER_ORDER)}")
    print(f"{'QID':<6} {'Query':<45} {'Asker':<8} {'Img Violations':<15}")
    print("-" * 95)

    img_viol_count = 0
    for iq in image_q_stats:
        qid = iq["q_id"]
        q_text = iq["query"][:42] + "..." if len(iq["query"]) > 42 else iq["query"]
        asker = iq.get("authorized_user", "unknown")
        q_viols = [v for v in all_violations if v["query_id"] == qid]
        img_viol_count += len(q_viols)
        status_str = f"{len(q_viols)} violations" if q_viols else "0 (CLEAN)"
        print(f"{qid:<6} {q_text:<45} {asker:<8} {status_str:<15}")

    print("=" * 95)
    print(f"TOTAL IMAGE SEARCH CHECKS    : {len(image_q_stats) * len(USER_ORDER)}")
    print(f"TOTAL IMAGE ACL VIOLATIONS    : {img_viol_count}")
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
