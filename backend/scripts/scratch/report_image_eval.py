import json
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.index.store import SecureStore
from app.security.principals import build_principal
from app.index.embedder import DenseEmbedder, SparseEmbedder

cache_file = backend_dir / "scripts" / "eval_answers_cache.json"
results_file = backend_dir / "scripts" / "eval_results.json"
eval_q_file = settings.dataset_path() / "dataset" / "eval" / "eval_questions.json"

with open(cache_file, "r", encoding="utf-8") as f:
    cache = json.load(f)
with open(results_file, "r", encoding="utf-8") as f:
    results = json.load(f)
with open(eval_q_file, "r", encoding="utf-8") as f:
    eval_q = json.load(f)

eq_map = {q["id"]: q for q in eval_q}
failures_map = {f["id"]: f for f in results.get("failures", [])}

store = SecureStore()
db = SessionLocal()
db_users = {u.external_id: u for u in db.query(User).all() if u.external_id}
principals = {uid: build_principal(db_users[uid]) for uid in db_users}
dense_embedder = DenseEmbedder()
sparse_embedder = SparseEmbedder()

print("=" * 110)
print(f"{'EVALUATION REPORT FOR IMAGE QUESTIONS (Q041 - Q049)':^110}")
print("=" * 110)

for qid in [f"Q0{i}" for i in range(41, 50)]:
    q = eq_map[qid]
    q_text = q["question"]
    asker = q["user_id"]
    is_failed = qid in failures_map
    status = "FAIL" if is_failed else "PASS"

    print(f"\n[{qid}] Status: {status} | Type: {q['type']} | Asker: {asker}")
    print(f"  Question: {q_text}")
    print(f"  Expected Sources: {q.get('expected_sources', [])}")
    print(f"  Must Contain: {q.get('answer_must_contain', [])}")

    # Find cache entry
    cache_entry = None
    for k, v in cache.items():
        if q_text in k:
            cache_entry = v
            break

    if is_failed:
        fail_info = failures_map[qid]
        reason_code = cache_entry.get("_reason") if cache_entry else "unknown"
        print(f"  Failure Detail: {fail_info['detail']}")
        print(f"  Reason Code: {reason_code}")

        # Retrieve chunks for this question
        principal = principals.get(asker)
        dvec = dense_embedder.embed_query(q_text)
        svec = sparse_embedder.embed_sparse_query(q_text)
        retrieved = store.search(principal=principal, query=(dvec, svec), top_k=5)

        print(f"  Retrieved Chunks ({len(retrieved)}):")
        from app.index.schema import point_id
        for r in retrieved:
            # Fetch point payload to get ocr_confidence and boxes
            pid = str(point_id(r.chunk_id))
            pt = store._client.retrieve(
                collection_name=settings.QDRANT_COLLECTION,
                ids=[pid],
                with_payload=True,
            )
            payload = pt[0].payload if pt else {}
            text_len = len(r.text)
            conf = payload.get("ocr_confidence", "N/A")
            kind = payload.get("kind", "text")
            print(f"    - ID: {r.chunk_id} | Kind: {kind} | Text Len: {text_len} | Mean Conf: {conf} | Score: {r.score:.3f}")
    else:
        if cache_entry:
            cits = [c.get("chunk_id") for c in cache_entry.get("citations", [])]
            print(f"  Answer: {cache_entry.get('answer')[:120]}...")
            print(f"  Citations: {cits}")

print("\n" + "=" * 110)
