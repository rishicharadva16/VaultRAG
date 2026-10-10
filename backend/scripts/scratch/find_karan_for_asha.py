import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.security.principals import build_principal
from app.index.store import SecureStore

db = SessionLocal()
asha = db.query(User).filter(User.external_id == "u_asha").first()
p = build_principal(asha)
store = SecureStore()
all_pts = store.scroll_all_points()
asha_pts = [pt for pt in all_pts if bool(set(p.tokens) & set(pt.payload.get("acl_tokens", [])))]
karan_pts = [pt for pt in asha_pts if "karan" in pt.payload.get("text", "").lower()]

print(f"Chunks with 'Karan' accessible to Asha: {len(karan_pts)}")
for pt in karan_pts:
    print(f"  {pt.payload.get('chunk_id')}: {pt.payload.get('text')}")
