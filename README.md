# VaultRAG

**Secure multi-modal RAG with row-level access control** — every retrieval respects who you are, what you're cleared to see, and which documents you own.

## The Problem

Standard RAG systems treat the vector store as a flat, open index. If you load sensitive HR, finance, and legal documents into one collection, any user can retrieve any chunk. VaultRAG solves this by enforcing access control **inside** every retrieval query, so users only ever see documents their roles and clearance allow.

## Architecture

```
User → API → Auth (JWT + DB reload) → Query Builder → SecureStore → Qdrant
                                            ↑
                                    ACL filter injected
                                    (roles, clearance, ownership)
```

1. **Ingest**: Documents are chunked, tagged with ACL metadata (owner, allowed roles, clearance level), and indexed into Qdrant with named dense (bge-m3) and sparse (BM25) vectors.
2. **Tag**: Each chunk carries `allowed_roles`, `allowed_users`, `classification`, `owner_id`, `is_public` in its Qdrant payload.
3. **Index**: The `SecureStore` gateway is the **only** module that touches Qdrant.
4. **Filter inside retrieval**: The server builds a Qdrant filter from the authenticated user's roles and clearance. The filter is applied **inside** the vector search — not after. Chunks the user cannot see are never returned.
5. **Verified citations**: Answers include source references that link back to the original document and page, so users can verify claims.

### Why the filter lives in the server, not in Qdrant

Qdrant has no built-in role-based access control. All access control comes from the filter built by our server code through the single `SecureStore` gateway, applied inside every search call. The client never supplies or influences the filter.

## Prerequisites

- Python 3.11+
- Docker Desktop (for Postgres and Qdrant)
- Git
- Ollama (installed natively, not in Docker) — needed for later steps

## Setup (PowerShell)

```powershell
# If script execution is blocked:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Clone and enter the repo
git clone <your-repo-url> VaultRAG
cd VaultRAG

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Copy environment config
Copy-Item .env.example .env
# ⚠️  Edit .env and set a real JWT_SECRET:
#     python -c "import secrets; print(secrets.token_urlsafe(64))"

# Start Postgres and Qdrant
docker compose up -d

# Create database tables
python backend/scripts/create_tables.py

# Seed demo users
python backend/scripts/seed_users.py

# Run the API
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests (in another terminal, with venv activated)
cd backend
pytest tests/ -v
```

## Demo Users

| Name  | Email                    | Role(s) | Clearance | Password       |
|-------|--------------------------|---------|-----------|----------------|
| Priya | priya@vaultrag.local     | admin   | 3         | changeme123 *  |
| Rahul | rahul@vaultrag.local     | hr      | 2         | changeme123 *  |
| Meera | meera@vaultrag.local     | finance | 2         | changeme123 *  |
| Arjun | arjun@vaultrag.local     | intern  | 1         | changeme123 *  |

\* **Demo only.** Set via `SEED_PASSWORD` env var. Never use in production.

## Security Principles

1. **Identity from the signed token only.** The JWT contains `sub` (user ID), `iat`, `exp`, and `jti` — nothing else. Roles are **never** stored in the token.
2. **Roles reloaded from the database on every request.** If an admin changes your roles, the change takes effect immediately without a new login.
3. **Server builds the filter.** The client never sends filter parameters. The server constructs the Qdrant filter from the authenticated user's DB record.
4. **Fail closed.** Any authentication or authorisation failure returns 401/403 and stops processing. The `search()` method requires an `acl_filter` argument with no default — if it's missing, the call fails.
5. **Only SecureStore touches Qdrant.** No other module imports `qdrant_client`. This single gateway ensures every query is filtered.

## API Endpoints

| Method | Path                          | Auth     | Description                  |
|--------|-------------------------------|----------|------------------------------|
| GET    | `/health`                     | None     | Postgres + Qdrant status     |
| POST   | `/auth/login`                 | None     | Get access token             |
| POST   | `/auth/register`              | None     | Self sign-up (no roles)      |
| GET    | `/auth/me`                    | Bearer   | Current user info            |
| POST   | `/admin/users`                | Admin    | Create user with roles       |
| GET    | `/admin/users`                | Admin    | List all users               |
| PUT    | `/admin/users/{id}/roles`     | Admin    | Update roles + clearance     |
| PUT    | `/admin/users/{id}/active`    | Admin    | Activate / deactivate user   |

## Roadmap

- [x] Project scaffold, auth, admin, health, audit trail
- [ ] Chunk schema design and PDF ingestion pipeline
- [ ] ACL filter builder and secure hybrid search (dense + sparse with RRF)
- [ ] Database row ingestion and OCR for scanned documents
- [ ] Grounded answers with citation verifier
- [ ] Frontend UI connection
- [ ] Document upload, sharing, and permission management
- [ ] Evaluation suite and end-to-end demo

## License

Private — not yet licensed for distribution.
