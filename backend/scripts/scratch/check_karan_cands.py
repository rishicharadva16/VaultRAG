import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.index.store import SecureStore
from app.rag.reranker import Reranker

db = SessionLocal()
karan = db.query(User).filter(User.external_id == "u_karan").first()
p = build_principal(karan)
store = SecureStore()

q = "What is my revised CTC salary? Karan Shah E1002"
cands = store.search(p, q, top_k=5)
print("Candidates for Karan salary:")
for c in cands:
    print(f"  {c.chunk_id}: score={c.score} | text={c.text[:80]}")

reranker = Reranker()
reranked = reranker.rerank(q, cands, top_k=5)
print("\nReranked:")
for c in reranked:
    print(f"  {c.chunk_id}: score={c.score}")
