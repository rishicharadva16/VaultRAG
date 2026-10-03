"""ACL manifest loader: resolves emails to user UUIDs for chunk tagging."""

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.security.users import get_user_by_email

logger = logging.getLogger(__name__)

# Default manifest path
_MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "acl_manifest.json"


def load_manifest(path: Path | None = None) -> dict:
    """Load the raw ACL manifest from JSON."""
    p = path or _MANIFEST_PATH
    if not p.exists():
        logger.warning("No ACL manifest at %s – all files will be admin-only", p)
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_manifest(db: Session, manifest: dict, filename: str) -> dict:
    """
    Resolve an ACL entry for a file. Returns:
    {owner_id, allowed_roles, allowed_users (UUIDs), classification, is_public}

    - If filename is not in the manifest, returns admin-only defaults with a warning.
    - If any email in the entry is not found in the DB, raises ValueError.
    """
    if filename not in manifest:
        # Default: admin-only, classification 3
        from app.db.models import User
        admin = db.query(User).filter(User.roles.any("admin")).first()
        if not admin:
            raise ValueError("No admin user found in the database – cannot default ACL")
        logger.warning(
            "File %r not in manifest – defaulting to admin-only, classification 3",
            filename,
        )
        return {
            "owner_id": admin.id,
            "allowed_roles": ["admin"],
            "allowed_users": [],
            "classification": 3,
            "is_public": False,
        }

    entry = manifest[filename]
    owner_email = entry["owner_email"]
    owner = get_user_by_email(db, owner_email)
    if owner is None:
        raise ValueError(
            f"File {filename!r}: owner email {owner_email!r} not found in the database"
        )

    allowed_users = []
    for email in entry.get("allowed_user_emails", []):
        user = get_user_by_email(db, email)
        if user is None:
            raise ValueError(
                f"File {filename!r}: allowed_user email {email!r} not found in the database"
            )
        allowed_users.append(user.id)

    return {
        "owner_id": owner.id,
        "allowed_roles": entry.get("allowed_roles", []),
        "allowed_users": allowed_users,
        "classification": entry.get("classification", 1),
        "is_public": entry.get("is_public", False),
    }
