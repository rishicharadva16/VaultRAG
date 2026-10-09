"""
scripts/walkthrough.py

Executes Section 9 walkthrough:
1. Log in as u_asha and u_karan
2. Ask 'What is the Apex vendor contract value?' through POST /ask as both users
3. GET /citation/{chunk_id} for one chunk as each user
Prints the full JSON responses.
"""

import json
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.main import app

client = TestClient(app)

print("=" * 80)
print("1. Log in as u_asha and u_karan")
print("=" * 80)

r_asha = client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": "changeme123"})
assert r_asha.status_code == 200, f"Login as u_asha failed: {r_asha.text}"
tok_asha = r_asha.json()["access_token"]
print("u_asha login successful.")

r_karan = client.post("/auth/login", json={"email": "karan.shah@northwind.example", "password": "changeme123"})
assert r_karan.status_code == 200, f"Login as u_karan failed: {r_karan.text}"
tok_karan = r_karan.json()["access_token"]
print("u_karan login successful.")

print("\n" + "=" * 80)
print("2. POST /ask as u_asha (question: 'What is the Apex vendor contract value?')")
print("=" * 80)
res_asha = client.post(
    "/ask",
    headers={"Authorization": f"Bearer {tok_asha}"},
    json={"question": "What is the Apex vendor contract value?"},
)
print(f"Status Code: {res_asha.status_code}")
print(json.dumps(res_asha.json(), indent=2))

print("\n" + "=" * 80)
print("3. POST /ask as u_karan (question: 'What is the Apex vendor contract value?')")
print("=" * 80)
res_karan = client.post(
    "/ask",
    headers={"Authorization": f"Bearer {tok_karan}"},
    json={"question": "What is the Apex vendor contract value?"},
)
print(f"Status Code: {res_karan.status_code}")
k_data = res_karan.json()
print(json.dumps(k_data, indent=2))

print("\n" + "=" * 80)
print("4. GET /citation/{chunk_id} for a chunk retrieved by Karan")
print("=" * 80)
chunk_id = k_data["citations"][0]["chunk_id"] if k_data.get("citations") else "vendor_contract_apex.pdf-p1-c1"
print(f"Target chunk_id: {chunk_id}\n")

print("--- Calling GET /citation/{chunk_id} as u_karan (Authorized) ---")
cite_karan = client.get(
    f"/citation/{chunk_id}",
    headers={"Authorization": f"Bearer {tok_karan}"},
)
print(f"Status Code: {cite_karan.status_code}")
print(json.dumps(cite_karan.json(), indent=2))

print("\n--- Calling GET /citation/{chunk_id} as u_asha (Forbidden) ---")
cite_asha = client.get(
    f"/citation/{chunk_id}",
    headers={"Authorization": f"Bearer {tok_asha}"},
)
print(f"Status Code: {cite_asha.status_code}")
print(json.dumps(cite_asha.json(), indent=2))
print("=" * 80)
