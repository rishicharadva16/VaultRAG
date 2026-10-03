"""
Smoke-test the running API against the Northwind user set without a frontend.
Logs in as each of the 7 seeded accounts, calls /auth/me, and verifies RBAC on /admin/users.

Usage: python scripts/check_login.py [--base-url http://127.0.0.1:8000]
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import httpx
except ImportError:
    print("ERROR: httpx is not installed. Run: pip install httpx")
    sys.exit(1)

SEED_PASSWORD = os.environ.get("SEED_PASSWORD", "changeme123")

ACCOUNTS = [
    {"user_id": "u_asha",  "email": "asha.patel@northwind.example",   "role": "employee",      "emp_id": "E1004"},
    {"user_id": "u_neha",  "email": "neha.desai@northwind.example",   "role": "employee",      "emp_id": "E1006"},
    {"user_id": "u_ravi",  "email": "ravi.menon@northwind.example",   "role": "manager",       "emp_id": "E1003"},
    {"user_id": "u_dev",   "email": "dev.joshi@northwind.example",    "role": "manager",       "emp_id": "E1005"},
    {"user_id": "u_meera", "email": "meera.iyer@northwind.example",   "role": "hr_admin",      "emp_id": "E1001"},
    {"user_id": "u_karan", "email": "karan.shah@northwind.example",   "role": "finance_admin", "emp_id": "E1002"},
    {"user_id": "u_admin", "email": "admin@northwind.example",        "role": "admin",         "emp_id": None},
]


def main():
    parser = argparse.ArgumentParser(description="Check login for Northwind dataset users")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    # Check API is reachable
    try:
        r = httpx.get(f"{base}/health", timeout=5)
        if r.status_code != 200:
            print(f"WARNING: Health endpoint returned {r.status_code}")
    except (httpx.ConnectError, httpx.RequestError):
        print(f"ERROR: Cannot reach the API at {base}")
        print("       Is the server running? Start it with:")
        print("       uvicorn app.main:app --reload --host 127.0.0.1 --port 8000")
        sys.exit(1)

    ok = True
    tokens = {}

    print()
    print(f"  {'User ID':<10} {'Email':<30} {'Expected Role':<15} {'Actual Role':<15} {'Emp ID':<8} {'Status'}")
    print(f"  {'-'*10} {'-'*30} {'-'*15} {'-'*15} {'-'*8} {'-'*6}")

    for u in ACCOUNTS:
        # 1. Login
        resp = httpx.post(f"{base}/auth/login", json={"email": u["email"], "password": SEED_PASSWORD})
        if resp.status_code != 200:
            print(f"  {u['user_id']:<10} {u['email']:<30} {u['role']:<15} {'(login failed)':<15} {'-':<8} FAIL")
            ok = False
            continue

        token = resp.json().get("access_token")
        tokens[u["user_id"]] = token

        # 2. Call /auth/me
        me_resp = httpx.get(f"{base}/auth/me", headers={"Authorization": f"Bearer {token}"})
        if me_resp.status_code != 200:
            print(f"  {u['user_id']:<10} {u['email']:<30} {u['role']:<15} {'(/me failed)':<15} {'-':<8} FAIL")
            ok = False
            continue

        data = me_resp.json()
        roles = data.get("roles", [])
        actual_role = roles[0] if roles else "(none)"
        emp_id = data.get("employee_id") or "-"
        expected_emp = u["emp_id"] or "-"

        match = (actual_role == u["role"]) and (emp_id == expected_emp)
        if not match:
            ok = False

        status_str = "PASS" if match else "FAIL"
        print(f"  {u['user_id']:<10} {u['email']:<30} {u['role']:<15} {actual_role:<15} {emp_id:<8} {status_str}")

    # RBAC checks
    print()
    # u_asha calling /admin/users -> 403
    asha_token = tokens.get("u_asha")
    if asha_token:
        r_admin = httpx.get(f"{base}/admin/users", headers={"Authorization": f"Bearer {asha_token}"})
        if r_admin.status_code == 403:
            print("  u_asha -> GET /admin/users  => 403 PASS")
        else:
            print(f"  u_asha -> GET /admin/users  => {r_admin.status_code} FAIL (expected 403)")
            ok = False
    else:
        print("  u_asha token missing -> skipping 403 check")
        ok = False

    # u_admin calling /admin/users -> 200
    admin_token = tokens.get("u_admin")
    if admin_token:
        r_admin = httpx.get(f"{base}/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        if r_admin.status_code == 200:
            print("  u_admin -> GET /admin/users => 200 PASS")
        else:
            print(f"  u_admin -> GET /admin/users => {r_admin.status_code} FAIL (expected 200)")
            ok = False
    else:
        print("  u_admin token missing -> skipping 200 check")
        ok = False

    print()
    if ok:
        print("All checks PASSED.")
    else:
        print("Some checks FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
