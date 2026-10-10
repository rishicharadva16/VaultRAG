import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.index.store import SecureStore
from app.rag.reranker import Reranker

db = SessionLocal()
ravi = db.query(User).filter(User.external_id == "u_ravi").first()
p = build_principal(ravi)
store = SecureStore()

q = "What sprint number is written on the sprint whiteboard?"
cands = store.search(p, q, top_k=5)
print(f"Candidates for '{q}': {len(cands)}")
for c in cands:
    print(f"  {c.chunk_id}: score={c.score} | source={c.source_id}")

reranker = Reranker()
reranked = reranker.rerank(q, cands, top_k=5)
print("\nReranked:")
for c in reranked:
    print(f"  {c.chunk_id}: score={c.score}")
