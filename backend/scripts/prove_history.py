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
user = db.query(User).filter(User.email == "neha.desai@northwind.example").first()
if not user:
    user = db.query(User).filter(User.active == True).first()
db.close()

token = create_token(user.id)
headers = {"Authorization": f"Bearer {token}"}

print(f"Testing as user: {user.name} ({user.email}), id={user.id}")

# 1. Run real query through /ask
ask_resp = client.post(
    "/ask",
    headers=headers,
    json={"question": "What are the rules regarding annual leave policies for Northwind staff?"}
)
print("POST /ask Status:", ask_resp.status_code)
ask_data = ask_resp.json()
print("POST /ask Answer snippet:", ask_data.get("answer", "")[:100], "Refused:", ask_data.get("refused"))

# 2. Call GET /history
hist_resp = client.get("/history?limit=3", headers=headers)
print("GET /history Status:", hist_resp.status_code)
hist_data = hist_resp.json()
print("GET /history JSON Response:")
print(json.dumps(hist_data, indent=2, default=str))
