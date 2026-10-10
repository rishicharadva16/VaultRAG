import json
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.store import SecureStore
from app.rag.answer import answer_question
from app.rag.reranker import Reranker
from app.security.principals import build_principal

db = SessionLocal()
users = {u.external_id: u for u in db.query(User).all() if u.external_id}
db.close()

store = SecureStore()
dense_embedder = DenseEmbedder()
sparse_embedder = SparseEmbedder()
reranker = Reranker()

def inspect_q(qid, uid, query):
    print("=" * 80)
    print(f"INSPECTING {qid} | User: {uid}")
    print(f"Query: {query}")
    p = build_principal(users[uid])
    dvec = dense_embedder.embed_query(query)
    svec = sparse_embedder.embed_sparse_query(query)
    candidates = store.search(p, (dvec, svec), top_k=10)
    print(f"Found {len(candidates)} candidates before rerank:")
    for i, c in enumerate(candidates[:5]):
        print(f"  [{i}] {c.source_id} ({c.chunk_id}) score={c.score:.4f} text={c.text[:80]!r}")
    
    reranked = reranker.rerank(query, candidates, top_k=5)
    print(f"Top reranked candidates:")
    for i, c in enumerate(reranked):
        print(f"  [{i}] {c.source_id} ({c.chunk_id}) rerank_score={c.score:.4f} text={c.text[:80]!r}")
    
    # Check what answer_question generates before verification
    # Run full answer_question with debug
    res = answer_question(p, query, top_k=5)
    print(f"Final answer: {res.answer}")
    print(f"Refused: {res.refused}, Reason: {res._reason}")

# 1. Q045: Asha ID card
inspect_q("Q045", "u_asha", "What employee ID is printed on my ID card?")

# 2. Q042: Blurry invoice 04
inspect_q("Q042", "u_karan", "What is the total on the Apex invoice dated 05 Jun 2026?")

# 3. Q049: Pune hotel
inspect_q("Q049", "u_karan", "Is the Pune hotel claim for Sneha Reddy within policy for her grade?")
