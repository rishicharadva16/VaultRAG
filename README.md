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

## Ingestion & Verification Commands

In a terminal with `.venv` active, from `D:\VaultRAG\backend`:

```cmd
:: 1. Check authentication across all 7 Northwind accounts
python scripts\check_login.py

:: 2. Reset Qdrant collections (drops and recreates main collection with indexes)
python scripts\reset_collection.py

:: 3. Ingest the 7 dataset PDFs and 3 poison files
python scripts\ingest_corpus.py --include-poison

:: 4. Inspect ingested chunks in Qdrant
python scripts\inspect_chunks.py --limit 5
python scripts\inspect_chunks.py --doc-id hr_policy

:: 5. Verify ACL permission matrix against reference acl.py (140 checks, 100% match)
python scripts\acl_matrix.py

:: 6. Run the complete test suite (41 passing tests)
pytest tests\ -v
```

---

## Chunk Schema (Pydantic v2)

Every chunk point stored in Qdrant has a deterministic UUID5 point ID (`point_id(chunk_id)`) and the following validated payload:

| Field | Type | Description |
|---|---|---|
| `chunk_id` | `str` | Deterministic ID: `<doc_id>-p<page>-c<n>` (page 1-based, chunk 1-based) |
| `doc_id` | `str` | Normalized slug identifier (e.g. `hr_policy`) |
| `source_doc` | `str` | Original file name (e.g. `hr_policy.pdf`) |
| `source_id` | `str` | ACL policy key (e.g. `pdf:hr_policy.pdf`, `poison:poison_02...`) |
| `source_type` | `Literal["pdf", "md", "html", "image", "db_row"]` | Origin media type |
| `source_name` | `str` | Stem identifier |
| `corpus` | `Literal["main", "poison_test"]` | Target corpus partition |
| `page` | `int \| None` | 1-based page number for PDFs (>= 1) |
| `bbox` | `list[float] \| None` | Bounding box coordinates (reserved for OCR) |
| `table` | `str \| None` | Serialized table descriptor |
| `row_pk` | `str \| None` | Database row identifier (reserved for row ingestion) |
| `chunk_type` | `Literal["text", "table"]` | Text chunk or serialized table row |
| `text` | `str` | Non-empty stripped text content |
| `owner_id` | `str` | Owner identifier (`u_admin`) |
| `allowed_roles` | `list[str]` | Allowed roles from `ROLES` |
| `allowed_employees` | `list[str]` | Explicit employee IDs granted access |
| `allowed_departments` | `list[str]` | Explicit departments granted access |
| `acl_tokens` | `list[str]` | Non-empty list of generated permission tokens |
| `classification_label` | `str` | E.g. `internal`, `confidential` |
| `deleted` | `bool` | Soft-deletion flag |
| `created_at` | `str` | ISO 8601 UTC timestamp |

### Payload Indexes in Qdrant
The `SecureStore` gateway automatically ensures payload indexes for fast filtered retrieval:
- **Keyword**: `acl_tokens`, `doc_id`, `source_doc`, `source_type`, `corpus`, `owner_id`
- **Bool**: `deleted`

---

## Security Principles Enforced

1. **Identity only in JWT**: Token payload carries identity (`sub`), timestamps (`iat`, `exp`), and unique ID (`jti`). Roles and clearance are **never** in the token.
2. **Live DB authorization**: Roles and active status are reloaded from PostgreSQL on every request. Admin role revocations or deactivations take effect immediately.
3. **Server-side query filtering**: Clients cannot pass or alter filter parameters.
4. **Fail closed**: Chunks with missing or empty permission tokens are rejected before embedding. Unlisted documents cannot be ingested.
5. **Single Gateway**: `app/index/store.py` (`SecureStore`) is the only module allowed to import `qdrant_client`.

---

## Test Suites

All 41 tests pass across the test suite:
- `tests/test_auth.py` (21 tests): Northwind login, `/auth/me` and `/me` identity, role reloading, token validation, password bcrypt limits, CORS.
- `tests/test_admin.py` (6 tests): Non-admin 403, admin user creation with valid roles, self-registration with empty roles, deactivation 401, audit logging.
- `tests/test_health.py` (1 test): Postgres & Qdrant health check.
- `tests/test_principals.py` (6 tests): User and document token generation, admin and empty user isolation, exact 100% matrix match across all 19 documents against reference `acl.py`.
- `tests/test_dataset_ingestion.py` (7 tests): Fast fake-embedder ingestion of 7 PDFs, ground-truth evaluation coverage (>= 90% on `eval_questions.json`), poison file comment and `display:none` preservation, ingestion idempotency, payload indexes, and `bge-m3` embedding dimension check.
