"""
Seed Northwind dataset users and system admin (idempotent).

Reads:
- data/northwind/rag_demo_dataset/dataset/acl/users_roles.json
- data/northwind/rag_demo_dataset/dataset/database/employees.csv

Creates:
- 6 dataset users with employee metadata and role
- 1 platform admin: admin@northwind.example (u_admin)
Marks legacy demo users (Priya, Rahul, Meera, Arjun) inactive without deleting them.

Demo password is read from the SEED_PASSWORD env var (default: changeme123).
WARNING: These credentials are for local development ONLY. Never use in production.
"""

import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.security.passwords import hash_password

SEED_PASSWORD = os.environ.get("SEED_PASSWORD", "changeme123")

LEGACY_EMAILS = [
    "priya@vaultrag.local",
    "rahul@vaultrag.local",
    "meera@vaultrag.local",
    "arjun@vaultrag.local",
]


def load_employee_records(csv_path: Path) -> dict[str, dict]:
    employees = {}
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            emp_id = row["employee_id"].strip()
            employees[emp_id] = {
                "name": row["name"].strip(),
                "email": row["email"].strip(),
                "department": row["department"].strip(),
            }
    return employees


def seed():
    dataset_dir = settings.dataset_path()
    users_roles_path = dataset_dir / "dataset" / "acl" / "users_roles.json"
    employees_path = dataset_dir / "dataset" / "database" / "employees.csv"

    if not users_roles_path.exists():
        print(f"ERROR: Cannot find {users_roles_path}")
        sys.exit(1)
    if not employees_path.exists():
        print(f"ERROR: Cannot find {employees_path}")
        sys.exit(1)

    with open(users_roles_path, mode="r", encoding="utf-8") as f:
        user_roles_data = json.load(f)

    employees = load_employee_records(employees_path)
    pw_hash = hash_password(SEED_PASSWORD)
    db = SessionLocal()

    try:
        # 1. Mark legacy demo users inactive
        for legacy_email in LEGACY_EMAILS:
            legacy_user = db.query(User).filter(User.email == legacy_email).first()
            if legacy_user and legacy_user.active:
                legacy_user.active = False
                print(f"  - Marked legacy user inactive: {legacy_email}")
        db.commit()

        # 2. Seed / update Northwind users
        seeded_users = []
        for u in user_roles_data["users"]:
            uid = u["user_id"]
            emp_id = u["employee_id"]
            role = u["role"]
            emp_meta = employees.get(emp_id, {})
            name = emp_meta.get("name", uid)
            email = emp_meta.get("email", f"{uid}@northwind.example")
            dept = emp_meta.get("department")

            user = db.query(User).filter(
                (User.external_id == uid) | (User.email == email)
            ).first()

            if user:
                user.name = name
                user.email = email
                user.roles = [role]
                user.employee_id = emp_id
                user.department = dept
                user.external_id = uid
                user.password_hash = pw_hash
                user.active = True
                print(f"  * Updated dataset user: {uid} ({email})")
            else:
                user = User(
                    name=name,
                    email=email,
                    password_hash=pw_hash,
                    roles=[role],
                    employee_id=emp_id,
                    department=dept,
                    external_id=uid,
                    active=True,
                )
                db.add(user)
                print(f"  + Created dataset user: {uid} ({email})")
            seeded_users.append(uid)

        # 3. Seed / update platform admin
        admin_email = "admin@northwind.example"
        admin_ext = "u_admin"
        admin_user = db.query(User).filter(
            (User.external_id == admin_ext) | (User.email == admin_email)
        ).first()

        if admin_user:
            admin_user.name = "System Admin"
            admin_user.email = admin_email
            admin_user.roles = ["admin"]
            admin_user.employee_id = None
            admin_user.department = None
            admin_user.external_id = admin_ext
            admin_user.password_hash = pw_hash
            admin_user.active = True
            print(f"  * Updated admin user: {admin_ext} ({admin_email})")
        else:
            admin_user = User(
                name="System Admin",
                email=admin_email,
                password_hash=pw_hash,
                roles=["admin"],
                employee_id=None,
                department=None,
                external_id=admin_ext,
                active=True,
            )
            db.add(admin_user)
            print(f"  + Created admin user: {admin_ext} ({admin_email})")
        seeded_users.append(admin_ext)

        db.commit()

        # Print summary table
        print()
        print(f"  {'External ID':<12} {'Name':<16} {'Email':<30} {'Role':<15} {'Emp ID':<8} {'Department':<14} {'Active'}")
        print(f"  {'-'*12} {'-'*16} {'-'*30} {'-'*15} {'-'*8} {'-'*14} {'-'*6}")

        all_seeded = db.query(User).filter(User.external_id.in_(seeded_users)).order_by(User.external_id).all()
        for row in all_seeded:
            role_str = ",".join(row.roles) if row.roles else "(none)"
            emp_str = row.employee_id or "-"
            dept_str = row.department or "-"
            print(
                f"  {row.external_id:<12} {row.name:<16} {row.email:<30} "
                f"{role_str:<15} {emp_str:<8} {dept_str:<14} {row.active}"
            )
        print()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
