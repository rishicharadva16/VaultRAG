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
from app.ingestion.acl_policy import load_acl_policy
from app.security.principals import doc_tokens, user_tokens

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
    print("VaultRAG vs Reference ACL Access Matrix (19 Documents × 7 Accounts)")
    print("=" * 95)

    user_labels = [u["user_id"] for u in USERS]
    header = f"{'Document Source ID':<48} | " + " | ".join(f"{uid:^7}" for uid in user_labels)
    print(header)
    print("-" * len(header))

    mismatches = 0
    total_checks = 0

    for doc_id in doc_ids:
        acl = policy[doc_id]
        d_tokens = doc_tokens(acl)

        row_symbols = []
        for u in USERS:
            u_tokens = user_tokens(u)
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
                # System admin
                total_checks += 1
                if vaultrag_can_read:
                    mismatches += 1
                    symbol = "ERR"
                else:
                    symbol = "  .  "  # Admin has 0 document access

            row_symbols.append(symbol)

        print(f"{doc_id:<48} | " + " | ".join(f"{s:^7}" for s in row_symbols))

    print("-" * len(header))
    print(f"Total evaluated cell checks: {total_checks}")
    print(f"Total mismatches with reference acl.py: {mismatches}")
    if mismatches == 0:
        print("[SUCCESS] 100% MATCH: VaultRAG permission tokens perfectly replicate dataset ACL rules!")
    else:
        print(f"[FAIL] Found {mismatches} mismatches!")
        sys.exit(1)


if __name__ == "__main__":
    main()
