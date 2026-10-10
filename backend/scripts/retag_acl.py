"""
ACL Retag Script for VaultRAG.

Retags dataset points in Qdrant in-place using set_payload (no re-embedding).
Supports:
  --model department (Step 5e default: department ACLs with salary rule)
  --model dataset    (Legacy dataset role-based model)
  --dry-run          (Preview changes without updating Qdrant)

Never touches uploaded points (source_ids starting with 'upl:').
Keeps a backup of previous payload tags in a JSON file for rollback/restoration.
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.index.store import SecureStore
from app.security.principals import finalize_acl_tokens

DEFAULT_BACKUP_PATH = Path(__file__).resolve().parent / "retag_backup.json"


def load_employee_dept_map() -> dict[str, str]:
    """Return {employee_id: department} from employees.csv."""
    ds_dir = settings.dataset_path()
    employees_csv = ds_dir / "dataset" / "database" / "employees.csv"
    emp_to_dept = {}
    if employees_csv.exists():
        with open(employees_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                emp_to_dept[row["employee_id"].strip()] = row["department"].strip()
    return emp_to_dept


def load_expense_and_approval_maps() -> tuple[dict[str, str], dict[str, str]]:
    """Return {expense_id: employee_id} and {approval_id: employee_id}."""
    ds_dir = settings.dataset_path()
    expenses_csv = ds_dir / "dataset" / "database" / "expenses.csv"
    approvals_csv = ds_dir / "dataset" / "database" / "approvals.csv"

    exp_to_emp = {}
    if expenses_csv.exists():
        with open(expenses_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                exp_to_emp[row["expense_id"].strip()] = row["employee_id"].strip()

    app_to_emp = {}
    if approvals_csv.exists():
        with open(approvals_csv, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                aid = row["approval_id"].strip()
                xid = row["expense_id"].strip()
                if xid in exp_to_emp:
                    app_to_emp[aid] = exp_to_emp[xid]

    return exp_to_emp, app_to_emp


def compute_department_tokens(
    source_id: str,
    chunk_id: str,
    exp_to_emp: dict[str, str],
    app_to_emp: dict[str, str],
    emp_to_dept: dict[str, str],
    current_tokens: list[str],
) -> list[str]:
    """Compute canonical department-mode tokens for a dataset chunk."""
    # 1. Company policies & poison files
    policies_cw = getattr(settings, "POLICIES_COMPANY_WIDE", True)
    policy_tokens = ["org:northwind"] if policies_cw else ["dept:HR"]
    if source_id in (
        "pdf:hr_policy.pdf",
        "pdf:leave_policy.pdf",
        "pdf:travel_expense_policy.pdf",
        "pdf:it_security_policy.pdf",
        "poison:poison_01_vendor_onboarding_checklist.pdf",
        "poison:poison_02_helpdesk_faq.md",
        "poison:poison_03_cafeteria_holiday_notice.html",
    ):
        return finalize_acl_tokens(policy_tokens)

    # 2. Board minutes -> Finance (HR removed)
    if source_id == "pdf:board_minutes_2026_08.pdf":
        return finalize_acl_tokens(["dept:Finance"])

    # 3. Vendor contract, finance memo -> Finance
    if source_id in ("pdf:vendor_contract_apex.pdf", "pdf:finance_memo_q2_fy27.pdf"):
        return finalize_acl_tokens(["dept:Finance"])

    # 4. Invoices and Purchase orders -> Finance
    if source_id.startswith("img:invoice_") or source_id.startswith("img:purchase_order_"):
        return finalize_acl_tokens(["dept:Finance"])

    # 5. Receipts -> Finance + emp:<id>
    if source_id == "img:receipt_hotel_lotus.png":
        return finalize_acl_tokens(["dept:Finance", "emp:E1010"])

    # 6. ID cards -> HR + emp:<id>
    if source_id.startswith("img:id_card_"):
        card_emp = source_id.replace("img:id_card_", "").split(".")[0]
        return finalize_acl_tokens(["dept:HR", f"emp:{card_emp}"])

    # 7. Whiteboard -> Engineering (HR removed)
    if source_id == "img:whiteboard_sprint.jpg":
        return finalize_acl_tokens(["dept:Engineering"])

    # 8. Employees table chunks
    # Base: dept:<employee's own dept>, dept:HR, emp:<id>, role:admin
    # Sensitive: dept:HR, emp:<id>, role:admin
    if source_id == "db:employees":
        eid = chunk_id.split("#")[1].split(":")[0]
        if chunk_id.endswith(":base"):
            emp_dept = emp_to_dept.get(eid)
            tokens = ["dept:HR", f"emp:{eid}"]
            if emp_dept:
                tokens.append(f"dept:{emp_dept}")
            return finalize_acl_tokens(tokens)
        elif chunk_id.endswith(":sensitive"):
            return finalize_acl_tokens(["dept:HR", f"emp:{eid}"])

    # 9. Salaries table chunks (base and sensitive: Finance + emp:<id>, HR excluded)
    if source_id == "db:salaries":
        eid = chunk_id.split("#")[1].split(":")[0]
        return finalize_acl_tokens(["dept:Finance", f"emp:{eid}"])

    # 10. Expenses table chunks -> Finance + emp:<submitter>
    if source_id == "db:expenses":
        xid = chunk_id.split("#")[1].split(":")[0]
        eid = exp_to_emp.get(xid)
        if not eid:
            for t in current_tokens:
                if t.startswith("emp:"):
                    eid = t.split(":")[1]
                    break
                elif t.startswith("rolemp:employee@"):
                    eid = t.split("@")[1]
                    break
        if eid:
            return finalize_acl_tokens(["dept:Finance", f"emp:{eid}"])
        return finalize_acl_tokens(["dept:Finance"])

    # 11. Approvals table chunks -> Finance + emp:<submitter>
    if source_id == "db:approvals":
        aid = chunk_id.split("#")[1].split(":")[0]
        eid = app_to_emp.get(aid)
        if not eid:
            for t in current_tokens:
                if t.startswith("emp:"):
                    eid = t.split(":")[1]
                    break
                elif t.startswith("rolemp:employee@"):
                    eid = t.split("@")[1]
                    break
        if eid:
            return finalize_acl_tokens(["dept:Finance", f"emp:{eid}"])
        return finalize_acl_tokens(["dept:Finance"])

    # If any unhandled source occurs: fail-safe
    raise ValueError(f"Unhandled dataset source_id: {source_id} (chunk_id: {chunk_id})")

def load_dataset_tokens_map() -> dict[str, list[str]]:
    """Compute exact legacy dataset tokens for all dataset chunks."""
    from app.ingestion.acl_policy import load_acl_policy
    from app.security.principals import doc_tokens
    from app.ingestion.db_ingestion import load_db_chunks

    token_map: dict[str, list[str]] = {}
    policy = load_acl_policy()
    for src_id, acl in policy.items():
        token_map[src_id] = finalize_acl_tokens(doc_tokens(acl))

    old_model = getattr(settings, "ACCESS_MODEL", "department")
    try:
        settings.ACCESS_MODEL = "dataset"
        db_chunks = load_db_chunks()
        for c in db_chunks:
            token_map[c.chunk_id] = finalize_acl_tokens(c.acl_tokens)
    finally:
        settings.ACCESS_MODEL = old_model

    return token_map


def main():
    parser = argparse.ArgumentParser(description="Retag dataset points ACL in Qdrant (in place)")
    parser.add_argument(
        "--model",
        choices=["department", "dataset"],
        default="department",
        help="Access model to tag points with (default: department)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying Qdrant")
    parser.add_argument("--backup-file", type=Path, default=DEFAULT_BACKUP_PATH, help="Path for backup JSON file")
    args = parser.parse_args()

    store = SecureStore()
    all_points = store.scroll_all_points()

    # Filter out uploaded points
    dataset_points = [p for p in all_points if not str(p.payload.get("source_id", "")).startswith("upl:")]
    upl_count = len(all_points) - len(dataset_points)

    print("=" * 95)
    print(f"VaultRAG In-Place ACL Retagging Tool (Model: {args.model.upper()})")
    print(f"Total points in collection: {len(all_points)} (Dataset: {len(dataset_points)}, Uploads skipped: {upl_count})")
    print(f"Dry Run: {args.dry_run}")
    print("=" * 95)

    # 1. Create / update backup file
    backup_data: dict[str, dict] = {}
    if args.backup_file.exists():
        try:
            with open(args.backup_file, "r", encoding="utf-8") as f:
                backup_data = json.load(f)
        except Exception:
            backup_data = {}

    if args.model == "department":
        # Save snapshot of pre-department tags if not already saved
        snapshot = {
            str(p.id): {
                "chunk_id": p.payload.get("chunk_id"),
                "source_id": p.payload.get("source_id"),
                "acl_tokens": sorted(p.payload.get("acl_tokens", [])),
            }
            for p in dataset_points
        }
        with open(args.backup_file, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        print(f"[OK] Backup of {len(snapshot)} point ACLs saved to {args.backup_file}")
        backup_data = snapshot

    exp_to_emp, app_to_emp = load_expense_and_approval_maps()
    emp_to_dept = load_employee_dept_map()

    # 2. Compute new ACL tokens for every dataset point
    updates = []
    old_token_counts = Counter()
    new_token_counts = Counter()
    mapping_samples: dict[str, tuple[list[str], list[str]]] = {}
    dataset_token_map = None

    for p in dataset_points:
        pid = p.id
        payload = p.payload or {}
        src_id = str(payload.get("source_id", ""))
        chunk_id = str(payload.get("chunk_id", ""))
        curr_tokens = sorted(payload.get("acl_tokens", []))
        old_token_counts[tuple(curr_tokens)] += 1

        if args.model == "department":
            new_tokens = compute_department_tokens(
                source_id=src_id,
                chunk_id=chunk_id,
                exp_to_emp=exp_to_emp,
                app_to_emp=app_to_emp,
                emp_to_dept=emp_to_dept,
                current_tokens=curr_tokens,
            )
        else:
            # Dataset model: reconstruct exact legacy dataset tokens
            if dataset_token_map is None:
                dataset_token_map = load_dataset_tokens_map()
            if chunk_id in dataset_token_map:
                new_tokens = dataset_token_map[chunk_id]
            elif src_id in dataset_token_map:
                new_tokens = dataset_token_map[src_id]
            else:
                new_tokens = curr_tokens

        new_tokens = sorted(new_tokens)
        new_token_counts[tuple(new_tokens)] += 1
        updates.append((pid, new_tokens))

        # Sample for mapping table report
        mapping_key = src_id
        if src_id.startswith("db:"):
            tbl_type = ":base" if ":base" in chunk_id else ":sensitive"
            mapping_key = f"{src_id}{tbl_type}"
        if mapping_key not in mapping_samples:
            mapping_samples[mapping_key] = (curr_tokens, new_tokens)

    # 3. Print Applied Mapping Table
    print("\nApplied ACL Mapping Table:")
    print(f"{'Source Pattern':<32} | {'Old Sample Tokens':<42} -> {'New Sample Tokens'}")
    print("-" * 115)
    for k in sorted(mapping_samples.keys()):
        old_s, new_s = mapping_samples[k]
        old_str = ", ".join(old_s)[:40]
        new_str = ", ".join(new_s)
        print(f"{k:<32} | {old_str:<42} -> {new_str}")

    # 4. Print Token Set Counts (Before & After)
    print("\nToken Set Distribution Comparison:")
    print(f"Previous Unique Token Sets: {len(old_token_counts)}")
    for t_set, cnt in old_token_counts.most_common(5):
        print(f"  {cnt:>3}x : {list(t_set)}")
    if len(old_token_counts) > 5:
        print(f"  ... and {len(old_token_counts) - 5} more sets")

    print(f"\nNew Unique Token Sets ({args.model.upper()}): {len(new_token_counts)}")
    for t_set, cnt in new_token_counts.most_common(10):
        print(f"  {cnt:>3}x : {list(t_set)}")

    # 5. Execute Update
    if args.dry_run:
        print(f"\n[DRY RUN] Would update {len(updates)} points in Qdrant with new payload. No changes made.")
    else:
        updated = store.batch_update_acl_tokens(updates)
        print(f"\n[SUCCESS] Successfully updated {updated} points in Qdrant with {args.model.upper()} ACL tokens!")


if __name__ == "__main__":
    main()
