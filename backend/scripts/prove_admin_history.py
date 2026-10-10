import sys
import json
sys.path.insert(0, r"d:\VaultRAG\backend")
from fastapi.testclient import TestClient
from app.main import app
from app.security.jwt import create_token
from app.db.session import SessionLocal
from app.db.models import User

client = TestClient(app)

db = SessionLocal()
admin = db.query(User).filter(User.roles.contains(["admin"])).first()
db.close()

token = create_token(admin.id)
headers = {"Authorization": f"Bearer {token}"}

hist_resp = client.get("/history?limit=3", headers=headers)
print("Admin GET /history Status:", hist_resp.status_code)
hist_data = hist_resp.json()
print("Admin GET /history JSON Response:")
print(json.dumps(hist_data, indent=2, default=str))
