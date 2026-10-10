import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.db.models import User
from app.db.session import SessionLocal
from app.security.principals import build_principal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.store import SecureStore
from app.rag.reranker import Reranker
from app.rag.answer import _build_context_block, _build_system_prompt, _extract_fact_tokens, _fact_token_in_chunks
from app.llm.provider import get_llm

db = SessionLocal()
u = db.query(User).filter_by(external_id="u_karan").first()
p = build_principal(u)
db.close()

store = SecureStore()
de = DenseEmbedder()
se = SparseEmbedder()
rr = Reranker()
llm = get_llm()

q = "What is the total on the Apex invoice dated 05 Jun 2026?"
res = store.search(p, (de.embed_query(q), se.embed_sparse_query(q)), top_k=10)
res = rr.rerank(q, res, top_k=5)
context_blocks = [_build_context_block(i + 1, c) for i, c in enumerate(res)]
sys_prompt = _build_system_prompt()
user_msg = "Context:\n" + "\n\n".join(context_blocks) + f"\n\nQuestion: {q}"

raw = llm.generate([
    {"role": "system", "content": sys_prompt},
    {"role": "user", "content": user_msg}
], json_mode=True)
print("RAW RESPONSE:")
print(raw)

import json
parsed = json.loads(raw)
for s in parsed.get("sentences", []):
    txt = s["text"]
    cits = s["citations"]
    tokens = _extract_fact_tokens(txt)
    print("Sentence:", txt)
    print("Tokens:", tokens)
    cited_texts = [res[c - 1].text for c in cits if c <= len(res)]
    for ft in tokens:
        ok = _fact_token_in_chunks(ft, cited_texts)
        print(f"  token '{ft}' in chunks: {ok}")
