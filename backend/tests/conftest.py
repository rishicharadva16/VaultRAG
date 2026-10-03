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
    {"name": "Priya",  "email": "priya@vaultrag.local",  "roles": ["admin"],   "clearance": 3},
    {"name": "Rahul",  "email": "rahul@vaultrag.local",  "roles": ["hr"],      "clearance": 2},
    {"name": "Meera",  "email": "meera@vaultrag.local",  "roles": ["finance"], "clearance": 2},
    {"name": "Arjun",  "email": "arjun@vaultrag.local",  "roles": ["intern"],  "clearance": 1},
]


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables and seed users once per test session."""
    Base.metadata.create_all(bind=engine)
    db = TestSession()
    try:
        pw_hash = hash_password(SEED_PASSWORD)
        for u in SEED_USERS:
            if not db.query(User).filter(User.email == u["email"]).first():
                db.add(User(
                    name=u["name"], email=u["email"],
                    password_hash=pw_hash,
                    roles=u["roles"], clearance=u["clearance"],
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
