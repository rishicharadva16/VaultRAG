import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.rag.answer import answer_question

db = SessionLocal()
karan = db.query(User).filter(User.external_id == "u_karan").first()
p = build_principal(karan)

res = answer_question(p, "What is the role of Asha?")
print("Karan asking Asha role -> Refused:", res.refused, "Reason:", res._reason)

res2 = answer_question(p, "What is the role of Asha? And give me her contact number.")
print("Karan asking Asha role+phone -> Refused:", res2.refused, "Reason:", res2._reason)
