"""
Database table row ingestion for VaultRAG.

Ingests rows from SQLite dataset database (employees, salaries, expenses, approvals)
as searchable chunks with row-level and column-level permission tokens inside Qdrant.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.audit.logger import write_audit
from app.config import settings
from app.db.models import User
from app.db.session import SessionLocal
from app.index.embedder import DenseEmbedder, SparseEmbedder
from app.index.schema import Chunk
from app.index.store import SecureStore
from app.security.principals import finalize_acl_tokens

logger = logging.getLogger(__name__)


def inr_format(n: int | float | str) -> str:
    """Format integer with Indian digit grouping (e.g. 1234567 -> 12,34,567)."""
    try:
        val = int(n)
    except (ValueError, TypeError):
        return str(n)
    s = str(abs(val))
    neg = val < 0
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if neg else "") + s


def get_default_db_path() -> Path:
    """Resolve the default path to northwind.db."""
    candidates = [
        Path("D:/VaultRAG/data/northwind/rag_demo_dataset/dataset/database/northwind.db"),
        Path(settings.DATASET_DIR) / "dataset" / "database" / "northwind.db",
        Path(settings.DATASET_DIR) / "northwind" / "rag_demo_dataset" / "dataset" / "database" / "northwind.db",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def load_db_chunks(db_path: Path | str | None = None) -> list[Chunk]:
    """
    Read all rows from the database and construct Chunk objects with appropriate
    base and sensitive token assignments.
    """
    resolved_path = Path(db_path) if db_path else get_default_db_path()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Database file not found at {resolved_path}")

    con = sqlite3.connect(resolved_path)
    con.row_factory = sqlite3.Row

    try:
        employees = [dict(r) for r in con.execute("SELECT * FROM employees").fetchall()]
        salaries = [dict(r) for r in con.execute("SELECT * FROM salaries").fetchall()]
        expenses = [dict(r) for r in con.execute("SELECT * FROM expenses").fetchall()]
        approvals = [dict(r) for r in con.execute("SELECT * FROM approvals").fetchall()]
    finally:
        con.close()

    emp_map = {e["employee_id"]: e for e in employees}
    exp_map = {x["expense_id"]: x for x in expenses}

    chunks: list[Chunk] = []

    # ─────────────────────────────────────────────────────────────
    # 1. EMPLOYEES TABLE (25 rows -> 25 base + 25 sensitive chunks)
    # ─────────────────────────────────────────────────────────────
    # Base: directory is public to internal staff (roles employee, manager, hr_admin, finance_admin)
    # Sensitive: date_of_birth, personal_phone visible to hr_admin and employee themselves
    emp_base_roles = ["role:employee", "role:manager", "role:hr_admin", "role:finance_admin"]

    for e in employees:
        eid = e["employee_id"]
        mgr_id = e.get("manager_id")
        mgr_name = emp_map[mgr_id]["name"] if mgr_id and mgr_id in emp_map else "None"
        mgr_disp = f"{mgr_id} ({mgr_name})" if mgr_id else "None"

        # (a) Base chunk
        base_text = (
            f"Employee record {eid} (employees table): name {e['name']}, email {e['email']}, "
            f"department {e['department']}, designation {e['designation']}, grade {e['grade']}, "
            f"manager {mgr_disp}, joined {e['join_date']}, location {e['location']}, status {e['status']}."
        )
        base_tokens = finalize_acl_tokens(emp_base_roles)
        chunks.append(
            Chunk(
                chunk_id=f"db:employees#{eid}:base",
                doc_id="db_employees",
                source_doc="employees",
                source_id="db:employees",
                source_type="db_row",
                source_name="employees",
                corpus="main",
                file="employees",
                table="employees",
                row_pk=eid,
                row_id=eid,
                kind="db_row",
                page=None,
                chunk_type="text",
                text=base_text,
                acl_tokens=base_tokens,
            )
        )

        # (b) Sensitive chunk
        sens_text = (
            f"Sensitive employee record {eid} (employees table): name {e['name']}, "
            f"date of birth {e['date_of_birth']}, personal phone {e['personal_phone']}."
        )
        sens_tokens = finalize_acl_tokens(["role:hr_admin", f"emp:{eid}"])
        chunks.append(
            Chunk(
                chunk_id=f"db:employees#{eid}:sensitive",
                doc_id="db_employees",
                source_doc="employees",
                source_id="db:employees",
                source_type="db_row",
                source_name="employees",
                corpus="main",
                file="employees",
                table="employees",
                row_pk=eid,
                row_id=eid,
                kind="db_row",
                page=None,
                chunk_type="text",
                text=sens_text,
                acl_tokens=sens_tokens,
            )
        )

    # ─────────────────────────────────────────────────────────────
    # 2. SALARIES TABLE (25 rows -> 25 base + 25 sensitive chunks)
    # ─────────────────────────────────────────────────────────────
    # Base: annual_ctc, revision_pct, revised_ctc, effective_date visible to emp, hr_admin, finance_admin
    # Sensitive: bank_account_last4 visible to hr_admin and employee themselves
    for s in salaries:
        eid = s["employee_id"]
        emp_name = emp_map.get(eid, {}).get("name", eid)
        ann_ctc = s["annual_ctc"]
        rev_ctc = s["revised_ctc"]

        # (a) Base chunk
        base_text = (
            f"Salary record for {emp_name} (employee ID {eid}, salaries table): "
            f"annual CTC Rs {inr_format(ann_ctc)} ({ann_ctc}), revision percentage {s['revision_pct']}%, "
            f"revised CTC Rs {inr_format(rev_ctc)} ({rev_ctc}), effective date {s['effective_date']}."
        )
        base_tokens = finalize_acl_tokens([f"emp:{eid}", "role:hr_admin", "role:finance_admin"])
        chunks.append(
            Chunk(
                chunk_id=f"db:salaries#{eid}:base",
                doc_id="db_salaries",
                source_doc="salaries",
                source_id="db:salaries",
                source_type="db_row",
                source_name="salaries",
                corpus="main",
                file="salaries",
                table="salaries",
                row_pk=eid,
                row_id=eid,
                kind="db_row",
                page=None,
                chunk_type="text",
                text=base_text,
                acl_tokens=base_tokens,
            )
        )

        # (b) Sensitive chunk
        sens_text = (
            f"Sensitive salary record for {emp_name} (employee ID {eid}, salaries table): "
            f"bank account last 4 digits {s['bank_account_last4']} (bank_account_last4: {s['bank_account_last4']})."
        )
        sens_tokens = finalize_acl_tokens(["role:hr_admin", f"emp:{eid}"])
        chunks.append(
            Chunk(
                chunk_id=f"db:salaries#{eid}:sensitive",
                doc_id="db_salaries",
                source_doc="salaries",
                source_id="db:salaries",
                source_type="db_row",
                source_name="salaries",
                corpus="main",
                file="salaries",
                table="salaries",
                row_pk=eid,
                row_id=eid,
                kind="db_row",
                page=None,
                chunk_type="text",
                text=sens_text,
                acl_tokens=sens_tokens,
            )
        )

    # ─────────────────────────────────────────────────────────────
    # 3. EXPENSES TABLE (40 rows -> 40 base chunks, 0 sensitive)
    # ─────────────────────────────────────────────────────────────
    # Visible to:
    # - finance_admin (1=1)
    # - submitter (if employee or manager)
    # - line manager of submitter (rolemp:manager@mgr_id)
    # hr_admin is 0=1 (cannot access)
    for x in expenses:
        xid = x["expense_id"]
        eid = x["employee_id"]
        emp_submitter = emp_map.get(eid, {}).get("name", eid)
        mgr_id = emp_map.get(eid, {}).get("manager_id")
        amt = x["amount"]

        exp_text = (
            f"Expense claim {xid} (expenses table): submitted by {emp_submitter} (employee {eid}), "
            f"category {x['category']}, amount Rs {inr_format(amt)} ({amt}), expense date {x['expense_date']}, "
            f"description {x['description']}, vendor {x['vendor']}, invoice reference {x['invoice_ref']}, "
            f"status {x['status']}."
        )

        tokens = ["role:finance_admin", f"rolemp:employee@{eid}", f"rolemp:manager@{eid}"]
        if mgr_id:
            tokens.append(f"rolemp:manager@{mgr_id}")

        final_tokens = finalize_acl_tokens(tokens)
        chunks.append(
            Chunk(
                chunk_id=f"db:expenses#{xid}:base",
                doc_id="db_expenses",
                source_doc="expenses",
                source_id="db:expenses",
                source_type="db_row",
                source_name="expenses",
                corpus="main",
                file="expenses",
                table="expenses",
                row_pk=xid,
                row_id=xid,
                kind="db_row",
                page=None,
                chunk_type="text",
                text=exp_text,
                acl_tokens=final_tokens,
            )
        )

    # ─────────────────────────────────────────────────────────────
    # 4. APPROVALS TABLE (40 rows -> 40 base chunks, 0 sensitive)
    # ─────────────────────────────────────────────────────────────
    # Visible to:
    # - finance_admin (1=1)
    # - submitter of underlying expense (if employee or manager)
    # - line manager of submitter (rolemp:manager@mgr_id)
    # - approver (rolemp:manager@approver_id)
    # hr_admin is 0=1 (cannot access)
    for a in approvals:
        aid = a["approval_id"]
        xid = a["expense_id"]
        approver_id = a["approver_id"]
        approver_name = emp_map.get(approver_id, {}).get("name", approver_id)

        exp_row = exp_map.get(xid, {})
        eid = exp_row.get("employee_id")
        mgr_id = emp_map.get(eid, {}).get("manager_id") if eid else None

        comments = a.get("comments") or "No comments"
        decided = a.get("decided_on") or "pending"

        app_text = (
            f"Expense approval {aid} (approvals table): expense ID {xid}, "
            f"approver {approver_name} (employee {approver_id}), level {a['level']}, "
            f"decision {a['decision']}, decided on {decided}, comments {comments}."
        )

        tokens = ["role:finance_admin"]
        if eid:
            tokens.extend([f"rolemp:employee@{eid}", f"rolemp:manager@{eid}"])
        if mgr_id:
            tokens.append(f"rolemp:manager@{mgr_id}")
        if approver_id:
            tokens.append(f"rolemp:manager@{approver_id}")

        final_tokens = finalize_acl_tokens(tokens)
        chunks.append(
            Chunk(
                chunk_id=f"db:approvals#{aid}:base",
                doc_id="db_approvals",
                source_doc="approvals",
                source_id="db:approvals",
                source_type="db_row",
                source_name="approvals",
                corpus="main",
                file="approvals",
                table="approvals",
                row_pk=aid,
                row_id=aid,
                kind="db_row",
                page=None,
                chunk_type="text",
                text=app_text,
                acl_tokens=final_tokens,
            )
        )

    return chunks


def ingest_database(
    db_path: Path | str | None = None,
    store: SecureStore | None = None,
    embedder: Any = None,
    sparse: Any = None,
    collection: str | None = None,
    db_session: Session | None = None,
) -> list[dict[str, Any]]:
    """
    Ingest all database tables into Qdrant idempotently with dense & sparse vectors.
    Returns per-table ingestion summaries.
    """
    store = store or SecureStore()
    embedder = embedder or DenseEmbedder()
    sparse = sparse or SparseEmbedder()
    coll = collection or settings.QDRANT_COLLECTION

    chunks = load_db_chunks(db_path)

    # Group by table
    by_table: dict[str, list[Chunk]] = {
        "employees": [],
        "salaries": [],
        "expenses": [],
        "approvals": [],
    }
    for c in chunks:
        tbl = str(c.table or c.source_doc)
        if tbl in by_table:
            by_table[tbl].append(c)

    results: list[dict[str, Any]] = []

    own_db = False
    if db_session is None:
        db_session = SessionLocal()
        own_db = True

    try:
        admin_user = db_session.query(User).filter(User.external_id == "u_admin").first()
        admin_id = admin_user.id if admin_user else "u_admin"

        for table_name, tbl_chunks in by_table.items():
            if not tbl_chunks:
                continue

            doc_id = f"db_{table_name}"
            # Clean up existing points for this table for clean idempotence
            store.delete_by_doc(doc_id, collection=coll)

            texts = [c.text for c in tbl_chunks]
            dense_vectors = embedder.embed(texts)
            sparse_vectors = sparse.embed_sparse(texts)
            store.upsert_chunks(tbl_chunks, dense_vectors, sparse_vectors, collection=coll)

            base_count = sum(1 for c in tbl_chunks if c.chunk_id.endswith(":base"))
            sens_count = sum(1 for c in tbl_chunks if c.chunk_id.endswith(":sensitive"))
            row_count = base_count  # each row has exactly 1 base chunk

            # Audit record
            try:
                write_audit(
                    db_session,
                    user_id=admin_id,
                    event="ingest",
                    event_type="ingest",
                    refused=False,
                    reason_code=None,
                    chunk_count=len(tbl_chunks),
                    admin_access=True,
                    details={
                        "table": table_name,
                        "doc_id": doc_id,
                        "source_id": f"db:{table_name}",
                        "rows": row_count,
                        "base_chunks": base_count,
                        "sensitive_chunks": sens_count,
                        "total_chunks": len(tbl_chunks),
                    },
                )
            except Exception as e:
                logger.warning("Failed to record audit log for DB table %s: %s", table_name, e)

            summary = {
                "table": table_name,
                "doc_id": doc_id,
                "source_id": f"db:{table_name}",
                "rows": row_count,
                "base_chunks": base_count,
                "sensitive_chunks": sens_count,
                "total_chunks": len(tbl_chunks),
            }
            results.append(summary)

        return results
    finally:
        if own_db:
            db_session.close()
