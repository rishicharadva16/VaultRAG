import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.rag import answer

db = SessionLocal()
meera = db.query(User).filter(User.external_id == "u_meera").first()
p = build_principal(meera)

llm = answer.get_llm()
orig_gen = llm.generate

def debug_gen(*args, **kwargs):
    res = orig_gen(*args, **kwargs)
    print("=== DEBUG_GEN CALL ===")
    msgs = kwargs.get("messages") or (args[0] if args else [])
    for m in msgs:
        print(f"--- ROLE: {m.get('role')} ---")
        print(m.get("content"))
    print("=== RAW RESPONSE ===")
    print(res)
    print("====================")
    return res

llm.generate = debug_gen
res = answer.answer_question(p, "What is the role of Asha? And give me her contact number.", _llm=llm)
print("FINAL RESULT -> Refused:", res.refused, "Reason:", res._reason)
print("Answer:", res.answer)
