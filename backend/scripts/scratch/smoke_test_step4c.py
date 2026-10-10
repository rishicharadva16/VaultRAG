"""
Live smoke test for Step 4c:
- Karan opens Apex fee citation: view JSON and page.png status (200 OK)
- Asha gets 404 for the same chunk
"""

import json
import urllib.request
import urllib.error

def login(email, password="changeme123"):
    req = urllib.request.Request(
        "http://localhost:8000/auth/login",
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["access_token"]

def main():
    karan_token = login("karan.shah@northwind.example")
    asha_token = login("asha.patel@northwind.example")

    chunk_id = "vendor_contract_apex-p1-c1"
    hl = "437-590"

    print("=" * 60)
    print("LIVE SMOKE TEST: STEP 4c ACCESS CONTROL & SOURCE VIEWER")
    print("=" * 60)

    # 1. Karan opens Apex fee citation view
    print(f"\n1. Karan (finance_admin) requests /source/{chunk_id}/view?hl={hl}:")
    req_karan_view = urllib.request.Request(
        f"http://localhost:8000/source/{chunk_id}/view?hl={hl}",
        headers={"Authorization": f"Bearer {karan_token}"},
    )
    with urllib.request.urlopen(req_karan_view) as resp:
        karan_view_status = resp.status
        karan_view_data = json.loads(resp.read())
        print(f"Status: {karan_view_status}")
        print("Response JSON:")
        print(json.dumps(karan_view_data, indent=2))

    # 2. Karan requests page.png
    print(f"\n2. Karan requests /source/{chunk_id}/page.png:")
    req_karan_png = urllib.request.Request(
        f"http://localhost:8000/source/{chunk_id}/page.png",
        headers={"Authorization": f"Bearer {karan_token}"},
    )
    with urllib.request.urlopen(req_karan_png) as resp:
        content_type = resp.headers.get("Content-Type")
        cache_control = resp.headers.get("Cache-Control")
        body_len = len(resp.read())
        print(f"Status: {resp.status}, Content-Type: {content_type}, Cache-Control: {cache_control}, Bytes: {body_len}")

    # 3. Asha requests the same chunk view (expecting 404)
    print(f"\n3. Asha (employee, forbidden) requests /source/{chunk_id}/view?hl={hl}:")
    req_asha_view = urllib.request.Request(
        f"http://localhost:8000/source/{chunk_id}/view?hl={hl}",
        headers={"Authorization": f"Bearer {asha_token}"},
    )
    try:
        urllib.request.urlopen(req_asha_view)
        print("ERROR: Expected 404, got 200!")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"Status: {e.code} (Identical 404), Body: {body}")

    # 4. Asha requests the same page.png (expecting 404)
    print(f"\n4. Asha requests /source/{chunk_id}/page.png:")
    req_asha_png = urllib.request.Request(
        f"http://localhost:8000/source/{chunk_id}/page.png",
        headers={"Authorization": f"Bearer {asha_token}"},
    )
    try:
        urllib.request.urlopen(req_asha_png)
        print("ERROR: Expected 404, got 200!")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"Status: {e.code} (Identical 404), Body: {body}")

if __name__ == "__main__":
    main()
