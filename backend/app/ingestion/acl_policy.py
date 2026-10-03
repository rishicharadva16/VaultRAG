"""
ACL policy loader for dataset documents.

Loads document ACL specifications from acl_policy.json and validates roles.
Fail-closed: unlisted documents return None and must be rejected.
"""

import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.security.roles import ROLES

_DOC_ACLS: dict[str, dict[str, Any]] | None = None


def find_acl_policy_file(custom_path: Path | None = None) -> Path:
    """Locate acl_policy.json within the dataset directory."""
    if custom_path and custom_path.exists():
        return custom_path

    ds_path = settings.dataset_path()
    candidates = [
        ds_path / "dataset" / "acl" / "acl_policy.json",
        ds_path / "acl" / "acl_policy.json",
        ds_path / "acl_policy.json",
    ]
    for p in candidates:
        if p.exists():
            return p

    raise FileNotFoundError(f"acl_policy.json not found in candidate paths under {ds_path}")


def load_acl_policy(path: Path | None = None, force_reload: bool = False) -> dict[str, dict[str, Any]]:
    """
    Load and cache documents ACL dictionary from acl_policy.json.
    Keys are source_ids (e.g. 'pdf:hr_policy.pdf', 'poison:poison_01_vendor_onboarding_checklist.pdf').
    """
    global _DOC_ACLS
    if _DOC_ACLS is not None and not force_reload and path is None:
        return _DOC_ACLS

    policy_file = find_acl_policy_file(path)
    with open(policy_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    docs = data.get("documents", {})
    # Validate roles in policy
    for source_id, acl in docs.items():
        for role in acl.get("allowed_roles", []):
            if role not in ROLES:
                raise ValueError(f"Invalid role {role!r} in ACL for {source_id}")

    _DOC_ACLS = docs
    return _DOC_ACLS


def resolve_source_id(filename: str, prefix: str | None = None) -> str:
    """
    Resolve the source_id key for a document filename.
    Poison docs start with 'poison:' regardless of file extension.
    """
    fn = Path(filename).name
    if prefix:
        return f"{prefix}:{fn}"

    if fn.startswith("poison_"):
        return f"poison:{fn}"

    ext = Path(fn).suffix.lower()
    if ext == ".pdf":
        return f"pdf:{fn}"
    elif ext in (".png", ".jpg", ".jpeg"):
        return f"img:{fn}"
    elif ext in (".md", ".html"):
        return f"poison:{fn}"
    return f"doc:{fn}"


def get_document_acl(source_id: str, policy: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """
    Retrieve ACL for a source_id. Returns None if unlisted (fail-closed).
    """
    if policy is None:
        policy = load_acl_policy()
    return policy.get(source_id)
