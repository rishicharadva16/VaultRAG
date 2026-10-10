"""
Security principals and permission token generation.

Permission tokens map access control lists (roles, employees, departments, users)
into discrete, indexable tokens for row- and document-level security.
"""

from dataclasses import dataclass
from typing import Any

from app.security.roles import ROLES


@dataclass(frozen=True)
class Principal:
    user_id: str
    tokens: list[str]
    name: str | None = None
    employee_id: str | None = None
    department: str | None = None


LEGACY_DATASET_ROLES: dict[str, list[str]] = {
    "u_meera": ["hr_admin"],
    "u_karan": ["finance_admin"],
    "u_ravi": ["manager"],
    "u_dev": ["manager"],
    "u_asha": ["employee"],
    "u_neha": ["employee"],
    "u_admin": ["admin"],
}


def build_principal(user: Any) -> Principal:
    """
    Build a security Principal from a database user model or dictionary.
    Freshly built on every request from DB-loaded user attributes.

    Department mode (Step 5e default):
      org:northwind (every active user)
      dept:<Department>
      emp:<employee_id>
      usr:<uuid>
      role:employee or role:admin (exactly one user has role admin)

    Dataset mode (legacy):
      role:<role> for each role
      emp:<employee_id>
      dept:<department>
      rolemp:<role>@<employee_id>
      usr:<user_id>
      org:northwind
    """
    if isinstance(user, dict):
        user_id = str(user.get("id") or user.get("user_id") or "")
        ext_id = str(user.get("external_id") or "")
        name = user.get("name")
        roles = list(user.get("roles") or [])
        emp_id = user.get("employee_id")
        dept = user.get("department")
        active = user.get("active", user.get("is_active", True))
    else:
        user_id = str(getattr(user, "id", "") or getattr(user, "user_id", "") or "")
        ext_id = str(getattr(user, "external_id", "") or "")
        name = getattr(user, "name", None)
        roles = list(getattr(user, "roles", None) or [])
        emp_id = getattr(user, "employee_id", None)
        dept = getattr(user, "department", None)
        active = getattr(user, "active", getattr(user, "is_active", True))

    # Deactivated users get NO tokens (fail closed)
    if active is False:
        return Principal(user_id=user_id or ext_id, tokens=[], name=name, employee_id=emp_id, department=dept)

    from app.config import settings
    access_model = getattr(settings, "ACCESS_MODEL", "department").lower()

    tokens: set[str] = set()

    if access_model == "department":
        # 1. Company token for all active users
        tokens.add("org:northwind")

        # 2. Department token
        if dept:
            tokens.add(f"dept:{dept}")

        # 3. Employee ID token
        if emp_id:
            tokens.add(f"emp:{emp_id}")

        # 4. User ID tokens
        if user_id:
            tokens.add(f"usr:{user_id}")
        if ext_id and ext_id != user_id:
            tokens.add(f"usr:{ext_id}")

        # 5. Role token: exactly one admin, everyone else employee
        if "admin" in roles:
            tokens.add("role:admin")
        else:
            tokens.add("role:employee")

        return Principal(user_id=user_id or ext_id, tokens=sorted(tokens), name=name, employee_id=emp_id, department=dept)

    # ── Dataset Mode (legacy) ──
    # If DB roles were updated to ["employee"], recover legacy roles for dataset mode
    if ext_id in LEGACY_DATASET_ROLES and roles == ["employee"]:
        effective_roles = LEGACY_DATASET_ROLES[ext_id]
    elif user_id in LEGACY_DATASET_ROLES and roles == ["employee"]:
        effective_roles = LEGACY_DATASET_ROLES[user_id]
    else:
        effective_roles = roles

    if "admin" in effective_roles:
        tokens.add("role:admin")
        tokens.add("org:northwind")
        return Principal(user_id=user_id or ext_id, tokens=sorted(tokens), name=name, employee_id=emp_id, department=dept)

    filtered_roles = [r for r in effective_roles if r in ROLES and r != "admin"]
    if not filtered_roles:
        return Principal(user_id=user_id or ext_id, tokens=[], name=name, employee_id=emp_id, department=dept)

    tokens.add("org:northwind")
    for r in filtered_roles:
        tokens.add(f"role:{r}")

    if emp_id:
        tokens.add(f"emp:{emp_id}")

    if dept:
        tokens.add(f"dept:{dept}")

    if emp_id:
        for r in filtered_roles:
            tokens.add(f"rolemp:{r}@{emp_id}")

    if user_id:
        tokens.add(f"usr:{user_id}")
    if ext_id and ext_id != user_id:
        tokens.add(f"usr:{ext_id}")

    return Principal(user_id=user_id or ext_id, tokens=sorted(tokens), name=name, employee_id=emp_id, department=dept)


def user_tokens(user: Any) -> set[str]:
    """
    Generate document permission tokens held by a user as a set.
    Admin role gets no document tokens (role:admin is not a document token).
    """
    from app.config import settings
    access_model = getattr(settings, "ACCESS_MODEL", "department").lower()
    if access_model == "dataset":
        p = build_principal(user)
        return {t for t in p.tokens if t not in ("role:admin", "org:northwind")}
    return {t for t in build_principal(user).tokens if t != "role:admin"}


def doc_tokens(acl: dict) -> set[str]:
    """
    Generate permission tokens required to read a document or chunk.
    `acl` can contain:
      - allowed_roles: list[str]
      - allowed_employees: list[str]
      - allowed_departments: list[str]
      - allowed_users: list[str]
    """
    tokens: set[str] = set()

    for r in acl.get("allowed_roles") or []:
        if r in ROLES and r != "admin":
            tokens.add(f"role:{r}")

    for emp in acl.get("allowed_employees") or []:
        if emp:
            tokens.add(f"emp:{emp}")

    for dept in acl.get("allowed_departments") or []:
        if dept:
            tokens.add(f"dept:{dept}")

    for u in acl.get("allowed_users") or []:
        if u:
            tokens.add(f"usr:{u}")

    return tokens


def finalize_acl_tokens(
    tokens: list[str] | set[str],
    admin_sees_all: bool | None = None,
) -> list[str]:
    """
    Finalize chunk permission tokens for ingestion and storage:
      - Deduplicate tokens
      - Append 'role:admin' if ADMIN_SEES_ALL is True
      - Return a sorted, unique list of token strings
    Used by all ingestion paths (PDF, DB rows, image chunks).
    """
    if admin_sees_all is None:
        from app.config import settings
        admin_sees_all = getattr(settings, "ADMIN_SEES_ALL", True)

    token_set = set(tokens)
    if admin_sees_all:
        token_set.add("role:admin")

    return sorted(token_set)
