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


def build_principal(user: Any) -> Principal:
    """
    Build a security Principal from a database user model or dictionary.
    Freshly built on every request from DB-loaded user attributes.
    Tokens generated:
      role:<role> for each role
      emp:<employee_id>
      dept:<department>
      rolemp:<role>@<employee_id>
      usr:<user_id>
    Platform admin role gets ONLY 'role:admin' (which appears in no document ACL).
    Empty or null source values are skipped.
    """
    if isinstance(user, dict):
        user_id = str(user.get("id") or user.get("user_id") or "")
        roles = user.get("roles") or []
        emp_id = user.get("employee_id")
        dept = user.get("department")
    else:
        user_id = str(getattr(user, "id", "") or getattr(user, "user_id", "") or "")
        roles = getattr(user, "roles", None) or []
        emp_id = getattr(user, "employee_id", None)
        dept = getattr(user, "department", None)

    tokens: set[str] = set()

    # B3: Platform admin role gets no document tokens beyond role:admin
    if "admin" in roles:
        tokens.add("role:admin")
        return Principal(user_id=user_id, tokens=sorted(tokens))

    filtered_roles = [r for r in roles if r in ROLES and r != "admin"]
    if not filtered_roles:
        return Principal(user_id=user_id, tokens=[])

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

    return Principal(user_id=user_id, tokens=sorted(tokens))


def user_tokens(user: Any) -> set[str]:
    """
    Generate document permission tokens held by a user as a set.
    Admin role gets no document tokens (role:admin is not a document token).
    """
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
