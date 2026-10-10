import sys
sys.path.insert(0, ".")
import json
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.index.store import SecureStore
from app.rag.answer import answer_question

db = SessionLocal()
karan_user = db.query(User).filter(User.external_id == "u_karan").first()
karan_p = build_principal(karan_user)

# Question Q001 or Apex fee question:
q = "What is the monthly logistics fee specified in the Apex contract?"
print("Question:", q)
res = answer_question(karan_p, q)
print("Refused:", res.refused)
print("Answer:", res.answer)
print("Citations count:", len(res.citations))
for c in res.citations:
    print(f"Citation [{c.id}]: chunk_id={c.chunk_id}, file={c.file}, page={c.page}, highlights={c.highlights}")
    print(f"  highlight_text: {c.highlight_text}")

db.close()
