"""
Tests for security principals and permission token evaluation.
Compares token intersections against the dataset reference acl.py.
"""

import importlib.util
import sys
from pathlib import Path
import pytest

# Ensure no __pycache__ created in data directory
sys.dont_write_bytecode = True

from app.config import settings
from app.ingestion.acl_policy import load_acl_policy
from app.security.principals import doc_tokens, user_tokens


# Dynamically load dataset acl.py without writing bytecode
dataset_dir = settings.dataset_path()
acl_py_path = dataset_dir / "acl.py"
if str(dataset_dir) not in sys.path:
    sys.path.insert(0, str(dataset_dir))

spec = importlib.util.spec_from_file_location("ref_acl", str(acl_py_path))
ref_acl = importlib.util.module_from_spec(spec)
sys.modules["ref_acl"] = ref_acl
spec.loader.exec_module(ref_acl)


DATASET_USERS = [
    {"user_id": "u_asha",  "name": "Asha Patel",   "roles": ["employee"],      "employee_id": "E1004", "department": "Engineering"},
    {"user_id": "u_neha",  "name": "Neha Desai",   "roles": ["employee"],      "employee_id": "E1006", "department": "Sales"},
    {"user_id": "u_ravi",  "name": "Ravi Menon",   "roles": ["manager"],       "employee_id": "E1003", "department": "Engineering"},
    {"user_id": "u_dev",   "name": "Dev Joshi",    "roles": ["manager"],       "employee_id": "E1005", "department": "Sales"},
    {"user_id": "u_meera", "name": "Meera Iyer",   "roles": ["hr_admin"],      "employee_id": "E1001", "department": "HR"},
    {"user_id": "u_karan", "name": "Karan Shah",   "roles": ["finance_admin"], "employee_id": "E1002", "department": "Finance"},
]

ADMIN_USER = {
    "user_id": "u_admin", "name": "System Admin", "roles": ["admin"], "employee_id": None, "department": None
}

EMPTY_USER = {
    "user_id": "u_empty", "name": "No Roles", "roles": [], "employee_id": None, "department": None
}


def test_user_tokens_generation():
    asha = DATASET_USERS[0]
    tokens = user_tokens(asha)
    assert "role:employee" in tokens
    assert "emp:E1004" in tokens
    assert "dept:Engineering" in tokens
    assert "rolemp:employee@E1004" in tokens
    assert "usr:u_asha" in tokens


def test_admin_has_no_document_tokens():
    tokens = user_tokens(ADMIN_USER)
    assert len(tokens) == 0


def test_empty_user_has_no_tokens():
    tokens = user_tokens(EMPTY_USER)
    assert len(tokens) == 0


def test_doc_tokens_hr_policy():
    acl = {"allowed_roles": ["employee", "manager", "hr_admin", "finance_admin"]}
    tokens = doc_tokens(acl)
    assert tokens == {"role:employee", "role:manager", "role:hr_admin", "role:finance_admin"}


def test_doc_tokens_with_employee_and_dept():
    acl_emp = {"allowed_roles": ["hr_admin"], "allowed_employees": ["E1004"]}
    tokens_emp = doc_tokens(acl_emp)
    assert "role:hr_admin" in tokens_emp
    assert "emp:E1004" in tokens_emp

    acl_dept = {"allowed_roles": ["hr_admin"], "allowed_departments": ["Engineering"]}
    tokens_dept = doc_tokens(acl_dept)
    assert "role:hr_admin" in tokens_dept
    assert "dept:Engineering" in tokens_dept


def test_all_19_documents_match_reference_acl_for_all_users():
    policy = load_acl_policy()
    assert len(policy) >= 19

    for doc_id, acl in policy.items():
        d_tokens = doc_tokens(acl)
        assert len(d_tokens) > 0, f"Document {doc_id} must have non-empty tokens"

        for u in DATASET_USERS:
            u_tokens = user_tokens(u)
            can_read_vaultrag = bool(u_tokens & d_tokens)
            can_read_reference = ref_acl.can_read_source(u["user_id"], doc_id)

            assert can_read_vaultrag == can_read_reference, (
                f"Mismatch for user={u['user_id']} on doc={doc_id}: "
                f"VaultRAG={can_read_vaultrag}, Ref={can_read_reference}"
            )

        # Admin has 0 document access
        admin_tokens = user_tokens(ADMIN_USER)
        assert not bool(admin_tokens & d_tokens), f"Admin should not have access to {doc_id}"

        # Empty user has 0 document access
        empty_tokens = user_tokens(EMPTY_USER)
        assert not bool(empty_tokens & d_tokens), f"Empty user should not have access to {doc_id}"
