"""
Role Matrix Verification Script (Step 5e-fix v2).

Evaluates the canonical access policy across all 7 Northwind accounts
(Admin, Meera HR, Karan Finance, Asha Engineering, Ravi Engineering, Dev Sales, Neha Sales)
using tests/role_questions.json plus live document upload sharing verification.

Usage:
    python scripts/role_matrix_check.py [--base-url http://127.0.0.1:8000]
"""

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

# CRITICAL: Prevent bytecode generation in read-only data directory
sys.dont_write_bytecode = True

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.main import app

SEED_PASSWORD = os.environ.get("SEED_PASSWORD", "changeme123")


def get_client(base_url: str | None):
    """Return an HTTP client (remote or in-process TestClient)."""
    if base_url:
        import httpx
        return httpx.Client(base_url=base_url.rstrip("/"), timeout=60.0), False
    else:
        from fastapi.testclient import TestClient
        return TestClient(app), True


def login_user(client, email: str) -> str:
    """Log in as user and return JWT bearer token."""
    resp = client.post("/auth/login", json={"email": email, "password": SEED_PASSWORD})
    if resp.status_code != 200:
        raise RuntimeError(f"Login failed for {email}: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token returned for {email}")
    return token


def run_upload_sharing_test(client, tokens: dict[str, str]) -> list[dict]:
    """
    Test uploaded-document sharing workflow:
    1. Upload as Asha (Engineering)
    2. Check owner Asha can read
    3. Check Ravi (Engineering) cannot read before sharing
    4. Share with Ravi
    5. Check Ravi can read
    6. Check Karan (Finance) cannot read
    7. Revoke share from Ravi
    8. Check Ravi cannot read after revocation
    """
    results = []
    asha_tok = tokens["asha.patel@northwind.example"]
    ravi_tok = tokens["ravi.menon@northwind.example"]
    karan_tok = tokens["karan.shah@northwind.example"]

    # 1. Upload text doc as Asha
    doc_content = b"Confidential Project Delta specification document. Code: DELTA-SEC-8819."
    files = {"file": ("project_delta.txt", io.BytesIO(doc_content), "text/plain")}
    up_resp = client.post(
        "/api/documents/upload",
        files=files,
        headers={"Authorization": f"Bearer {asha_tok}"},
    )
    if up_resp.status_code not in (200, 201):
        results.append({
            "test": "Upload document as Asha",
            "passed": False,
            "error": f"Upload failed: {up_resp.status_code}",
        })
        return results

    up_data = up_resp.json()
    doc_id = up_data.get("id") or up_data.get("document_id")

    # Question to ask about this doc
    q_share = "What is the code for Project Delta?"

    # (a) Check owner Asha can read
    ask_asha = client.post(
        "/ask",
        json={"question": q_share},
        headers={"Authorization": f"Bearer {asha_tok}"},
    )
    res_a = ask_asha.json()
    pass_a = not res_a.get("refused", True) and "DELTA-SEC-8819" in res_a.get("answer", "")
    results.append({
        "test": "Owner (Asha) reads uploaded doc",
        "passed": pass_a,
        "detail": f"refused={res_a.get('refused')}",
    })

    # (b) Check unshared Ravi cannot read
    ask_ravi1 = client.post(
        "/ask",
        json={"question": q_share},
        headers={"Authorization": f"Bearer {ravi_tok}"},
    )
    res_r1 = ask_ravi1.json()
    pass_r1 = res_r1.get("refused", False) is True
    results.append({
        "test": "Unshared colleague (Ravi) cannot read",
        "passed": pass_r1,
        "detail": f"refused={res_r1.get('refused')}",
    })

    # (c) Share document with Ravi
    # Look up Ravi's user ID from /auth/me
    me_ravi = client.get("/auth/me", headers={"Authorization": f"Bearer {ravi_tok}"}).json()
    ravi_uid = me_ravi.get("id")

    share_resp = client.post(
        f"/api/documents/{doc_id}/share",
        json={"user_id": ravi_uid, "permission": "read"},
        headers={"Authorization": f"Bearer {asha_tok}"},
    )
    share_ok = share_resp.status_code in (200, 201)

    # (d) Check shared Ravi can read
    ask_ravi2 = client.post(
        "/ask",
        json={"question": q_share},
        headers={"Authorization": f"Bearer {ravi_tok}"},
    )
    res_r2 = ask_ravi2.json()
    pass_r2 = share_ok and not res_r2.get("refused", True) and "DELTA-SEC-8819" in res_r2.get("answer", "")
    results.append({
        "test": "Shared colleague (Ravi) reads doc",
        "passed": pass_r2,
        "detail": f"refused={res_r2.get('refused')}",
    })

    # (e) Check unshared other dept (Karan) cannot read
    ask_karan = client.post(
        "/ask",
        json={"question": q_share},
        headers={"Authorization": f"Bearer {karan_tok}"},
    )
    res_k = ask_karan.json()
    pass_k = res_k.get("refused", False) is True
    results.append({
        "test": "Unshared other department (Karan) cannot read",
        "passed": pass_k,
        "detail": f"refused={res_k.get('refused')}",
    })

    # (f) Revoke share from Ravi
    share_id = None
    if share_ok:
        share_data = share_resp.json()
        share_id = share_data.get("share_id") or share_data.get("id")
    if share_id:
        client.delete(
            f"/api/documents/{doc_id}/share/{share_id}",
            headers={"Authorization": f"Bearer {asha_tok}"},
        )

    # (g) Check Ravi cannot read after revocation
    ask_ravi3 = client.post(
        "/ask",
        json={"question": q_share},
        headers={"Authorization": f"Bearer {ravi_tok}"},
    )
    res_r3 = ask_ravi3.json()
    pass_r3 = res_r3.get("refused", False) is True
    results.append({
        "test": "Revoked colleague (Ravi) cannot read",
        "passed": pass_r3,
        "detail": f"refused={res_r3.get('refused')}",
    })

    return results


def main():
    parser = argparse.ArgumentParser(description="Role Matrix Check Script")
    parser.add_argument("--base-url", default=None, help="Base URL of running VaultRAG API (default: in-process TestClient)")
    parser.add_argument("--questions", default=str(backend_dir / "tests" / "role_questions.json"), help="Path to role questions JSON file")
    args = parser.parse_args()

    client, is_in_process = get_client(args.base_url)
    mode_str = "In-Process TestClient" if is_in_process else f"Live API ({args.base_url})"

    q_file = Path(args.questions)
    if not q_file.exists():
        print(f"ERROR: Questions file not found at {q_file}")
        sys.exit(1)

    with open(q_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print("=" * 105)
    print("VaultRAG Role Matrix Check (Step 5e-fix v2)")
    print(f"Mode: {mode_str} | Questions: {len(questions)}")
    print("=" * 105)

    # Pre-login all users
    user_emails = sorted(list({q["user"] for q in questions}))
    tokens: dict[str, str] = {}
    print("\nAuthenticating users...")
    for email in user_emails:
        tokens[email] = login_user(client, email)
        print(f"  [OK] Authenticated: {email}")

    print("\nExecuting queries sequentially (no parallel GPU calls)...\n")

    user_stats = {
        email: {"total": 0, "passed": 0, "failed": 0, "failures": []}
        for email in user_emails
    }

    col_id = "ID"
    col_user = "User"
    col_q = "Question"
    col_exp = "Expected"
    col_act = "Actual"
    col_status = "Result"

    header = f"{col_id:<8} | {col_user:<18} | {col_q:<42} | {col_exp:<8} | {col_act:<8} | {col_status}"
    print(header)
    print("-" * len(header))

    t0_all = time.time()

    for idx, item in enumerate(questions, 1):
        qid = item.get("id", f"Q{idx:02d}")
        email = item["user"]
        q_text = item["question"]
        expected = item["expect"].lower()
        must_contain = item.get("must_contain", [])
        must_not_contain = item.get("must_not_contain", [])

        token = tokens[email]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post("/ask", json={"question": q_text}, headers=headers)
        if resp.status_code != 200:
            actual = "error"
            passed = False
            fail_reason = f"HTTP {resp.status_code}"
        else:
            data = resp.json()
            is_refused = bool(data.get("refused", False))
            actual = "refused" if is_refused else "answered"
            answer_text = data.get("answer", "")

            # Check expected vs actual
            passed = (actual == expected)
            fail_reason = ""
            if not passed:
                fail_reason = f"expected {expected}, got {actual}"

            # Check must_contain
            if passed and must_contain and actual == "answered":
                for mc in must_contain:
                    if mc.lower() not in answer_text.lower():
                        passed = False
                        fail_reason = f"missing must_contain token"
                        break

            # Check must_not_contain
            if passed and must_not_contain:
                for mnc in must_not_contain:
                    if mnc.lower() in answer_text.lower():
                        passed = False
                        fail_reason = f"found forbidden token"
                        break

        status_str = "PASS" if passed else "FAIL"

        user_short = email.split("@")[0]
        q_trunc = (q_text[:39] + "...") if len(q_text) > 42 else q_text

        print(f"{qid:<8} | {user_short:<18} | {q_trunc:<42} | {expected:<8} | {actual:<8} | {status_str}")

        user_stats[email]["total"] += 1
        if passed:
            user_stats[email]["passed"] += 1
        else:
            user_stats[email]["failed"] += 1
            user_stats[email]["failures"].append({
                "id": qid,
                "question": q_text,
                "expected": expected,
                "actual": actual,
                "reason": fail_reason,
            })

    total_time = time.time() - t0_all
    avg_latency = total_time / len(questions) if questions else 0.0

    # ── Upload Sharing Verification ──
    print("\n" + "=" * 105)
    print("Uploaded Document Sharing ACL Verification")
    print("=" * 105)
    upload_results = run_upload_sharing_test(client, tokens)
    upload_all_passed = True
    for ur in upload_results:
        res_str = "PASS" if ur["passed"] else "FAIL"
        if not ur["passed"]:
            upload_all_passed = False
        print(f"  [{res_str}] {ur['test']:<50} ({ur.get('detail', '')})")

    # ── Summary Tables ──
    print("\n" + "=" * 105)
    print("ROLE MATRIX SUMMARY PER USER")
    print("=" * 105)
    sum_header = f"{'User Email':<32} | {'Department':<12} | {'Total':<6} | {'Passed':<6} | {'Failed':<6} | {'Pass Rate'}"
    print(sum_header)
    print("-" * len(sum_header))

    user_depts = {
        "admin@northwind.example": "Admin",
        "meera.iyer@northwind.example": "HR",
        "karan.shah@northwind.example": "Finance",
        "asha.patel@northwind.example": "Engineering",
        "ravi.menon@northwind.example": "Engineering",
        "dev.joshi@northwind.example": "Sales",
        "neha.desai@northwind.example": "Sales",
    }

    grand_total = 0
    grand_passed = 0
    grand_failed = 0

    for email, stats in user_stats.items():
        grand_total += stats["total"]
        grand_passed += stats["passed"]
        grand_failed += stats["failed"]
        dept = user_depts.get(email, "-")
        rate = (stats["passed"] / stats["total"] * 100.0) if stats["total"] else 0.0
        print(f"{email:<32} | {dept:<12} | {stats['total']:<6} | {stats['passed']:<6} | {stats['failed']:<6} | {rate:>6.1f}%")

    print("-" * len(sum_header))
    grand_rate = (grand_passed / grand_total * 100.0) if grand_total else 0.0
    print(f"{'OVERALL TOTAL':<32} | {'ALL':<12} | {grand_total:<6} | {grand_passed:<6} | {grand_failed:<6} | {grand_rate:>6.1f}%")
    print(f"Total Test Duration: {total_time:.2f}s | Average Query Latency: {avg_latency:.2f}s/query")
    print("=" * 105)

    if grand_failed > 0:
        print("\nFAILURES REPORT (Reason Codes Only):")
        for email, stats in user_stats.items():
            for f in stats["failures"]:
                print(f"  [{f['id']}] User: {email} | Exp: {f['expected']} | Act: {f['actual']} | Reason: {f['reason']}")
        sys.exit(1)

    if not upload_all_passed:
        print("\nFAILURES in Upload Sharing verification!")
        sys.exit(1)

    print("\n[SUCCESS] ALL ROLE MATRIX QUESTIONS AND SHARING TESTS PASSED 100%!")


if __name__ == "__main__":
    main()
