import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.db.models import User
from app.db.session import SessionLocal
from app.security.principals import build_principal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.store import SecureStore
from app.rag.reranker import Reranker
from app.rag.answer import _build_context_block, _build_system_prompt, _query_llm, _verify_answer

db = SessionLocal()
u = db.query(User).filter_by(external_id="u_karan").first()
p = build_principal(u)
db.close()

store = SecureStore()
de = DenseEmbedder()
se = SparseEmbedder()
rr = Reranker()

q = "What is the total on the Apex invoice dated 05 Jun 2026?"
res = store.search(p, (de.embed_query(q), se.embed_sparse_query(q)), top_k=10)
res = rr.rerank(q, res, top_k=5)
ctx, cits = _build_context_block(res, p)
sys_prompt = _build_system_prompt()
ans = _query_llm(sys_prompt, ctx, q)
print("RAW LLM ANSWER:\n", ans)
ver = _verify_answer(q, ans, cits)
print("VERIFY RESULT:", ver)
