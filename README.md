# VaultRAG

**Secure multi-modal RAG with row/document-level access control** — every retrieval respects who you are, what you're cleared to see, and which documents you own.

---

## The Problem

Standard RAG systems treat the vector store as a flat, open index. If sensitive HR, finance, and operational documents are indexed together, any user can retrieve any chunk. VaultRAG solves this by enforcing access control **inside** every retrieval query using discrete **permission tokens**, ensuring users only ever receive chunks their roles, employee ID, department, or individual grants permit.

---

## Architecture

```
User → API → Auth (JWT + DB reload) → Token Generator → Query Builder → SecureStore → Qdrant
                                            ↑
                                   Permission Tokens
                     (role:*, emp:*, dept:*, rolemp:*, usr:*)
```

1. **Ingest**: PDF documents are loaded per page (PyMuPDF for text, pdfplumber for structured tables), markdown and HTML documents are loaded preserving comments and hidden elements, chunked within page boundaries (never crossing pages), tagged with ACL permission tokens, and indexed into Qdrant with named dense (`bge-m3`, 1024-dim) and sparse (BM25 with IDF modifier) vectors.
2. **Permission Tokens**: Every chunk carries an `acl_tokens` payload (e.g. `role:employee`, `emp:E1004`, `dept:Engineering`).
3. **Index**: The `SecureStore` gateway is the **sole gateway** in the codebase allowed to interact with Qdrant.
4. **Filter inside retrieval**: The server matches user permission tokens against chunk `acl_tokens` inside Qdrant. Chunks the user cannot see are never retrieved or loaded into memory.
5. **Verified citations**: Grounded responses reference original document names and page numbers for transparent verification.

### Why Access Control Lives in the Server, Not in Qdrant

Qdrant has no built-in role-based access control engine. All authorization logic comes from the filter built by server-side code through the single `SecureStore` gateway and applied inside the vector search. The client never supplies or modifies filter criteria.

---

## Northwind Dataset & Permission Model

VaultRAG is evaluated against the Northwind Industrial Pvt Ltd dataset (`data/northwind/rag_demo_dataset`):
- **Roles**: `employee`, `manager`, `hr_admin`, `finance_admin`, `admin`
- **System Admin**: In the Northwind model, system admin has no document ACLs (can only manage users/system).
- **Fail-Closed**: Any chunk without permission tokens is rejected. Any document not listed in `acl_policy.json` is rejected.

### Permission Token Syntax

| Token Format | Meaning | Example |
|---|---|---|
| `role:<role>` | Role-based document access | `role:employee`, `role:hr_admin` |
| `emp:<id>` | Individual employee access (e.g. ID card, hotel receipt) | `emp:E1004`, `emp:E1010` |
| `dept:<dept>` | Department-level document access | `dept:Engineering` |
| `rolemp:<r>@<id>` | Role-employee specific binding | `rolemp:manager@E1003` |
| `usr:<id>` | User account grant | `usr:u_asha` |

---

## Demo Accounts

All demo accounts share the password `changeme123`:

| User ID | Name | Email | Roles | Employee ID | Department |
|---|---|---|---|---|---|
| `u_asha` | Asha Patel | `asha.patel@northwind.example` | `employee` | `E1004` | Engineering |
| `u_neha` | Neha Desai | `neha.desai@northwind.example` | `employee` | `E1006` | Sales |
| `u_ravi` | Ravi Menon | `ravi.menon@northwind.example` | `manager` | `E1003` | Engineering |
| `u_dev` | Dev Joshi | `dev.joshi@northwind.example` | `manager` | `E1005` | Sales |
| `u_meera` | Meera Iyer | `meera.iyer@northwind.example` | `hr_admin` | `E1001` | HR |
| `u_karan` | Karan Shah | `karan.shah@northwind.example` | `finance_admin` | `E1002` | Finance |
| `u_admin` | System Admin | `admin@northwind.example` | `admin` | None | None |

---

## Prerequisites

- Windows 11 (or Linux / macOS)
- Python 3.11+
- Docker Desktop (for Postgres and Qdrant)
- Git

---

## Setup & Quickstart (cmd syntax)

Run all commands from Windows Command Prompt (`cmd`):

```cmd
:: 1. Clone and enter repo
cd D:\VaultRAG

:: 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate.bat

:: 3. Install pinned dependencies
pip install -r requirements.txt

:: 4. Configure environment
copy .env.example .env
:: Edit .env and set JWT_SECRET to a secure random string

:: 5. Start infrastructure (PostgreSQL & Qdrant)
docker compose up -d

:: 6. Initialize database schema & seed Northwind users
cd backend
python scripts\create_tables.py
python scripts\seed_users.py

:: 7. Start the FastAPI backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

## Step 3: Secure Hybrid Search & Scripts

### 1. The `/search` Endpoint
- **URL**: `POST /search`
- **Auth**: Bearer JWT token required
- **Body**: `{"query": "...", "top_k": 5, "rerank": false}`
- **Response**: `{"results": [...], "count": n}`. Each result item contains `chunk_id`, `source_id`, `file`, `page`, `text`, and `score`.
- **Fail-Closed Security**: When a user queries a forbidden document or a nonexistent document, the response is byte-for-byte identical:
  ```json
  {
    "results": [],
    "count": 0,
    "message": "No accessible results found."
  }
  ```
  The server never leaks whether a document exists or how many results were filtered out.
- **Audit Logging**: Every search is logged to `audit_log` with `user_id`, `timestamp`, `query` (truncated to 200 chars), returned `chunk_ids`, and `count`. Document text is **never** logged.
- **Rate Limiting**: Configured via `SEARCH_RATE_LIMIT_PER_MINUTE` (default: 60). Excessive queries return `429 Too Many Requests`.

### 2. Demo & Verification Scripts (cmd syntax)

Run from `D:\VaultRAG\backend` with `.venv` active:

```cmd
:: Compare search results across all 7 dataset users for any question
python scripts\compare_users.py "What is the notice period for confirmed employees?"
python scripts\compare_users.py "What is the Apex vendor contract value?"
python scripts\compare_users.py "What was decided in the August board meeting?"

:: Run security leak check and retrieval accuracy audit across all eval & attack queries
python scripts\leak_check.py

:: Check authentication across all 7 Northwind accounts
python scripts\check_login.py

:: Inspect ingested chunks in Qdrant
python scripts\inspect_chunks.py --limit 5

:: Verify ACL permission matrix against reference acl.py (140 checks, 100% match)
python scripts\acl_matrix.py

:: Run the complete test suite (55 passing tests)
pytest tests\ -v
```

---

## Permission Tokens & Access Control

VaultRAG enforces access control through discrete permission tokens:
- `role:<role>` — for each active role (e.g. `role:employee`, `role:manager`, `role:hr_admin`, `role:finance_admin`)
- `emp:<id>` — for the employee's ID (e.g. `emp:E1004`, `emp:E1010`)
- `dept:<dept>` — for the employee's department (e.g. `dept:Engineering`, `dept:Sales`)
- `rolemp:<r>@<id>` — role-employee specific binding (e.g. `rolemp:employee@E1004`)
- `usr:<id>` — user account ID (e.g. `usr:<uuid>`)

### Token Building Rules
1. Tokens are constructed fresh from the database `User` model on **every request** via `build_principal(user)`.
2. Tokens **never** come from request bodies, query strings, or JWT claims.
3. System Admin (`u_admin`) receives only `role:admin`, which appears in no document ACL, so admins see 0 documents.
4. If a principal has no tokens, `SecureStore.search` returns `[]` immediately without querying Qdrant.

---

## Leftover Cleanups (Part A)

- **A1. Clearance Field Removal**: Completely removed legacy `clearance` column from `User` model, schemas (`CreateUserRequest`, `UserOut`, `UpdateRolesRequest`), and admin endpoints. Migration ran `ALTER TABLE users DROP COLUMN IF EXISTS clearance;`.
- **A2. Self-Registration Gate**: Added `ALLOW_SELF_REGISTER` setting (default: `false`). When `false`, `POST /auth/register` returns `403 Forbidden` with `"Registration is disabled"`. When `true`, registered users get empty roles and `employee_id = None`, giving them zero document access.
- **A3. Live User Deactivation**: Inactive users cannot log in. An active JWT token for a user who was subsequently deactivated in the database is rejected with `401 Unauthorized` on their very next request.

---

## Settings & Environment Variables (.env)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant vector database URL |
| `QDRANT_COLLECTION` | `vaultrag_chunks` | Main vector collection name |
| `JWT_SECRET` | `CHANGE_ME...` | Secret key for HS256 JWT tokens |
| `ALLOW_SELF_REGISTER` | `false` | Enable/disable public user registration |
| `RERANK_ENABLED` | `false` | Enable cross-encoder reranking by default |
| `RERANK_CANDIDATES` | `20` | Max candidates retrieved for reranking |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Cross-encoder reranker model |
| `SEARCH_RATE_LIMIT_PER_MINUTE` | `60` | In-memory search rate limit per user |

---

## Test Suites

All 55 tests pass across the test suite:
- `tests/test_auth.py` (21 tests): Northwind login, `/auth/me` identity, role reload without new token, bcrypt bounds, self-registration toggle (403 when false).
- `tests/test_admin.py` (6 tests): Non-admin 403, user creation with roles, deactivation 401, audit log persistence.
- `tests/test_health.py` (2 tests): Postgres & Qdrant health check, API root.
- `tests/test_principals.py` (6 tests): User and document token generation, admin isolation, 100% matrix match across all 19 documents against reference `acl.py`.
- `tests/test_dataset_ingestion.py` (8 tests): Fake-embedder ingestion, ground-truth evaluation coverage, poison file preservation, ingestion idempotency, and `bge-m3` embedding dimension.
- `tests/test_search.py` (12 tests): Fail-closed empty tokens, filter presence on prefetches + outer query, dynamic DB role update without re-login, 401 on missing/tampered/deactivated token, ACL separation (Asha vs Ravi/Karan on Apex; Asha vs Karan/Meera on memo & board; Admin 0 results), identical empty response, poison exclusion by default, and rate limiting (429).
