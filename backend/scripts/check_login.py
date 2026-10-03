"""
Smoke-test the running API without a frontend.
Logs in as each seeded user, checks /auth/me, and verifies RBAC on /admin/users.

Usage: python scripts/check_login.py [--base-url http://127.0.0.1:8000]
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import httpx
except ImportError:
    print("ERROR: httpx is not installed. Run: pip install httpx")
    sys.exit(1)

SEED_PASSWORD = os.environ.get("SEED_PASSWORD", "changeme123")

EXPECTED = [
    {"email": "priya@vaultrag.local",  "name": "Priya", "role": "admin",   "clearance": 3},
    {"email": "rahul@vaultrag.local",  "name": "Rahul", "role": "hr",      "clearance": 2},
    {"email": "meera@vaultrag.local",  "name": "Meera", "role": "finance", "clearance": 2},
    {"email": "arjun@vaultrag.local",  "name": "Arjun", "role": "intern",  "clearance": 1},
]


def main():
    parser = argparse.ArgumentParser(description="Check login for seeded users")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    # Check API is reachable
    try:
        r = httpx.get(f"{base}/health", timeout=5)
    except httpx.ConnectError:
        print(f"ERROR: Cannot reach the API at {base}")
        print("       Is the server running? Start it with:")
        print("       uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
        sys.exit(1)

    ok = True
    tokens = {}

    print()
    print(f"  {'User':<10} {'Expected':<10} {'Actual':<10} {'Clr':>3}  {'Result'}")
    print(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*3}  {'-'*6}")

    for u in EXPECTED:
        resp = httpx.post(f"{base}/auth/login", json={"email": u["email"], "password": SEED_PASSWORD})
        if resp.status_code != 200:
            print(f"  {u['name']:<10} {u['role']:<10} {'(login failed)':<10} {'':>3}  FAIL")
            ok = False
            continue

        token = resp.json()["access_token"]
        tokens[u["email"]] = token

        me = httpx.get(f"{base}/auth/me", headers={"Authorization": f"Bearer {token}"})
        if me.status_code != 200:
            print(f"  {u['name']:<10} {u['role']:<10} {'(/me failed)':<10} {'':>3}  FAIL")
            ok = False
            continue

        data = me.json()
        actual_roles = data.get("roles", [])
        actual_role = actual_roles[0] if actual_roles else "(none)"
        clr = data.get("clearance", "?")
        passed = u["role"] in actual_roles and data.get("clearance") == u["clearance"]
        result = "PASS" if passed else "FAIL"
        if not passed:
            ok = False
        print(f"  {u['name']:<10} {u['role']:<10} {actual_role:<10} {clr:>3}  {result}")

    # RBAC check: Arjun (intern) → 403 on /admin/users, Priya (admin) → 200
    print()
    arjun_token = tokens.get("arjun@vaultrag.local")
    priya_token = tokens.get("priya@vaultrag.local")

    if arjun_token:
        r = httpx.get(f"{base}/admin/users", headers={"Authorization": f"Bearer {arjun_token}"})
        status_str = "PASS" if r.status_code == 403 else "FAIL"
        if r.status_code != 403:
            ok = False
        print(f"  Arjun -> GET /admin/users  => {r.status_code} {status_str}")

    if priya_token:
        r = httpx.get(f"{base}/admin/users", headers={"Authorization": f"Bearer {priya_token}"})
        status_str = "PASS" if r.status_code == 200 else "FAIL"
        if r.status_code != 200:
            ok = False
        print(f"  Priya -> GET /admin/users  => {r.status_code} {status_str}")

    print()
    if ok:
        print("All checks PASSED.")
    else:
        print("Some checks FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
