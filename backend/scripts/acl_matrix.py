"""
ACL Access Matrix: checks user tokens vs document tokens for all 19 dataset documents
across all 7 accounts, comparing results against the reference acl.py.

Usage:
  python scripts/acl_matrix.py
"""

import importlib.util
import sys
from pathlib import Path

# CRITICAL: Prevent bytecode generation in read-only data directory
sys.dont_write_bytecode = True

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
settings.ACCESS_MODEL = "dataset"
from app.ingestion.acl_policy import load_acl_policy
from app.security.principals import build_principal, doc_tokens, finalize_acl_tokens, user_tokens

# Load reference acl.py dynamically without writing bytecode
dataset_dir = settings.dataset_path()
acl_py_path = dataset_dir / "acl.py"
if not acl_py_path.exists():
    raise FileNotFoundError(f"Reference acl.py not found at {acl_py_path}")

spec = importlib.util.spec_from_file_location("dataset_acl", str(acl_py_path))
dataset_acl = importlib.util.module_from_spec(spec)
sys.modules["dataset_acl"] = dataset_acl
# Also allow acl.py to find facts.py in dataset_dir
if str(dataset_dir) not in sys.path:
    sys.path.insert(0, str(dataset_dir))
spec.loader.exec_module(dataset_acl)

# Users to evaluate
USERS = [
    {"user_id": "u_asha",  "name": "Asha (Emp)",    "roles": ["employee"],      "employee_id": "E1004", "department": "Engineering"},
    {"user_id": "u_neha",  "name": "Neha (Emp)",    "roles": ["employee"],      "employee_id": "E1006", "department": "Sales"},
    {"user_id": "u_ravi",  "name": "Ravi (Mgr)",    "roles": ["manager"],       "employee_id": "E1003", "department": "Engineering"},
    {"user_id": "u_dev",   "name": "Dev (Mgr)",     "roles": ["manager"],       "employee_id": "E1005", "department": "Sales"},
    {"user_id": "u_meera", "name": "Meera (HR)",    "roles": ["hr_admin"],      "employee_id": "E1001", "department": "HR"},
    {"user_id": "u_karan", "name": "Karan (Fin)",   "roles": ["finance_admin"], "employee_id": "E1002", "department": "Finance"},
    {"user_id": "u_admin", "name": "Admin (Admin)", "roles": ["admin"],         "employee_id": None,    "department": None},
]


def main():
    policy = load_acl_policy()
    doc_ids = sorted(policy.keys())

    print("=" * 95)
    img_count = sum(1 for d in doc_ids if d.startswith("img:"))
    print(f"VaultRAG vs Reference ACL Access Matrix ({len(doc_ids)} Documents [{img_count} Images, {len(doc_ids)-img_count} Text/Poison] × {len(USERS)} Accounts = {len(doc_ids)*len(USERS)} Cells)")
    print("=" * 95)

    user_labels = [u["user_id"] for u in USERS]
    header = f"{'Document Source ID':<48} | " + " | ".join(f"{uid:^7}" for uid in user_labels)
    print(header)
    print("-" * len(header))

    mismatches = 0
    total_checks = 0
    admin_exceptions = 0

    for doc_id in doc_ids:
        acl = policy[doc_id]
        base_tokens = doc_tokens(acl)
        d_tokens = set(finalize_acl_tokens(base_tokens))

        row_symbols = []
        for u in USERS:
            # Build principal tokens
            p = build_principal(u)
            u_tokens = set(p.tokens)
            vaultrag_can_read = bool(u_tokens & d_tokens)

            # Compare against reference acl.py for dataset users
            if u["user_id"] in dataset_acl.ROLE_OF:
                total_checks += 1
                ref_can_read = dataset_acl.can_read_source(u["user_id"], doc_id)
                if vaultrag_can_read != ref_can_read:
                    mismatches += 1
                    symbol = "ERR"
                else:
                    symbol = " YES " if vaultrag_can_read else "  .  "
            else:
                # System admin (u_admin): single intended exception to dataset acl.py
                total_checks += 1
                if vaultrag_can_read:
                    admin_exceptions += 1
                    symbol = " YES "
                else:
                    mismatches += 1
                    symbol = "ERR"

            row_symbols.append(symbol)

        print(f"{doc_id:<48} | " + " | ".join(f"{s:^7}" for s in row_symbols))

    print("-" * len(header))
    print(f"Total document checks: {total_checks} ({img_count * len(USERS)} image checks across {len(USERS)} users)")
    print(f"Document mismatches on dataset user rules: {mismatches}")


    # ─────────────────────────────────────────────────────────────
    # PART 2: Database Table Row & Column Level Matrix
    # ─────────────────────────────────────────────────────────────
    from app.ingestion.db_ingestion import get_default_db_path, load_db_chunks

    db_path = get_default_db_path()
    db_chunks = load_db_chunks(db_path)

    print("\n" + "=" * 95)
    print("VaultRAG vs Reference Database ACL Matrix (4 Tables, 180 Chunks × 7 Accounts)")
    print("=" * 95)

    db_mismatches = 0
    db_total_checks = 0
    db_admin_exceptions = 0

    # Pre-fetch allowed rows per table for all dataset users
    ref_rows_cache = {}
    for u in USERS:
        uid = u["user_id"]
        if uid in dataset_acl.ROLE_OF:
            ref_rows_cache[uid] = {}
            for tbl in ["employees", "salaries", "expenses", "approvals"]:
                rows = dataset_acl.allowed_rows(db_path, uid, tbl)
                pk_col = "employee_id" if tbl in ("employees", "salaries") else ("expense_id" if tbl == "expenses" else "approval_id")
                ref_rows_cache[uid][tbl] = {r[pk_col]: dict(r) for r in rows}

    # Summary counts: table -> user -> count of accessible chunks
    tbl_user_counts = {tbl: {u["user_id"]: 0 for u in USERS} for tbl in ["employees", "salaries", "expenses", "approvals"]}

    for c in db_chunks:
        tbl = str(c.table)
        pk = str(c.row_pk)
        is_sensitive = c.chunk_id.endswith(":sensitive")

        for u in USERS:
            uid = u["user_id"]
            db_total_checks += 1
            p = build_principal(u)
            u_tokens = set(p.tokens)
            vaultrag_can_read = bool(u_tokens & set(c.acl_tokens))

            if vaultrag_can_read:
                tbl_user_counts[tbl][uid] += 1

            if uid in dataset_acl.ROLE_OF:
                ref_map = ref_rows_cache[uid].get(tbl, {})
                ref_can_read = pk in ref_map
                if ref_can_read and is_sensitive:
                    if tbl == "employees":
                        ref_can_read = "date_of_birth" in ref_map[pk]
                    elif tbl == "salaries":
                        ref_can_read = "bank_account_last4" in ref_map[pk]

                if vaultrag_can_read != ref_can_read:
                    db_mismatches += 1
                    print(f"  [MISMATCH] user={uid} chunk={c.chunk_id} (vaultrag={vaultrag_can_read}, ref={ref_can_read})")
            else:
                # u_admin exception
                if vaultrag_can_read:
                    db_admin_exceptions += 1
                else:
                    db_mismatches += 1

    # Print summary table
    db_header = f"{'Table (Total Chunks)':<25} | " + " | ".join(f"{uid:^7}" for uid in user_labels)
    print(db_header)
    print("-" * len(db_header))
    for tbl in ["employees", "salaries", "expenses", "approvals"]:
        tbl_total = sum(1 for c in db_chunks if c.table == tbl)
        counts = [f"{tbl_user_counts[tbl][uid]}/{tbl_total}" for uid in user_labels]
        print(f"{tbl + f' ({tbl_total})':<25} | " + " | ".join(f"{cnt:^7}" for cnt in counts))

    print("-" * len(db_header))
    print(f"Total database checks: {db_total_checks}")
    print(f"Database mismatches on dataset user rules: {db_mismatches}")
    print(
        f"[INTENDED EXCEPTION] Platform admin (u_admin) can read all 180 database chunks "
        f"({db_admin_exceptions} allowed via ADMIN_SEES_ALL role:admin chunk ACL token; "
        f"dataset acl.py reference grants admin no database access)."
    )

    all_mismatches = mismatches + db_mismatches
    if all_mismatches == 0:
        print("\n[SUCCESS] 100% MATCH: Documents + Database records perfectly replicate dataset ACL rules (with intended admin exceptions)!")
    else:
        print(f"\n[FAIL] Found {all_mismatches} total mismatches!")
        sys.exit(1)


if __name__ == "__main__":
    main()
