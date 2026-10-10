import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.index.store import SecureStore
from app.rag.answer import answer_question

db = SessionLocal()
meera = db.query(User).filter(User.external_id == "u_meera").first()
p = build_principal(meera)

store = SecureStore()
all_pts = store.scroll_all_points()
meera_pts = [pt for pt in all_pts if bool(set(p.tokens) & set(pt.payload.get("acl_tokens", [])))]
salary_pts = [pt for pt in meera_pts if "db:salaries" in pt.payload.get("source_id", "")]
print("Salary chunks accessible to Meera:", len(salary_pts))
for pt in salary_pts:
    print(f"  {pt.payload.get('chunk_id')}: {pt.payload.get('text')}")
