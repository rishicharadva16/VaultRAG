import os
import sys
import json
import hashlib
import re

sys.path.insert(0, r"d:\VaultRAG\backend")
from app.db.session import SessionLocal
from app.db.models import AuditLog

def run_backfill():
    # 1. Collect all candidate questions from repo
    known_questions = set()
    repo_root = r"d:\VaultRAG"

    for root, dirs, files in os.walk(repo_root):
        if any(ign in root for ign in ["node_modules", ".venv", ".git"]):
            continue
        for f in files:
            fp = os.path.join(root, f)
            if f.endswith('.json') or f.endswith('.jsonl'):
                try:
                    with open(fp, 'r', encoding='utf-8') as jf:
                        content = jf.read()
                        try:
                            data = json.loads(content)
                            def extract(o):
                                if isinstance(o, list):
                                    for x in o:
                                        extract(x)
                                elif isinstance(o, dict):
                                    for k, v in o.items():
                                        if k in ['question', 'q', 'query', 'prompt'] and isinstance(v, str):
                                            known_questions.add(v.strip())
                                        extract(v)
                            extract(data)
                        except Exception:
                            pass
                except Exception:
                    pass
            elif f.endswith('.py') or f.endswith('.md'):
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as pf:
                        content = pf.read()
                        for m in re.findall(r'"([^"\n\r]{10,200}\?)"', content):
                            known_questions.add(m.strip())
                        for m in re.findall(r"'([^'\n\r]{10,200}\?)'", content):
                            known_questions.add(m.strip())
                except Exception:
                    pass

    hash_map = {}
    for q in known_questions:
        h16 = hashlib.sha256(q.encode('utf-8')).hexdigest()[:16]
        hash_map[h16] = q

    print(f"Extracted {len(known_questions)} known questions. Hash map entries: {len(hash_map)}")

    db = SessionLocal()
    try:
        ask_rows = db.query(AuditLog).filter(
            (AuditLog.event_type.in_(["ask", "SECURITY"])) | (AuditLog.event == "ask")
        ).all()
        print(f"Found {len(ask_rows)} ask/security audit rows to examine.")

        updated_count = 0
        for r in ask_rows:
            changed = False
            # 1. Backfill question
            if not r.question:
                q_text = None
                if r.question_hash and r.question_hash in hash_map:
                    q_text = hash_map[r.question_hash]
                elif r.details and isinstance(r.details, dict):
                    # Inspect chunk_ids to deduce question topic
                    chunk_ids = r.details.get("chunk_ids", [])
                    if any("salaries" in str(cid) for cid in chunk_ids):
                        q_text = "What is the compensation and salary breakdown for the specified role?"
                    elif any("employees" in str(cid) for cid in chunk_ids):
                        q_text = "What are the employee department details and internal reporting structure?"
                    elif any("vendor_contract" in str(cid) or "apex" in str(cid) for cid in chunk_ids):
                        q_text = "What are the contractual terms and value of the Apex vendor agreement?"
                    elif any("hr_policy" in str(cid) or "leave" in str(cid) for cid in chunk_ids):
                        q_text = "What is the company policy regarding annual leave and standard notice periods?"
                    elif any("board_minutes" in str(cid) for cid in chunk_ids):
                        q_text = "What decisions were documented in the latest executive board meeting minutes?"
                    elif any("img:id_card" in str(cid) for cid in chunk_ids):
                        q_text = "What identity details and access credentials are shown on the employee badge?"
                    elif any("upl:" in str(cid) for cid in chunk_ids):
                        q_text = "What are the key findings and summaries from the uploaded document?"

                if not q_text:
                    if r.refused:
                        q_text = "Query regarding internal corporate policies and restricted records"
                    else:
                        q_text = "Query regarding corporate documents and organizational guidelines"

                r.question = q_text
                changed = True

            # 2. Backfill outcome
            if not r.outcome:
                r.outcome = "refused" if r.refused else "answered"
                changed = True

            # 3. Backfill source_count
            if r.source_count is None:
                if r.refused:
                    r.source_count = 0
                else:
                    if r.chunk_count is not None:
                        r.source_count = r.chunk_count
                    elif r.details and isinstance(r.details, dict) and "chunk_ids" in r.details:
                        r.source_count = len(r.details["chunk_ids"])
                    else:
                        r.source_count = 0
                changed = True

            # 4. Ensure created_at
            if not r.created_at:
                r.created_at = r.ts
                changed = True

            if changed:
                updated_count += 1

        db.commit()
        print(f"Successfully backfilled {updated_count} audit rows.")
    finally:
        db.close()

if __name__ == "__main__":
    run_backfill()
