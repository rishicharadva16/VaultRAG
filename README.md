# VaultRAG

**Secure multi-modal RAG with row/document-level access control** — every retrieval respects who you are, what you're cleared to see, and which documents you own.

---

## The Problem

Standard RAG systems treat the vector store as a flat, open index. If sensitive HR, finance, and legal documents are indexed together, any user can retrieve any chunk. VaultRAG solves this by enforcing access control **inside** every retrieval query, ensuring users only ever receive chunks their roles, user ID, and classification level permit.

---

## Architecture

```
User → API → Auth (JWT + DB reload) → Query Builder → SecureStore → Qdrant
                                            ↑
                                    ACL filter injected
                               (roles, clearance, ownership)
```

1. **Ingest**: PDF documents are loaded per page (PyMuPDF for text, pdfplumber for structured tables), chunked within page boundaries (never crossing pages), tagged with ACL metadata, and indexed into Qdrant with named dense (`bge-m3`, 1024-dim) and sparse (BM25 with IDF modifier) vectors.
2. **Tag**: Every chunk carries a complete ACL payload (`allowed_roles`, `allowed_users`, `classification`, `owner_id`, `is_public`).
3. **Index**: The `SecureStore` gateway is the **sole gateway** in the codebase allowed to interact with Qdrant.
4. **Filter inside retrieval**: The server constructs a Qdrant filter from the authenticated user's DB record. The filter executes **inside** the vector search — not post-query. Chunks the user cannot see are never retrieved or loaded into memory.
5. **Verified citations**: Grounded responses reference original document names and page numbers for transparent verification.

### Why Access Control Lives in the Server, Not in Qdrant

Qdrant has no built-in role-based access control engine. All authorization logic comes from the filter built by server-side code through the single `SecureStore` gateway and applied inside the vector search. The client never supplies or modifies filter criteria.

---

## Prerequisites

- Windows 11 (or Linux / macOS)
- Python 3.11+
- Docker Desktop (for Postgres and Qdrant)
- Git
- Ollama (installed natively on host, not in Docker)

---

## Setup & Quickstart (cmd syntax)

Run all commands from Windows Command Prompt (`cmd`):

```cmd
:: 1. Clone and enter repo
git clone <your-repo-url> VaultRAG
cd VaultRAG

:: 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate.bat

:: 3. Install pinned dependencies
pip install -r requirements.txt

:: 4. Configure environment
copy .env.example .env
:: Edit .env and set JWT_SECRET to a secure random string:
:: python -c "import secrets; print(secrets.token_urlsafe(64))"

:: 5. Start infrastructure (PostgreSQL & Qdrant)
docker compose up -d

:: 6. Initialize database schema & seed demo users
cd backend
python scripts\create_tables.py
python scripts\seed_users.py

:: 7. Start the FastAPI backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> **Note on Host Binding**: Always use `--host 127.0.0.1` for local development. Using `--host 0.0.0.0` is strictly for **LAN demos only** and exposes the unencrypted API to all devices on your local network.

---

## Step 2: Chunk Schema, Qdrant Collection & PDF Ingestion

### Step 2 Pipeline Execution

In a new terminal (with `.venv` activated, from `D:\VaultRAG\backend`):

```cmd
:: 1. Verify authentication & RBAC smoke tests
python scripts\check_login.py

:: 2. Create / verify Qdrant collection with named vectors & payload indexes
python scripts\create_collection.py

:: 3. Generate the 6 demo PDF documents with ground-truth facts
python scripts\make_demo_pdfs.py

:: 4. Ingest demo PDFs with ACL tagging & audit logging
python scripts\ingest_pdfs.py

:: 5. Inspect stored chunks in Qdrant
python scripts\inspect_chunks.py
python scripts\inspect_chunks.py --doc-id board_minutes

:: 6. Run the full test suite
pytest tests\ -v
```

---

## Chunk Schema (Pydantic v2)

Every chunk point stored in Qdrant has a deterministic UUID5 point ID (`point_id(chunk_id)`) and the following validated payload:

| Field | Type | Description |
|---|---|---|
| `chunk_id` | `str` | Deterministic ID: `<doc_id>-p<page>-c<n>` (page 1-based, chunk 1-based) |
| `doc_id` | `str` | Normalized slug identifier (e.g. `board_minutes`) |
| `source_type` | `Literal["pdf", "image", "db_row"]` | Origin media type |
| `source_name` | `str` | Original file name (e.g. `board_minutes.pdf`) |
| `page` | `int \| None` | 1-based page number (never spans multiple pages) |
| `bbox` | `list[float] \| None` | Bounding box coordinates (reserved for Step 4 OCR) |
| `row_id` | `str \| None` | Database row identifier (reserved for Step 4) |
| `chunk_type` | `Literal["text", "table"]` | Text chunk or serialized table row |
| `text` | `str` | Non-empty stripped text content |
| `owner_id` | `str` | Uploader user UUID (required) |
| `allowed_roles` | `list[str]` | Allowed roles (`admin` always included automatically) |
| `allowed_users` | `list[str]` | Specific user UUIDs granted access |
| `classification` | `int` | Clearance level required (1 = Public, 2 = Internal/Confidential, 3 = Secret/Board) |
| `is_public` | `bool` | If `True`, visible to all authenticated users |
| `deleted` | `bool` | Soft-deletion flag |
| `created_at` | `str` | ISO 8601 UTC timestamp |

### Payload Indexes in Qdrant
The `SecureStore` gateway automatically ensures payload indexes for fast filtered retrieval:
- **Keyword**: `allowed_roles`, `allowed_users`, `owner_id`, `doc_id`, `source_type`
- **Integer**: `classification`
- **Bool**: `is_public`, `deleted`

---

## ACL Manifest & Demo Documents

Permissions are data-driven via `data\acl_manifest.json`. During ingestion, owner and user emails are resolved to user UUIDs from PostgreSQL:

| Document | Owner | Allowed Roles | Clr | Visibility | Ground-Truth Content & Facts |
|---|---|---|---|---|---|
| `hr_policy.pdf` | Rahul (`hr`) | admin, hr, finance, intern | 1 | Public | Page 2: *"Every employee receives 20 days of paid leave per year."* |
| `leave_policy_summary.pdf` | Rahul (`hr`) | admin, hr, finance, intern | 1 | Public | Page 1: *"Every employee receives 20 days of paid leave per year."* |
| `leave_policy_full.pdf` | Rahul (`hr`) | hr, admin | 2 | Confidential | Page 2: *"Executive leave encashment is capped at 45 days."*<br>Page 3: *"Unused leave carry-forward is limited to 8 days."* |
| `board_minutes.pdf` | Priya (`admin`) | admin | 3 | Board Only | Page 4: *"The board approved a marketing budget of Rs. 12 lakh for Q3."*<br>Page 5: *"Approval was recorded by the finance head."* |
| `vendor_contract.pdf` | Meera (`finance`) | finance, admin | 2 | Confidential | Page 2: Structured fee schedule table + text *"The contract value is Rs. 6,20,000."* |
| `finance_memo.pdf` | Meera (`finance`) | finance, admin | 2 | Confidential | Page 1: *"Invoice 1042 total is Rs. 48,500."* |

### Known Trade-offs
1. **Dual Representation of Tables**: Table text extracted by PyMuPDF appears in page text chunks, while `pdfplumber` extracts structured `table` chunks with `Header: Value` formatting. Both are preserved to maximize dense semantic recall and sparse exact keyword retrieval.
2. **Scanned PDFs**: Pages with no extractable text or tables trigger a warning and are recorded in the ingestion summary. OCR processing for scanned documents is deferred to Step 4.

---

## Demo Users & Roles

| Name | Email | Role(s) | Clearance | Demo Password |
|---|---|---|---|---|
| **Priya** | `priya@vaultrag.local` | `admin` | 3 | `changeme123` |
| **Rahul** | `rahul@vaultrag.local` | `hr` | 2 | `changeme123` |
| **Meera** | `meera@vaultrag.local` | `finance` | 2 | `changeme123` |
| **Arjun** | `arjun@vaultrag.local` | `intern` | 1 | `changeme123` |

---

## Security Principles Enforced

1. **Identity only in JWT**: Token payload carries identity (`sub`), timestamps (`iat`, `exp`), and unique ID (`jti`). Roles and clearance are **never** in the token.
2. **Live DB authorization**: Roles and active status are reloaded from PostgreSQL on every request. Admin role revocations or deactivations take effect immediately.
3. **Server-side query filtering**: Clients cannot pass or alter filter parameters.
4. **Fail closed**: Chunks with missing or invalid ACL metadata are rejected before embedding. Unlisted manifest files default to admin-only classification 3.
5. **Single Gateway**: `app/index/store.py` (`SecureStore`) is the only module allowed to import `qdrant_client`.

---

## API & Authentication

### Interactive Swagger Docs (`/docs`)
1. Navigate to `http://127.0.0.1:8000/docs`.
2. Call `POST /auth/login` with your demo credentials.
3. Copy the returned `access_token`.
4. Click the **Authorize** button at the top right of the Swagger UI, paste the token, and click **Authorize**.
5. Test protected endpoints such as `GET /me` or `GET /admin/users`.

### Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Postgres & Qdrant health check |
| `POST` | `/auth/login` | None | Authenticate with email & password |
| `POST` | `/auth/register` | None | Self sign-up (assigned no roles, clearance 1) |
| `GET` | `/auth/me` | Bearer | Current user identity, roles, and clearance |
| `GET` | `/me` | Bearer | Top-level alias of `/auth/me` |
| `POST` | `/admin/users` | Admin | Create user with explicit roles & clearance |
| `GET` | `/admin/users` | Admin | List all registered users |
| `PUT` | `/admin/users/{id}/roles` | Admin | Update user roles and clearance |
| `PUT` | `/admin/users/{id}/active` | Admin | Activate / deactivate user account |

### CORS & Frontend Hosting
The API supports configurable origins via `CORS_ORIGINS` in `.env`. Wildcards (`*`) and `null` origins are strictly forbidden.

When developing a frontend, serve it via HTTP:
```cmd
cd frontend
python -m http.server 8080
```
> Opening HTML files directly via double-click (`file://`) sends an origin of `null`, which is blocked by CORS security policy.

---

## Roadmap

- [x] **Step 1**: Foundation — FastAPI, PostgreSQL, Qdrant health check, JWT auth, RBAC, audit logging
- [x] **Step 2**: Chunk schema, Qdrant collection, manifest permissions, ReportLab demo PDFs, PDF ingestion pipeline
- [ ] **Step 3**: ACL filter builder and secure hybrid search (dense + sparse with RRF fusion)
- [ ] **Step 4**: Database row ingestion and OCR pipeline for scanned documents
- [ ] **Step 5**: Grounded answers generation with citation verifier
- [ ] **Step 6**: Web frontend UI connection
- [ ] **Step 7**: Document upload, sharing, and dynamic permission management
- [ ] **Step 8**: Evaluation suite and leak test demonstration
