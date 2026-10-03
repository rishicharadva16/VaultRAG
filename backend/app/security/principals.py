"""
Security principals and permission token generation.

Permission tokens map access control lists (roles, employees, departments, users)
into discrete, indexable tokens for row- and document-level security.
"""

from typing import Any

from app.security.roles import ROLES


def user_tokens(user: Any) -> set[str]:
    """
    Generate permission tokens held by a user.
    `user` can be an SQLAlchemy User model, a dict, or any object with
    roles, employee_id, department, external_id.
    """
    # Extract fields whether user is model or dict
    if isinstance(user, dict):
        roles = user.get("roles") or []
        emp_id = user.get("employee_id")
        dept = user.get("department")
        ext_id = user.get("external_id") or user.get("user_id")
    else:
        roles = getattr(user, "roles", None) or []
        emp_id = getattr(user, "employee_id", None)
        dept = getattr(user, "department", None)
        ext_id = getattr(user, "external_id", None) or getattr(user, "id", None)

    # In Northwind model, system admin and users with no document roles have 0 document tokens
    filtered_roles = [r for r in roles if r in ROLES and r != "admin"]
    if not filtered_roles:
        return set()

    tokens: set[str] = set()

    for r in filtered_roles:
        tokens.add(f"role:{r}")

    if emp_id:
        tokens.add(f"emp:{emp_id}")

    if dept:
        tokens.add(f"dept:{dept}")

    if emp_id:
        for r in filtered_roles:
            tokens.add(f"rolemp:{r}@{emp_id}")

    if ext_id:
        tokens.add(f"usr:{ext_id}")

    return tokens


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
