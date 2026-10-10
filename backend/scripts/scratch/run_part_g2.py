import asyncio
import json
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import SessionLocal
from app.db.models import AuditLog

SEED_PASSWORD = "changeme123"

async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login users
        res_karan = await client.post("/auth/login", json={"email": "karan.shah@northwind.example", "password": SEED_PASSWORD})
        t_karan = res_karan.json()["access_token"]
        h_karan = {"Authorization": f"Bearer {t_karan}"}

        res_meera = await client.post("/auth/login", json={"email": "meera.iyer@northwind.example", "password": SEED_PASSWORD})
        t_meera = res_meera.json()["access_token"]
        h_meera = {"Authorization": f"Bearer {t_meera}"}

        res_asha = await client.post("/auth/login", json={"email": "asha.patel@northwind.example", "password": SEED_PASSWORD})
        t_asha = res_asha.json()["access_token"]
        h_asha = {"Authorization": f"Bearer {t_asha}"}

        print("=" * 80)
        print("(a) Karan asks invoice amount (Clean invoice 01)")
        r_a = await client.post("/ask", headers=h_karan, json={"question": "What is the total on invoice INV-APX-0412?"})
        print(f"Status: {r_a.status_code}")
        print("Response JSON:")
        print(json.dumps(r_a.json(), indent=2))

        print("\n" + "=" * 80)
        print("(b1) Karan asks about rotated invoice (invoice 05)")
        r_b1 = await client.post("/ask", headers=h_karan, json={"question": "What is the invoice number on the rotated Shree Ganesh Stationers scan?"})
        print(f"Status: {r_b1.status_code}")
        print("Response JSON:")
        print(json.dumps(r_b1.json(), indent=2))

        print("\n" + "=" * 80)
        print("(b2) Karan asks about blurry invoice (invoice 04)")
        r_b2 = await client.post("/ask", headers=h_karan, json={"question": "What is the total on the Apex invoice dated 05 Jun 2026?"})
        print(f"Status: {r_b2.status_code}")
        print("Response JSON:")
        print(json.dumps(r_b2.json(), indent=2))

        print("\n" + "=" * 80)
        print("(c) Meera (HR Admin) asks about an employee's ID card")
        r_c = await client.post("/ask", headers=h_meera, json={"question": "What is the emergency contact on Asha Patel's ID card?"})
        print(f"Status: {r_c.status_code}")
        print("Response JSON:")
        print(json.dumps(r_c.json(), indent=2))

        print("\n" + "=" * 80)
        print("(d) Asha asks about someone else's ID card (Sneha Reddy E1010)")
        r_d = await client.post("/ask", headers=h_asha, json={"question": "What is the employee ID and blood group on Sneha Reddy's ID card?"})
        print(f"Status: {r_d.status_code}")
        print("Response JSON:")
        print(json.dumps(r_d.json(), indent=2))

        print("\n" + "=" * 80)
        print("(e) Asha asks about the whiteboard (Engineering member)")
        r_e = await client.post("/ask", headers=h_asha, json={"question": "What launch date is written on the sprint planning whiteboard?"})
        print(f"Status: {r_e.status_code}")
        print("Response JSON:")
        print(json.dumps(r_e.json(), indent=2))

        print("\n" + "=" * 80)
        print("(f) GET /image/{chunk_id} with token of allowed user (Karan -> invoice_01)")
        chunk_inv1 = "img:invoice_01_apex_apr.png%230"
        r_f = await client.get(f"/image/{chunk_inv1}", headers=h_karan)
        print(f"Status: {r_f.status_code}")
        print(f"Content-Type: {r_f.headers.get('content-type')}")
        print(f"Content-Length: {len(r_f.content)} bytes")

        # Check audit log for image_read event
        db = SessionLocal()
        latest_audit_karan = db.query(AuditLog).filter(AuditLog.event == "image_read").order_by(AuditLog.ts.desc()).first()
        print(f"Audit log event for Karan: event={latest_audit_karan.event}, reason_code={latest_audit_karan.reason_code}, refused={latest_audit_karan.refused}, details={latest_audit_karan.details}")

        print("\n" + "=" * 80)
        print("(g) GET /image/{chunk_id} with token of forbidden user (Asha -> invoice_01)")
        r_g = await client.get(f"/image/{chunk_inv1}", headers=h_asha)
        print(f"Status: {r_g.status_code}")
        print(f"Response: {r_g.text}")

        # Check audit log for image_read_denied event
        latest_audit_asha = db.query(AuditLog).filter(AuditLog.event == "image_read_denied").order_by(AuditLog.ts.desc()).first()
        print(f"Audit log event for Asha: event={latest_audit_asha.event}, reason_code={latest_audit_asha.reason_code}, refused={latest_audit_asha.refused}, details={latest_audit_asha.details}")
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
