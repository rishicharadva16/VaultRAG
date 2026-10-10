"""Create all database tables and apply migrations (idempotent)."""

import os
import sys

# Add backend to path so `app` is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import text
from app.db.models import Base
from app.db.session import engine


def create_tables():
    print("Creating tables …")
    Base.metadata.create_all(bind=engine)

    # Idempotent migration for Northwind user attributes
    print("Applying migrations for Northwind employee fields …")
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS employee_id VARCHAR;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS department VARCHAR;"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS external_id VARCHAR;"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_external_id ON users (external_id);"))
        conn.execute(text("ALTER TABLE users DROP COLUMN IF EXISTS clearance;"))

        # Idempotent migration for audit_log query event fields
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS event_type VARCHAR;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS refused BOOLEAN;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS reason_code VARCHAR;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS latency_ms FLOAT;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS chunk_count INTEGER;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS admin_access BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS question_hash VARCHAR;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS question_length INTEGER;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS question VARCHAR;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS outcome VARCHAR;"))
        conn.execute(text("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS source_count INTEGER;"))
        # Backfill existing event -> event_type and ts -> created_at if NULL
        conn.execute(text("UPDATE audit_log SET event_type = event WHERE event_type IS NULL AND event IS NOT NULL;"))
        conn.execute(text("UPDATE audit_log SET created_at = ts WHERE created_at IS NULL AND ts IS NOT NULL;"))

        # Step 6: Idempotent migration for documents and document_shares
        print("Applying migrations for documents and document_shares …")
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_documents_source_id ON documents (source_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_owner_id ON documents (owner_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_sha256 ON documents (sha256);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_shares_doc_id ON document_shares (document_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_document_shares_grantee ON document_shares (document_id, grantee_type, grantee_value);"))
        conn.execute(text("ALTER TABLE document_shares ADD COLUMN IF NOT EXISTS include_sensitive BOOLEAN DEFAULT FALSE;"))
        conn.commit()

    print("Done.")


if __name__ == "__main__":
    create_tables()
