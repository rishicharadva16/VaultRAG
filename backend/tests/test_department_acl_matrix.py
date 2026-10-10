"""
Department-Mode ACL Matrix Test (Step 5e-fix v2).

Verifies the canonical department access model rules across all users:
- Meera (HR)
- Karan (Finance)
- Asha (Engineering)
- Ravi (Engineering)
- Dev (Sales)
- Neha (Sales)
- System Admin (role:admin)
- Deactivated User (fails closed)

Rules verified:
1. Company policies: org:northwind (company-wide when POLICIES_COMPANY_WIDE=true) or dept:HR.
2. Board minutes: dept:Finance only (HR removed).
3. Vendor contract, finance memo, invoices, POs: dept:Finance only.
4. Hotel receipt: dept:Finance + emp:E1010.
5. Expenses & Approvals: dept:Finance + emp:<submitter>.
6. Salaries: dept:Finance + emp:<id> (Finance reads all, HR cannot read others, employee reads own).
7. Employees Base: dept:<own dept> + dept:HR + emp:<id> (HR reads all, dept colleagues read, employee reads own, other depts CANNOT).
8. Employees Sensitive & ID Cards: dept:HR + emp:<id> (HR reads all, Finance cannot read others, employee reads own).
9. Whiteboard: dept:Engineering only (HR removed).
10. Admin reads everything (via role:admin).
11. Deactivated user reads nothing.
"""

import pytest
from app.config import settings
from app.db.models import User
from app.security.principals import Principal, build_principal


@pytest.fixture(autouse=True)
def force_department_model(monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_MODEL", "department")
    monkeypatch.setattr(settings, "POLICIES_COMPANY_WIDE", True)


# Test User definitions
USERS = {
    "admin": {
        "id": "u_admin", "name": "System Admin", "department": None,
        "employee_id": None, "roles": ["admin"], "active": True,
    },
    "meera_hr": {
        "id": "u_meera", "name": "Meera Iyer", "department": "HR",
        "employee_id": "E1001", "roles": ["employee"], "active": True,
    },
    "karan_fin": {
        "id": "u_karan", "name": "Karan Shah", "department": "Finance",
        "employee_id": "E1002", "roles": ["employee"], "active": True,
    },
    "asha_eng": {
        "id": "u_asha", "name": "Asha Patel", "department": "Engineering",
        "employee_id": "E1004", "roles": ["employee"], "active": True,
    },
    "ravi_eng": {
        "id": "u_ravi", "name": "Ravi Menon", "department": "Engineering",
        "employee_id": "E1003", "roles": ["employee"], "active": True,
    },
    "dev_sales": {
        "id": "u_dev", "name": "Dev Joshi", "department": "Sales",
        "employee_id": "E1005", "roles": ["employee"], "active": True,
    },
    "neha_sales": {
        "id": "u_neha", "name": "Neha Desai", "department": "Sales",
        "employee_id": "E1006", "roles": ["employee"], "active": True,
    },
    "deactivated": {
        "id": "u_deact", "name": "Deactivated User", "department": "Finance",
        "employee_id": "E1099", "roles": ["employee"], "active": False,
    },
}


def can_read(user_key: str, chunk_tokens: list[str] | set[str]) -> bool:
    user_dict = USERS[user_key]
    user_obj = User(
        id=user_dict["id"],
        name=user_dict["name"],
        department=user_dict["department"],
        employee_id=user_dict["employee_id"],
        roles=user_dict["roles"],
        active=user_dict["active"],
    )
    p = build_principal(user_obj)
    return bool(set(p.tokens) & set(chunk_tokens))


# ── 1. Company Policies ──
def test_company_policies_company_wide(monkeypatch):
    """When POLICIES_COMPANY_WIDE=true, all active users can read."""
    monkeypatch.setattr(settings, "POLICIES_COMPANY_WIDE", True)
    policy_tokens = {"org:northwind", "role:admin"}
    for ukey, u in USERS.items():
        if u["active"]:
            assert can_read(ukey, policy_tokens), f"{ukey} should read company policy"
        else:
            assert not can_read(ukey, policy_tokens), f"{ukey} should NOT read company policy"


def test_company_policies_restricted_when_not_company_wide(monkeypatch):
    """When POLICIES_COMPANY_WIDE=false, policies are restricted to HR and Admin."""
    monkeypatch.setattr(settings, "POLICIES_COMPANY_WIDE", False)
    policy_tokens = {"dept:HR", "role:admin"}
    assert can_read("meera_hr", policy_tokens)
    assert can_read("admin", policy_tokens)
    assert not can_read("karan_fin", policy_tokens)
    assert not can_read("asha_eng", policy_tokens)
    assert not can_read("ravi_eng", policy_tokens)
    assert not can_read("dev_sales", policy_tokens)
    assert not can_read("neha_sales", policy_tokens)
    assert not can_read("deactivated", policy_tokens)


# ── 2. Board Minutes (Finance only, HR removed) ──
def test_board_minutes_finance_only_hr_removed():
    board_tokens = {"dept:Finance", "role:admin"}
    assert can_read("karan_fin", board_tokens)
    assert can_read("admin", board_tokens)
    assert not can_read("meera_hr", board_tokens), "HR must NOT read board minutes"
    assert not can_read("asha_eng", board_tokens)
    assert not can_read("ravi_eng", board_tokens)
    assert not can_read("dev_sales", board_tokens)
    assert not can_read("neha_sales", board_tokens)
    assert not can_read("deactivated", board_tokens)


# ── 3. Vendor Contract, Finance Memo, Invoices, Purchase Orders ──
def test_finance_documents_restricted_to_finance():
    fin_docs = {"dept:Finance", "role:admin"}
    assert can_read("karan_fin", fin_docs)
    assert can_read("admin", fin_docs)
    assert not can_read("meera_hr", fin_docs), "HR must NOT read finance docs"
    assert not can_read("asha_eng", fin_docs)
    assert not can_read("ravi_eng", fin_docs)
    assert not can_read("dev_sales", fin_docs)
    assert not can_read("neha_sales", fin_docs)
    assert not can_read("deactivated", fin_docs)


# ── 4. Hotel Receipt (Finance + Submitter) ──
def test_hotel_receipt_finance_and_submitter():
    receipt_tokens = {"dept:Finance", "emp:E1010", "role:admin"}
    assert can_read("karan_fin", receipt_tokens)
    assert can_read("admin", receipt_tokens)
    assert not can_read("meera_hr", receipt_tokens)
    assert not can_read("asha_eng", receipt_tokens)
    assert not can_read("ravi_eng", receipt_tokens)
    assert not can_read("dev_sales", receipt_tokens)
    assert not can_read("neha_sales", receipt_tokens)
    assert not can_read("deactivated", receipt_tokens)


# ── 5. Expenses and Approvals (Finance + Submitter) ──
def test_expenses_and_approvals_finance_and_owner():
    asha_expense = {"dept:Finance", "emp:E1004", "role:admin"}
    assert can_read("karan_fin", asha_expense)
    assert can_read("asha_eng", asha_expense)
    assert can_read("admin", asha_expense)
    assert not can_read("meera_hr", asha_expense), "HR must not read Asha's expense"
    assert not can_read("ravi_eng", asha_expense), "Ravi must not read Asha's expense"
    assert not can_read("dev_sales", asha_expense)
    assert not can_read("neha_sales", asha_expense)
    assert not can_read("deactivated", asha_expense)


# ── 6. Salary Rule (Finance reads all, HR cannot, employee reads own) ──
def test_salary_rule_all_users():
    asha_salary = {"dept:Finance", "emp:E1004", "role:admin"}
    karan_salary = {"dept:Finance", "emp:E1002", "role:admin"}
    meera_salary = {"dept:Finance", "emp:E1001", "role:admin"}
    dev_salary = {"dept:Finance", "emp:E1005", "role:admin"}

    # Finance reads all
    assert can_read("karan_fin", asha_salary)
    assert can_read("karan_fin", karan_salary)
    assert can_read("karan_fin", meera_salary)
    assert can_read("karan_fin", dev_salary)

    # HR cannot read others, reads own
    assert not can_read("meera_hr", asha_salary), "HR must not read Asha salary"
    assert not can_read("meera_hr", karan_salary), "HR must not read Karan salary"
    assert not can_read("meera_hr", dev_salary), "HR must not read Dev salary"
    assert can_read("meera_hr", meera_salary), "Meera reads own salary"

    # Employees read own, not others
    assert can_read("asha_eng", asha_salary)
    assert not can_read("asha_eng", karan_salary)
    assert not can_read("asha_eng", meera_salary)
    assert not can_read("asha_eng", dev_salary)

    assert can_read("dev_sales", dev_salary)
    assert not can_read("dev_sales", asha_salary)

    # Admin reads all, deactivated reads none
    assert can_read("admin", asha_salary)
    assert not can_read("deactivated", asha_salary)


# ── 7. Employees Base Records (dept:<emp dept> + dept:HR + emp:<id>) ──
def test_employees_base_record_matrix():
    """
    Base record: Asha is Engineering (E1004).
    - HR (Meera): CAN read.
    - Engineering colleague (Ravi): CAN read.
    - Asha herself: CAN read.
    - Admin: CAN read.
    - Finance (Karan): CANNOT read.
    - Sales (Dev, Neha): CANNOT read.
    - Deactivated: CANNOT read.
    """
    asha_base = {"dept:Engineering", "dept:HR", "emp:E1004", "role:admin"}

    assert can_read("asha_eng", asha_base), "Asha reads own base record"
    assert can_read("ravi_eng", asha_base), "Ravi (colleague in Engineering) reads Asha base"
    assert can_read("meera_hr", asha_base), "Meera (HR) reads Asha base"
    assert can_read("admin", asha_base), "Admin reads Asha base"

    assert not can_read("karan_fin", asha_base), "Karan (Finance) CANNOT read Asha base record"
    assert not can_read("dev_sales", asha_base), "Dev (Sales) CANNOT read Asha base record"
    assert not can_read("neha_sales", asha_base), "Neha (Sales) CANNOT read Asha base record"
    assert not can_read("deactivated", asha_base), "Deactivated user CANNOT read Asha base"

    # Karan is Finance (E1002)
    karan_base = {"dept:Finance", "dept:HR", "emp:E1002", "role:admin"}
    assert can_read("karan_fin", karan_base), "Karan reads own base record"
    assert can_read("meera_hr", karan_base), "Meera (HR) reads Karan base"
    assert can_read("admin", karan_base), "Admin reads Karan base"
    assert not can_read("asha_eng", karan_base), "Asha (Engineering) CANNOT read Karan base"
    assert not can_read("dev_sales", karan_base), "Dev (Sales) CANNOT read Karan base"

    # Dev is Sales (E1005)
    dev_base = {"dept:Sales", "dept:HR", "emp:E1005", "role:admin"}
    assert can_read("dev_sales", dev_base), "Dev reads own base record"
    assert can_read("neha_sales", dev_base), "Neha (Sales colleague) reads Dev base"
    assert can_read("meera_hr", dev_base), "Meera (HR) reads Dev base"
    assert not can_read("karan_fin", dev_base), "Karan (Finance) CANNOT read Dev base"
    assert not can_read("asha_eng", dev_base), "Asha (Engineering) CANNOT read Dev base"


# ── 8. Employees Sensitive Records & ID Cards (dept:HR + emp:<id>) ──
def test_employees_sensitive_and_id_cards():
    """
    Sensitive record / ID card: Asha (E1004).
    - HR (Meera): CAN read.
    - Asha herself: CAN read.
    - Admin: CAN read.
    - Ravi (colleague in Engineering): CANNOT read.
    - Karan (Finance): CANNOT read.
    - Dev / Neha (Sales): CANNOT read.
    """
    asha_sensitive = {"dept:HR", "emp:E1004", "role:admin"}
    asha_id_card = {"dept:HR", "emp:E1004", "role:admin"}

    for tokens in (asha_sensitive, asha_id_card):
        assert can_read("meera_hr", tokens), "HR reads sensitive / ID card"
        assert can_read("asha_eng", tokens), "Employee reads own sensitive / ID card"
        assert can_read("admin", tokens), "Admin reads sensitive / ID card"

        assert not can_read("ravi_eng", tokens), "Engineering colleague must NOT read sensitive / ID card"
        assert not can_read("karan_fin", tokens), "Finance must NOT read sensitive / ID card of Asha"
        assert not can_read("dev_sales", tokens), "Sales must NOT read sensitive / ID card of Asha"
        assert not can_read("neha_sales", tokens), "Sales must NOT read sensitive / ID card of Asha"
        assert not can_read("deactivated", tokens), "Deactivated user must NOT read sensitive / ID card"

    # Karan's sensitive: Karan reads own, Meera reads, others do not
    karan_sensitive = {"dept:HR", "emp:E1002", "role:admin"}
    assert can_read("karan_fin", karan_sensitive), "Karan reads own sensitive"
    assert can_read("meera_hr", karan_sensitive), "Meera reads Karan sensitive"
    assert not can_read("asha_eng", karan_sensitive), "Asha cannot read Karan sensitive"


# ── 9. Whiteboard (dept:Engineering only, HR removed) ──
def test_whiteboard_engineering_only_hr_removed():
    whiteboard_tokens = {"dept:Engineering", "role:admin"}
    assert can_read("asha_eng", whiteboard_tokens), "Asha (Engineering) reads whiteboard"
    assert can_read("ravi_eng", whiteboard_tokens), "Ravi (Engineering) reads whiteboard"
    assert can_read("admin", whiteboard_tokens), "Admin reads whiteboard"

    assert not can_read("meera_hr", whiteboard_tokens), "HR must NOT read whiteboard"
    assert not can_read("karan_fin", whiteboard_tokens), "Finance must NOT read whiteboard"
    assert not can_read("dev_sales", whiteboard_tokens), "Sales must NOT read whiteboard"
    assert not can_read("neha_sales", whiteboard_tokens), "Sales must NOT read whiteboard"
    assert not can_read("deactivated", whiteboard_tokens), "Deactivated user must NOT read whiteboard"


# ── 10. Admin Sees All Chunks ──
def test_admin_sees_all_documents_and_tables():
    all_token_groups = [
        {"org:northwind", "role:admin"},
        {"dept:Finance", "role:admin"},
        {"dept:Engineering", "role:admin"},
        {"dept:HR", "emp:E1004", "role:admin"},
        {"dept:Finance", "emp:E1004", "role:admin"},
        {"dept:Engineering", "dept:HR", "emp:E1004", "role:admin"},
    ]
    for group in all_token_groups:
        assert can_read("admin", group), f"Admin should read chunk with {group}"


# ── 11. Deactivated User Gets Nothing ──
def test_deactivated_user_reads_nothing():
    all_token_groups = [
        {"org:northwind", "role:admin"},
        {"dept:Finance", "role:admin"},
        {"dept:Engineering", "role:admin"},
        {"dept:HR", "emp:E1099", "role:admin"},
        {"dept:Finance", "emp:E1099", "role:admin"},
        {"dept:Finance", "dept:HR", "emp:E1099", "role:admin"},
    ]
    for group in all_token_groups:
        assert not can_read("deactivated", group), "Deactivated user must read nothing"
