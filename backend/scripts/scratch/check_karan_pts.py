import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.index.store import SecureStore

db = SessionLocal()
karan = db.query(User).filter(User.external_id == "u_karan").first()
p = build_principal(karan)
store = SecureStore()
all_pts = store.scroll_all_points()

print(f"Karan employee_id: {karan.employee_id}, name: {karan.name}, dept: {karan.department}")
print(f"Karan principal tokens: {p.tokens}")

karan_e1002_pts = [pt for pt in all_pts if "E1002" in pt.payload.get("chunk_id", "") or "E1002" in pt.payload.get("text", "")]
print(f"\nAll points in Qdrant mentioning E1002: {len(karan_e1002_pts)}")
for pt in karan_e1002_pts:
    cid = pt.payload.get("chunk_id")
    tokens = pt.payload.get("acl_tokens")
    readable = bool(set(p.tokens) & set(tokens))
    print(f"  {cid:<32} | readable={readable} | tokens={tokens}")
