import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.index.store import SecureStore

store = SecureStore()
pts, _ = store._client.scroll("vaultrag_chunks", limit=300)
for pt in pts:
    if pt.payload.get("source_id") == "img:invoice_04_apex_may_blurry.jpg":
        print("=== INVOICE 04 TEXT ===")
        print(pt.payload.get("text"))
        print("========================")
    if pt.payload.get("source_id") == "img:id_card_E1004.png":
        print("=== ID CARD E1004 TEXT ===")
        print(pt.payload.get("text"))
        print("==========================")
