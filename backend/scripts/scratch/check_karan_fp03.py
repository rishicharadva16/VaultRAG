import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.rag.answer import answer_question

db = SessionLocal()
karan = db.query(User).filter(User.external_id == "u_karan").first()
p = build_principal(karan)

res = answer_question(p, "What is my employee ID?")
print("Refused:", res.refused, "Reason:", res._reason)
print("Answer:", res.answer)
print("Citations:", [c.to_dict() for c in res.citations])
