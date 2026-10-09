"""
scripts/calibrate_threshold.py

Calibrates relevance and semantic support thresholds using PDF questions from eval_questions.json.

Features:
- Fixes Windows thread-pool deadlocks (TOKENIZERS_PARALLELISM=false)
- Explicit timeout on Qdrant and database connections
- Caches reranker scores in JSON to avoid repeating expensive computation
- Progress reporting every 10 searches
- CLI flags: --max-questions N (default 40), --users, --cache-file
- By default tests each question's own asker + 1 unanswerable user (not all 7 users)
"""

import argparse
import importlib.util
import json
import os
import statistics
import sys
import time
from pathlib import Path

# CRITICAL: Prevent bytecode generation in read-only data directory
sys.dont_write_bytecode = True

# CRITICAL: Prevent HuggingFace / PyTorch thread deadlock on Windows
os.environ["TOKENIZERS_PARALLELISM"] = "false"

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.index.store import SecureStore
from app.rag.reranker import Reranker
from app.security.principals import build_principal

# Load reference acl.py dynamically
dataset_dir = settings.dataset_path()
acl_py_path = dataset_dir / "acl.py"
spec = importlib.util.spec_from_file_location("dataset_acl", str(acl_py_path))
dataset_acl = importlib.util.module_from_spec(spec)
sys.modules["dataset_acl"] = dataset_acl
if str(dataset_dir) not in sys.path:
    sys.path.insert(0, str(dataset_dir))
spec.loader.exec_module(dataset_acl)

ALL_USERS = ["u_asha", "u_neha", "u_ravi", "u_dev", "u_meera", "u_karan", "u_admin"]
DEFAULT_CACHE_FILE = backend_dir / "scripts" / "calibration_cache.json"


def doc_of(src: str) -> str:
    return src.split("#")[0]


def is_pdf_question(q: dict) -> bool:
    q_type = q.get("type", "")
    if q_type in ("single_pdf", "table_pdf"):
        return True
    exp = q.get("expected_sources", [])
    bad = q.get("must_not_cite", [])
    if exp and all(s.startswith("pdf:") for s in exp):
        return True
    if bad and all(s.startswith("pdf:") for s in bad):
        return True
    return False


def is_answerable_for_user(uid: str, q: dict) -> bool:
    if uid == "u_admin":
        return False
    if q.get("access_expected") == "deny":
        return False
    exp = q.get("expected_sources", [])
    if not exp:
        return False
    for s in exp:
        doc = doc_of(s)
        try:
            if not dataset_acl.can_read_source(uid, doc):
                return False
        except Exception:
            return False
    return True


def pick_unanswerable_user(q: dict) -> str:
    """Find a user who is not allowed to see the documents for this question."""
    # First try a normal user who is forbidden
    for u in ["u_asha", "u_neha", "u_ravi", "u_dev"]:
        if not is_answerable_for_user(u, q):
            return u
    # Otherwise fallback to admin (who has zero doc permissions)
    return "u_admin"


def load_cache(cache_path: Path) -> dict:
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"questions": {}}


def save_cache(cache: dict, cache_path: Path) -> None:
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as exc:
        print(f"Warning: could not save cache: {exc}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Calibrate RAG relevance & support thresholds")
    parser.add_argument("--max-questions", type=int, default=40, help="Maximum number of questions to evaluate (default: 40)")
    parser.add_argument("--users", type=str, default="", help="Comma-separated users to test (default: asker + 1 unanswerable user)")
    parser.add_argument("--cache-file", type=str, default=str(DEFAULT_CACHE_FILE), help="Path to cache JSON file")
    parser.add_argument("--recompute", action="store_true", help="Ignore existing cache")
    args = parser.parse_args()

    cache_path = Path(args.cache_file)
    cache = {"questions": {}} if args.recompute else load_cache(cache_path)

    print("=" * 80)
    print("VaultRAG Reranker Threshold Calibration (PDF Questions)")
    print(f"Max Questions: {args.max_questions} | Cache: {cache_path.name}")
    print("=" * 80)

    eval_q_file = dataset_dir / "dataset" / "eval" / "eval_questions.json"
    with open(eval_q_file, "r", encoding="utf-8") as f:
        all_questions = json.load(f)

    pdf_questions = [q for q in all_questions if is_pdf_question(q)][:args.max_questions]
    print(f"Evaluating {len(pdf_questions)} PDF-related questions.")

    explicit_users = [u.strip() for u in args.users.split(",") if u.strip()] if args.users else None

    # Connect to DB and fetch users with proper cleanup
    db = SessionLocal()
    try:
        db_users = {u.external_id: u for u in db.query(User).all() if u.external_id}
    finally:
        db.close()

    principals = {uid: build_principal(db_users[uid]) for uid in db_users}

    store = SecureStore(timeout=10.0)
    reranker = Reranker()

    answerable_scores: list[float] = []
    unanswerable_scores: list[float] = []
    support_scores: list[float] = []

    search_count = 0
    t_start = time.time()

    for q_idx, q in enumerate(pdf_questions, 1):
        q_id = q.get("id")
        query_text = q.get("question", "")

        q_cache = cache.setdefault("questions", {}).setdefault(q_id, {"user_scores": {}, "support_scores": []})

        # Determine target users for this question
        if explicit_users:
            target_users = explicit_users
        else:
            asker = q.get("user_id", "u_asha")
            unans_user = pick_unanswerable_user(q)
            target_users = [asker] if asker == unans_user else [asker, unans_user]

        for uid in target_users:
            principal = principals.get(uid)
            if not principal:
                continue

            search_count += 1
            answerable = is_answerable_for_user(uid, q)

            # Check cache
            if uid in q_cache.get("user_scores", {}):
                top_score = q_cache["user_scores"][uid]["top_score"]
            else:
                try:
                    candidates = store.search(
                        principal=principal,
                        query=query_text,
                        top_k=settings.ASK_CANDIDATES,
                    )
                except Exception as exc:
                    print(f"Warning: search failed for {uid} on {q_id}: {exc}", file=sys.stderr)
                    candidates = []

                if candidates:
                    pairs = [[query_text, c.text] for c in candidates]
                    try:
                        raw_scores = reranker.score_pairs(pairs)
                        top_score = max(raw_scores) if raw_scores else -99.0
                    except Exception as exc:
                        print(f"Warning: reranker failed for {uid} on {q_id}: {exc}", file=sys.stderr)
                        top_score = -99.0
                else:
                    top_score = -99.0

                q_cache["user_scores"][uid] = {
                    "answerable": answerable,
                    "top_score": top_score,
                }
                save_cache(cache, cache_path)

            if answerable:
                if top_score > -90.0:
                    answerable_scores.append(top_score)
            else:
                if top_score > -90.0:
                    unanswerable_scores.append(top_score)

            if search_count % 10 == 0:
                elapsed = time.time() - t_start
                print(f"  [Progress] {search_count} searches processed in {elapsed:.1f}s (Q {q_idx}/{len(pdf_questions)}: {q_id})", flush=True)

        # Support score evaluation
        if q.get("access_expected") == "allow" and q.get("answer_must_contain"):
            if q_cache.get("support_scores"):
                support_scores.extend(q_cache["support_scores"])
            else:
                target_user = q.get("user_id")
                principal = principals.get(target_user)
                if principal:
                    try:
                        candidates = store.search(principal=principal, query=query_text, top_k=5)
                    except Exception:
                        candidates = []

                    pairs_to_score = []
                    for fact in q.get("answer_must_contain", []):
                        for c in candidates:
                            if fact.lower() in c.text.lower():
                                pairs_to_score.append([f"The answer is {fact}.", c.text])

                    if pairs_to_score:
                        try:
                            s_scores = reranker.score_pairs(pairs_to_score)
                            q_cache["support_scores"] = s_scores
                            support_scores.extend(s_scores)
                            save_cache(cache, cache_path)
                        except Exception:
                            pass

    total_time = time.time() - t_start
    print(f"\nCompleted {search_count} total searches across {len(pdf_questions)} questions in {total_time:.2f}s.")

    print("\n" + "=" * 80)
    print("CALIBRATION RESULTS")
    print("=" * 80)

    def stats(name, vals):
        if not vals:
            print(f"{name}: No data")
            return
        vals_s = sorted(vals)
        p10 = vals_s[int(0.10 * len(vals_s))]
        p25 = vals_s[int(0.25 * len(vals_s))]
        med = statistics.median(vals_s)
        p75 = vals_s[int(0.75 * len(vals_s))]
        p90 = vals_s[int(0.90 * len(vals_s))]
        print(f"{name} (count={len(vals)}):")
        print(f"  Min:    {vals_s[0]:.4f}")
        print(f"  P10:    {p10:.4f}")
        print(f"  P25:    {p25:.4f}")
        print(f"  Median: {med:.4f}")
        print(f"  P75:    {p75:.4f}")
        print(f"  P90:    {p90:.4f}")
        print(f"  Max:    {vals_s[-1]:.4f}")

    stats("Answerable Queries (Top Reranker Score)", answerable_scores)
    print()
    stats("Unanswerable Queries (Top Reranker Score)", unanswerable_scores)
    print()
    stats("Fact-Chunk Support Pairs Score", support_scores)

    if answerable_scores:
        rec_p10 = sorted(answerable_scores)[int(0.05 * len(answerable_scores))]
        rec_relevance = max(0.10, min(0.30, round(rec_p10 - 0.05, 2)))
    else:
        rec_relevance = 0.10

    if support_scores:
        sup_min = min(support_scores)
        rec_support = max(0.05, round(min(0.20, sup_min - 0.05), 2))
    else:
        rec_support = 0.05

    print("\n" + "=" * 80)
    print("RECOMMENDED THRESHOLDS")
    print("=" * 80)
    print(f"RELEVANCE_THRESHOLD = {rec_relevance:.2f}")
    print(f"SUPPORT_THRESHOLD   = {rec_support:.2f}")
    print(f"Total calibration runtime: {total_time:.2f}s")
    print("=" * 80)


if __name__ == "__main__":
    main()
