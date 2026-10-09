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
- **System Admin**: Platform administrator (`u_admin`, role `admin`). When `ADMIN_SEES_ALL=true` (default), `role:admin` is included in all document ACLs so admin can read all documents and monitor system activity without any filter bypass.
- **Fail-Closed**: Any chunk without permission tokens is rejected. Any document not listed in `acl_policy.json` is rejected.

### Permission Token Syntax

| Token Format | Meaning | Example |
|---|---|---|
| `role:<role>` | Role-based document access | `role:employee`, `role:hr_admin`, `role:admin` |
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

## Admin Access & Monitoring (`ADMIN_SEES_ALL`)

VaultRAG empowers the platform administrator (`u_admin`, role `admin`) to read all ingested documents and monitor system activity (queries asked, answered vs refused, chunk counts, latency, and uploads) **without introducing any filter bypass or backdoor**:

1. **Zero-Bypass Architecture**:
   - Access control remains 100% inside Qdrant (`MatchAny` filter on `acl_tokens` in dense and sparse prefetches and the final query).
   - There is **no** `if user.role == "admin"` bypass anywhere in the retrieval engine or API.
   - Admin access works strictly because `role:admin` is present in the chunk's `acl_tokens` list.
   - Admin principal tokens remain strictly `["role:admin"]` (no wildcards).
   - Poison corpus (`poison_test`) remains excluded from search by default for all users, including admin.

2. **In-Place Switching Without Re-embedding (`scripts/set_admin_access.py`)**:
   - Easily toggle or check admin access on existing Qdrant vector points in place without re-embedding:
   ```cmd
   :: Check status (how many points contain role:admin)
   python scripts\set_admin_access.py --status

   :: Grant admin access to all existing points (adds role:admin)
   python scripts\set_admin_access.py --on

   :: Revoke admin access (removes role:admin)
   python scripts\set_admin_access.py --off
   ```

3. **Audited Reads**:
   - Every read by `u_admin` via `/ask`, `/search`, or `/citation/{chunk_id}` writes an audit log entry in PostgreSQL with `admin_access=true`.
   - The audit log records structured metadata: `event_type`, `user_id`, `created_at`, `refused`, `reason_code`, `latency_ms`, `chunk_count`, `question_hash`, and `question_length`.
   - Document text, plain query text, and passwords/tokens are **never** logged.

### Real API Interaction Examples

#### (a) `u_admin` asking the Apex monthly fee (`/ask`)
Request:
```http
POST /ask
Authorization: Bearer <u_admin_jwt>
Content-Type: application/json

{"question": "What is the monthly service fee under the Apex contract?"}
```
Response (`200 OK`):
```json
{
  "answer": "The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18% [1].",
  "refused": false,
  "verified": true,
  "citations": [
    {
      "id": 1,
      "chunk_id": "vendor_contract_apex-p1-c1",
      "source_id": "pdf:vendor_contract_apex.pdf",
      "file": "vendor_contract_apex.pdf",
      "page": 1,
      "snippet": "from 1 Apr 2026 - 31 Mar 2028, unless terminated earlier under Clause 7. 2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%.",
      "highlights": [
        {
          "start": 437,
          "end": 590
        }
      ],
      "highlight_text": "2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%."
    }
  ]
}
```

#### (b) `u_admin` fetching citation details (`/citation/vendor_contract_apex-p1-c1`)
Request:
```http
GET /citation/vendor_contract_apex-p1-c1
Authorization: Bearer <u_admin_jwt>
```
Response (`200 OK`):
```json
{
  "chunk_id": "vendor_contract_apex-p1-c1",
  "source_id": "pdf:vendor_contract_apex.pdf",
  "file": "vendor_contract_apex.pdf",
  "page": 1,
  "text": "Northwind Industrial Pvt Ltd | Master Logistics Services Agreement VC-2026-014 | Confidential | CONF-VC-3340 Page 1 of 4 Master Logistics Services Agreement This Agreement is made between Northwind Industrial Pvt Ltd (the Company) and Apex Logistics Pvt Ltd (the Vendor), contract reference VC-2026-014. 1. Term The Agreement is effective for a term of 24 months, from 1 Apr 2026 - 31 Mar 2028, unless terminated earlier under Clause 7. 2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%."
}
```

#### (c) `u_asha` asking the same Apex fee question (`/ask` - unauthorized)
Request:
```http
POST /ask
Authorization: Bearer <u_asha_jwt>
Content-Type: application/json

{"question": "What is the monthly service fee under the Apex contract?"}
```
Response (`200 OK` with safe constant refusal):
```json
{
  "answer": "I couldn't find an answer to that in the documents available to you.",
  "refused": true,
  "verified": false,
  "citations": []
}
```

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

All 89 tests pass across the test suite:
- `tests/test_auth.py` (21 tests): Northwind login, `/auth/me` identity, role reload without new token, bcrypt bounds, self-registration toggle (403 when false).
- `tests/test_admin.py` (6 tests): Non-admin 403, user creation with roles, deactivation 401, audit log persistence.
- `tests/test_health.py` (2 tests): Postgres & Qdrant health check, API root.
- `tests/test_principals.py` (6 tests): User and document token generation, admin isolation, 100% matrix match across all 19 documents against reference `acl.py`.
- `tests/test_dataset_ingestion.py` (8 tests): Fake-embedder ingestion, ground-truth evaluation coverage, poison file preservation, ingestion idempotency, and `bge-m3` embedding dimension.
- `tests/test_search.py` (12 tests): Fail-closed empty tokens, filter presence on prefetches + outer query, dynamic DB role update without re-login, 401 on missing/tampered/deactivated token, ACL separation, identical empty response, poison exclusion, and rate limiting (429).
- `tests/test_ask.py` (34 tests): Grounded answer pipeline, low-relevance refusal before LLM, citation mapping, deterministic fact checking, canary output guard, poison canary blocks, delimiter neutralization, JSON repair retry, timeout 503 handling, identical refusal responses, citation ACL enforcement (same 404), rate limiting (429), highlight offsets matching chunk text, supporting-only citations, answer bracket marker retention, and live Ollama integration test.

---

## Step 5: Grounded Answers & Prompt Injection Defense

### 1. Ollama Setup & Model Verification
The LLM runs locally via Ollama HTTP API (port 11434) and is **never** loaded in-process.

To start Ollama and check installed models:
```cmd
:: Start Ollama server
ollama serve

:: Verify installed models
curl http://localhost:11434/api/tags

:: If models are missing, pull them (Lenovo LOQ RTX 4050 6GB VRAM):
ollama pull qwen2.5:7b
ollama pull qwen2.5:3b
```

### 2. The `/ask` and `/citation` Endpoints

#### `POST /ask`
- **URL**: `POST /ask`
- **Auth**: Bearer JWT token required
- **Body**: `{"question": "What is the monthly service fee under the Apex contract?", "top_k": 5}`
- **Response (`u_karan` - Authorized)**:
  ```json
  {
    "answer": "The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18% [1].",
    "refused": false,
    "verified": true,
    "citations": [
      {
        "id": 1,
        "chunk_id": "vendor_contract_apex-p1-c1",
        "source_id": "pdf:vendor_contract_apex.pdf",
        "file": "vendor_contract_apex.pdf",
        "page": 1,
        "snippet": "from 1 Apr 2026 - 31 Mar 2028, unless terminated earlier under Clause 7. 2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%.",
        "highlights": [
          {
            "start": 437,
            "end": 590
          }
        ],
        "highlight_text": "2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%."
      }
    ]
  }
  ```
- **Response (`u_meera` - "What was decided in the August board meeting?")**:
  ```json
  {
    "answer": "The board approved a contract with Apex Logistics Pvt Ltd for logistics services, an increment pool for FY 2026-27, hiring of engineers, and capital expenditure for warehouse automation [1].",
    "refused": false,
    "verified": true,
    "citations": [
      {
        "id": 1,
        "chunk_id": "board_minutes_2026_08-p2-c1",
        "source_id": "pdf:board_minutes_2026_08.pdf",
        "file": "board_minutes_2026_08.pdf",
        "page": 2,
        "snippet": "8,00,000 for 24 months from 1 April 2026, be and is hereby approved. R2. Resolved that an increment pool of 8% of total fixed pay be approved for FY 2026-27, effective 1 October 2026, with no individual increment exceeding 12%. R3. Resolved that the hiring of 12 additional engineers in the Engineeri",
        "highlights": [
          {
            "start": 345,
            "end": 499
          }
        ],
        "highlight_text": "Resolved that an increment pool of 8% of total fixed pay be approved for FY 2026-27, effective 1 October 2026, with no individual increment exceeding 12%."
      }
    ]
  }
  ```
- **Response (`u_asha` - Forbidden / Safe Refusal)**:
  ```json
  {
    "answer": "I couldn't find an answer to that in the documents available to you.",
    "refused": true,
    "verified": false,
    "citations": []
  }
  ```

#### `GET /citation/{chunk_id}`
- **URL**: `GET /citation/{chunk_id}`
- **Auth**: Bearer JWT token required
- **ACL Enforcement**: Evaluates the user's permission tokens against the chunk's `acl_tokens` in Qdrant. If the chunk does not exist OR the user lacks permission, returns the **exact same 404 body**: `{"detail": "Chunk not found"}`.

### 3. Safe Refusal Design
When an answer cannot be generated (missing data, forbidden documents, low relevance, or failed verification), VaultRAG returns **one constant string**:
> `"I couldn't find an answer to that in the documents available to you."`

The API response **never** reveals internal reason codes, chunk counts, or whether the document exists. Reason codes (`no_relevant_context`, `llm_not_answerable`, `verification_failed`, `output_guard`) are written **only** to the internal security audit log.

### 4. Multi-Layer Prompt Injection Defense
1. **Context Delimiters & Neutralization**: Chunks are wrapped between `BEGIN_CONTEXT_CHUNK` and `END_CONTEXT_CHUNK`. Any appearance of these delimiters inside untrusted document text is stripped/replaced before prompting.
2. **Untrusted Data Rule**: System prompt instructs the model that retrieved chunks are data, not instructions, and any instructions within them must be ignored.
3. **Canary Leak Detection**: The canary marker `SYS-CANARY-0xA17` is planted in the system prompt. If it ever appears in an answer, the output is blocked and logged as a security alert.
4. **Poison Canary Defense**: Poison strings (`PWNED-4471`, `EXFIL-8832`, `ADMIN-GRANTED-2290`) are blocked by the post-generation output guard.
5. **URL & Link Sanitization**: Markdown links and external URLs not present in cited chunks are blocked.
6. **Claim-Level Fact Verification**: Every number, amount, date, and ID token in generated sentences must exist in cited chunks, and sentences must meet `SUPPORT_THRESHOLD`.

### 5. Running Step 5 Scripts (cmd syntax)
From `D:\VaultRAG\backend` with `.venv` active:

```cmd
:: 1. Run reranker threshold calibration (PDF questions, cached)
python scripts\calibrate_threshold.py --max-questions 40

:: 2. Run comprehensive answer and security evaluation (real LLM)
python scripts\eval_answers.py

:: 3. Run interactive walkthrough (u_asha vs u_karan)
python scripts\walkthrough.py

:: 4. Run test suite
pytest tests\ -v -m "not llm"
pytest tests\test_ask.py -v -m llm
```

### 6. Settings & Fallback Warning

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | Provider: `ollama` (default) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama HTTP endpoint |
| `LLM_MODEL` | `qwen2.5:7b` | Primary local LLM |
| `LLM_FALLBACK_MODEL` | `qwen2.5:3b` | Local fallback LLM |
| `LLM_TIMEOUT_S` | `90` | HTTP timeout for LLM generation |
| `LLM_MAX_TOKENS` | `400` | Max generation tokens |
| `LLM_FALLBACK_ENABLED` | `false` | Enable fallback to hosted cloud LLMs |
| `ASK_TOP_K` | `5` | Max context chunks provided to LLM |
| `ASK_CANDIDATES` | `10` | Candidates retrieved for reranking |
| `RELEVANCE_THRESHOLD` | `0.05` | Calibrated reranker relevance gate |
| `SUPPORT_THRESHOLD` | `0.05` | Calibrated claim semantic support threshold |
| `ASK_RATE_LIMIT_PER_MINUTE` | `20` | Sliding window rate limit for `/ask` |
| `ADMIN_SEES_ALL` | `true` | When true, role:admin is added to chunk ACLs so platform admin can read all documents. All admin reads are audited. |

> **IMPORTANT - DATA SOVEREIGNTY & PRIVACY NOTE:**
> `LLM_FALLBACK_ENABLED` is set to `false` by default. Enabling fallback to hosted providers (e.g. Groq, Gemini) sends confidential document text outside your local machine to external third-party cloud APIs. Keep this disabled for strict on-premise data confidentiality.
