"""
Switch Admin Access Script: adds or removes role:admin in chunk ACL tokens in-place.

Idempotently updates existing points in Qdrant through SecureStore without re-embedding.

Usage:
  python scripts/set_admin_access.py --status
  python scripts/set_admin_access.py --on
  python scripts/set_admin_access.py --off
"""

import argparse
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.index.store import SecureStore


def get_status(store: SecureStore | None = None) -> dict[str, int]:
    """Get current admin access status across all points."""
    if store is None:
        store = SecureStore()
    status = store.get_admin_access_status()
    admin_pts = status["admin_points"]
    total_pts = status["total_points"]
    pct = (admin_pts / total_pts * 100.0) if total_pts > 0 else 0.0
    print(f"Admin access status: role:admin present in {admin_pts} / {total_pts} points ({pct:.1f}%)")
    return status


def set_access(enabled: bool, store: SecureStore | None = None) -> dict[str, int]:
    """Set admin access on or off in place."""
    if store is None:
        store = SecureStore()
    action_str = "enabling" if enabled else "disabling"
    print(f"{action_str.capitalize()} admin access in place (without re-embedding)...")
    res = store.set_admin_access(enabled=enabled)
    print(f"  Points scanned:         {res['scanned']}")
    print(f"  Points changed:         {res['changed']}")
    print(f"  Points already correct: {res['already_correct']}")
    return res


def main():
    parser = argparse.ArgumentParser(description="Switch platform admin access without re-embedding")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Print how many points contain role:admin out of the total")
    group.add_argument("--on", action="store_true", help="Add role:admin to acl_tokens of all points in place")
    group.add_argument("--off", action="store_true", help="Remove role:admin from acl_tokens of all points in place")

    args = parser.parse_args()
    store = SecureStore()

    if args.status:
        get_status(store)
    elif args.on:
        set_access(True, store)
        get_status(store)
    elif args.off:
        set_access(False, store)
        get_status(store)


if __name__ == "__main__":
    main()
