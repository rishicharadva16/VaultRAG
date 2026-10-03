"""
Seed demo users (idempotent – skips if email already exists).

Demo password is read from the SEED_PASSWORD env var (default: changeme123).
WARNING: These credentials are for local development ONLY. Never use in production.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.models import User
from app.db.session import SessionLocal
from app.security.passwords import hash_password

SEED_PASSWORD = os.environ.get("SEED_PASSWORD", "changeme123")

USERS = [
    {"name": "Priya",  "email": "priya@vaultrag.local",  "roles": ["admin"],   "clearance": 3},
    {"name": "Rahul",  "email": "rahul@vaultrag.local",  "roles": ["hr"],      "clearance": 2},
    {"name": "Meera",  "email": "meera@vaultrag.local",  "roles": ["finance"], "clearance": 2},
    {"name": "Arjun",  "email": "arjun@vaultrag.local",  "roles": ["intern"],  "clearance": 1},
]


def seed():
    db = SessionLocal()
    try:
        pw_hash = hash_password(SEED_PASSWORD)
        for u in USERS:
            existing = db.query(User).filter(User.email == u["email"]).first()
            if existing:
                print(f"  * {u['name']} already exists, skipping")
                continue
            db.add(User(
                name=u["name"],
                email=u["email"],
                password_hash=pw_hash,
                roles=u["roles"],
                clearance=u["clearance"],
            ))
            print(f"  + Created {u['name']} ({u['email']})")
        db.commit()

        # Print summary table
        print()
        print(f"  {'Name':<10} {'Email':<30} {'Roles':<15} {'Clr':>3}  {'ID'}")
        print(f"  {'-'*10} {'-'*30} {'-'*15} {'-'*3}  {'-'*36}")
        for u in USERS:
            row = db.query(User).filter(User.email == u["email"]).first()
            if row:
                roles_str = ",".join(row.roles) if row.roles else "(none)"
                print(f"  {row.name:<10} {row.email:<30} {roles_str:<15} {row.clearance:>3}  {row.id}")
        print()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
