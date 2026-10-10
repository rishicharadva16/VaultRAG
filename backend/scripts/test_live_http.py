import urllib.request
import json
import sys
sys.path.insert(0, r"d:\VaultRAG\backend")
from app.security.jwt import create_token
from app.db.session import SessionLocal
from app.db.models import User

db = SessionLocal()
user = db.query(User).filter(User.email == 'neha.desai@northwind.example').first()
db.close()

token = create_token(user.id)
req = urllib.request.Request(
    'http://127.0.0.1:8000/history?limit=3',
    headers={'Authorization': f'Bearer {token}'}
)

with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    print("HTTP Status:", resp.status)
    print("Items count:", len(data.get("items", [])))
    print("Total count:", data.get("total"))
    print("Sample item:", json.dumps(data["items"][0], indent=2))
