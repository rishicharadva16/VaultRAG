import json
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.rag.answer import answer_question
from app.security.principals import build_principal

dataset_dir = settings.dataset_path()
eval_q_file = dataset_dir / "dataset" / "eval" / "eval_questions.json"
with open(eval_q_file, "r", encoding="utf-8") as f:
    eval_questions = json.load(f)

image_questions = [q for q in eval_questions if q["id"] in [f"Q0{i}" for i in range(41, 50)]]

db = SessionLocal()
try:
    users = {u.external_id: u for u in db.query(User).all() if u.external_id}
finally:
    db.close()

principals = {uid: build_principal(users[uid]) for uid in users}

print(f"Testing {len(image_questions)} Image/Cross-source questions (Q041-Q049)...")

for q in image_questions:
    qid = q["id"]
    uid = q["user_id"]
    p = principals[uid]
    query = q["question"]
    print("\n" + "=" * 80)
    print(f"[{qid}] User: {uid} | Access Expected: {q['access_expected']}")
    print(f"Query: {query}")
    print(f"Expected Sources: {q.get('expected_sources')}")
    print(f"Must Contain: {q.get('answer_must_contain')}")
    print(f"Must Not Cite: {q.get('must_not_cite')}")

    res = answer_question(principal=p, question=query, top_k=5)
    print(f"Result Refused: {res.refused} (reason: {res._reason})")
    print(f"Result Verified: {res.verified}")
    print(f"Answer: {res.answer}")
    print("Citations:")
    for c in res.citations:
        print(f"  - source_id: {c.source_id}, file: {c.file}, row_id: {getattr(c, 'row_id', None)}, boxes: {len(getattr(c, 'boxes', [])) if getattr(c, 'boxes', None) else 0}")
