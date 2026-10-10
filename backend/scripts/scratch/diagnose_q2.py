import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.index.store import SecureStore
from app.config import settings
from app.rag.reranker import Reranker
from app.llm.provider import get_llm
from app.rag.answer import _build_system_prompt, _build_context_block, _parse_llm_response

db = SessionLocal()
meera = db.query(User).filter(User.external_id == "u_meera").first()
p = build_principal(meera)
store = SecureStore()
q = "What is the role of Asha? And give me her contact number."

# 1. Accessible entities
ents = store.get_accessible_employee_entities(p)
matched_ents = [e for e in ents if "asha" in e["name"].lower()]
print("Accessible entities matching Asha:", matched_ents)

# 2. Sub questions
raw_sub_qs = [s.strip() for s in q.split("?") if s.strip()]
print("Sub-questions split by ?:", raw_sub_qs)

# In answer.py:
# raw_sub_qs = [s.strip() for s in re.split(r'\?|\band\b|\balso\b|;', question, flags=re.IGNORECASE) if s.strip()]
import re
raw_sub_qs_full = [s.strip() for s in re.split(r'\?|\band\b|\balso\b|;', q, flags=re.IGNORECASE) if s.strip()]
print("Sub-questions split by regex in answer.py:", raw_sub_qs_full)

candidates = []
seen_ids = set()
for sub_q in raw_sub_qs_full[:3]:
    expanded_q = f"{sub_q} Asha Patel E1004"
    cands = store.search(p, expanded_q, top_k=settings.ASK_CANDIDATES)
    for c in cands:
        if c.chunk_id not in seen_ids:
            seen_ids.add(c.chunk_id)
            candidates.append(c)

print(f"Total retrieved candidates: {len(candidates)}")
has_base = any(c.chunk_id == "db:employees#E1004:base" for c in candidates)
has_sens = any(c.chunk_id == "db:employees#E1004:sensitive" for c in candidates)
print(f"db:employees#E1004:base in candidates: {has_base}")
print(f"db:employees#E1004:sensitive in candidates: {has_sens}")

# Reranker
reranker = Reranker()
ranking_query = f"{q} Asha Patel E1004"
candidates = reranker.rerank(ranking_query, candidates, top_k=settings.ASK_CANDIDATES)

print("\nTop 5 after reranking:")
for i, c in enumerate(candidates[:5]):
    print(f"  [{i+1}] {c.chunk_id} | score={c.score:.4f} | source={c.source_id}")

print(f"\nSettings: RELEVANCE_THRESHOLD={settings.RELEVANCE_THRESHOLD}, ASK_TOP_K={settings.ASK_TOP_K}")
relevant = [c for c in candidates if c.score >= settings.RELEVANCE_THRESHOLD]
print(f"Chunks above threshold: {len(relevant)}")

# Relevance gate override logic in answer.py:
if not relevant and matched_ents:
    print("Relevance gate override would trigger if relevant is empty.")

relevant = (relevant or candidates)[:settings.ASK_TOP_K]
print("\nFinal relevant chunks sent to LLM:")
for i, c in enumerate(relevant):
    print(f"  [{i+1}] {c.chunk_id} (score={c.score:.4f})")

# Prompt sent to LLM
system_msg = _build_system_prompt()
context_blocks = [_build_context_block(i + 1, c) for i, c in enumerate(relevant)]
user_msg = "Context:\n" + "\n\n".join(context_blocks) + f"\n\nQuestion: {q}"
messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]

llm = get_llm()
raw_response = llm.generate(messages=messages, max_tokens=settings.LLM_MAX_TOKENS, temperature=0, json_mode=True)
print("\nLLM raw response:")
print(raw_response)
parsed = _parse_llm_response(raw_response)
print("Parsed response:", parsed)
