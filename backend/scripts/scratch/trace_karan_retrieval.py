import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.index.store import SecureStore
from app.config import settings
from app.rag.reranker import Reranker
from app.rag.answer import answer_question

db = SessionLocal()
karan = db.query(User).filter(User.external_id == "u_karan").first()
p = build_principal(karan)
store = SecureStore()
q = "What is my personal phone number?"

# Let's inspect answer_question step by step
accessible_entities = store.get_accessible_employee_entities(p)
print("Accessible entities for Karan:", [e["name"] for e in accessible_entities])

# How was first person resolved?
import re
is_first_person = bool(re.search(r'\b(my|I)\b', q))
print("is_first_person:", is_first_person)

user_emp_id = getattr(p, "employee_id", None)
user_name = getattr(p, "name", None)
self_ent = None
if user_emp_id:
    for ent in accessible_entities:
        if ent["employee_id"] == user_emp_id:
            self_ent = ent
            break
print("self_ent found in accessible_entities:", self_ent)

# What if name resolution also ran?
words = re.findall(r'\b[A-Za-z]+\b', q)
from app.rag.answer import _COMMON_STOP_WORDS
name_tokens = [w for w in words if w.lower() not in _COMMON_STOP_WORDS and len(w) >= 3]
print("name_tokens for q:", name_tokens)

# What did store.search retrieve?
expanded_q = f"{q} {self_ent['name']} {self_ent['employee_id']}" if self_ent else q
print("Expanded query:", expanded_q)
cands = store.search(p, expanded_q, top_k=10)
print(f"Retrieved {len(cands)} candidates:")
for c in cands[:5]:
    print(f"  {c.chunk_id}: score={c.score}")

reranker = Reranker()
reranked = reranker.rerank(expanded_q, cands, top_k=5)
print("\nReranked top 5:")
for c in reranked:
    print(f"  {c.chunk_id}: score={c.score}")
