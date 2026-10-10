import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.llm.provider import get_llm
from app.rag.answer import _build_system_prompt, _build_context_block
from app.index.store import SecureStore
from app.rag.reranker import Reranker

db = SessionLocal()
karan = db.query(User).filter(User.external_id == "u_karan").first()
p = build_principal(karan)
store = SecureStore()

q = "What is my revised CTC salary?"
cands = store.search(p, f"{q} {p.name} {p.employee_id}", top_k=5)
reranker = Reranker()
relevant = reranker.rerank(f"{q} {p.name} {p.employee_id}", cands, top_k=5)

system_msg = _build_system_prompt()
context_blocks = [_build_context_block(i + 1, c) for i, c in enumerate(relevant)]

# Test without user identity vs with user identity
user_msg_with_id = (
    "Context:\n"
    + "\n\n".join(context_blocks)
    + f"\n\nAuthenticated User: {p.name} (employee ID {p.employee_id})\nQuestion: {q}"
)

llm = get_llm()
resp = llm.generate(
    messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg_with_id}],
    max_tokens=256,
    temperature=0,
    json_mode=True,
)
print("LLM Response WITH user identity:")
print(resp)
