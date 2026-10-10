"""
Shared test fixtures.

Tests run against a SEPARATE database (vaultrag_test) on the same Compose Postgres.
The test DB is created automatically if it doesn't exist.
"""

import os

# Point at the test database BEFORE any app imports
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://vaultrag:changeme@localhost:5432/vaultrag_test",
)

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db.models import Base, User
from app.db.session import get_db
from app.main import app
from app.security.passwords import hash_password

from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Ensure the test database exists
# ---------------------------------------------------------------------------
_admin_url = settings.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
_admin_engine = create_engine(_admin_url, isolation_level="AUTOCOMMIT")
with _admin_engine.connect() as conn:
    exists = conn.execute(
        text("SELECT 1 FROM pg_database WHERE datname = 'vaultrag_test'")
    ).scalar()
    if not exists:
        conn.execute(text("CREATE DATABASE vaultrag_test"))
_admin_engine.dispose()

# ---------------------------------------------------------------------------
# Test engine / session
# ---------------------------------------------------------------------------
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)

SEED_PASSWORD = "changeme123"

SEED_USERS = [
    {"user_id": "u_asha",  "name": "Asha Patel",   "email": "asha.patel@northwind.example",   "roles": ["employee"],      "employee_id": "E1004", "department": "Engineering"},
    {"user_id": "u_neha",  "name": "Neha Desai",   "email": "neha.desai@northwind.example",   "roles": ["employee"],      "employee_id": "E1006", "department": "Sales"},
    {"user_id": "u_ravi",  "name": "Ravi Menon",   "email": "ravi.menon@northwind.example",   "roles": ["manager"],       "employee_id": "E1003", "department": "Engineering"},
    {"user_id": "u_dev",   "name": "Dev Joshi",    "email": "dev.joshi@northwind.example",    "roles": ["manager"],       "employee_id": "E1005", "department": "Sales"},
    {"user_id": "u_meera", "name": "Meera Iyer",   "email": "meera.iyer@northwind.example",   "roles": ["hr_admin"],      "employee_id": "E1001", "department": "HR"},
    {"user_id": "u_karan", "name": "Karan Shah",   "email": "karan.shah@northwind.example",   "roles": ["finance_admin"], "employee_id": "E1002", "department": "Finance"},
    {"user_id": "u_admin", "name": "System Admin", "email": "admin@northwind.example",        "roles": ["admin"],         "employee_id": None,    "department": None},
]


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables, run migrations, and seed users once per test session."""
    Base.metadata.create_all(bind=engine)
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
        conn.execute(text("UPDATE audit_log SET event_type = event WHERE event_type IS NULL AND event IS NOT NULL;"))
        conn.execute(text("UPDATE audit_log SET created_at = ts WHERE created_at IS NULL AND ts IS NOT NULL;"))

        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS shown_in_demo BOOLEAN DEFAULT FALSE;"))

        # Step 6 migrations for documents and document_shares
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_documents_source_id ON documents (source_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_owner_id ON documents (owner_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_sha256 ON documents (sha256);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_shares_doc_id ON document_shares (document_id);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_document_shares_grantee ON document_shares (document_id, grantee_type, grantee_value);"))
        conn.execute(text("ALTER TABLE document_shares ADD COLUMN IF NOT EXISTS include_sensitive BOOLEAN DEFAULT FALSE;"))
        conn.commit()

    db = TestSession()
    try:
        pw_hash = hash_password(SEED_PASSWORD)
        demo_visible_ids = {"u_admin", "u_meera", "u_karan", "u_asha"}
        for u in SEED_USERS:
            existing = db.query(User).filter(
                (User.email == u["email"]) | (User.external_id == u["user_id"])
            ).first()
            user_roles = u["roles"]
            if settings.ACCESS_MODEL == "department":
                user_roles = ["admin"] if "admin" in u["roles"] else ["employee"]
            is_visible = u["user_id"] in demo_visible_ids
            if existing:
                existing.name = u["name"]
                existing.email = u["email"]
                existing.password_hash = pw_hash
                existing.roles = user_roles
                existing.employee_id = u["employee_id"]
                existing.department = u["department"]
                existing.external_id = u["user_id"]
                existing.shown_in_demo = is_visible
                existing.active = True
            else:
                db.add(User(
                    name=u["name"],
                    email=u["email"],
                    password_hash=pw_hash,
                    roles=user_roles,
                    employee_id=u["employee_id"],
                    department=u["department"],
                    external_id=u["user_id"],
                    shown_in_demo=is_visible,
                    active=True,
                ))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture()
def db():
    """Yield a DB session for direct queries in tests."""
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
async def client(db):
    """Provide an httpx AsyncClient wired to the FastAPI app with the test DB."""
    def _override_get_db():
        try:
            yield db
        finally:
            pass  # session closed by the db fixture

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
