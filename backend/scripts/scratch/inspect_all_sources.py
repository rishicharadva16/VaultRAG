import sys
sys.path.insert(0, r"D:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import User
from app.index.store import SecureStore

store = SecureStore()
points = store.scroll_all_points()

# Print sample text from each source
sources = {}
for p in points:
    src = p.payload.get("source_id", "")
    if src not in sources:
        sources[src] = p.payload.get("text", "")[:120]

for src, txt in sorted(sources.items()):
    print(f"{src:<35}: {txt}")
