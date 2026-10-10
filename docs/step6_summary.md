# Step 6 Summary: Live Upload, Sharing and Admin Monitoring

## 1. Architecture & Design Overview

VaultRAG Step 6 delivers live document ingestion, dynamic multi-tenant sharing with immediate revocation, and comprehensive zero-leak administrative monitoring while strictly upholding all VaultRAG security invariants:
- **Zero Dataset Alteration**: The Northwind reference dataset folder remains strictly read-only.
- **Single Vector Client Gateway**: `SecureStore` remains the sole module importing `qdrant_client`.
- **Pure Vector ACL Filtering**: Access control is enforced exclusively inside Qdrant by matching the principal's dynamic tokens against chunk `acl_tokens`. No endpoint or role bypasses exist.
- **Fail-Closed Identical 404**: Forbidden documents and nonexistent documents return the exact same response: `404 Not Found` with `{"detail": "Document not found"}` (and `{"detail": "Chunk not found"}` for citations/images).
- **Sequential Background Ingestion**: Uploaded documents are queued in an asynchronous FIFO worker queue (`asyncio.Queue`) so that OCR, PDF chunking, dense embedding, and sparse vector generation execute one job at a time, preventing GPU and CPU thrashing with LLM query generation.
- **In-Place ACL Updates**: Updating shares or revoking access recomputes canonical ACL tokens from the database and updates points in Qdrant in-place via `set_acl_by_source_id` using Qdrant's `models.SetPayloadOperation` without re-embedding.
- **Crash Recovery**: Interrupted documents left in `status="processing"` upon system restart are automatically marked `status="failed"` with `reason_code="interrupted"`.

---

## 2. PostgreSQL Data Model & Migration

All migrations are fully idempotent within `create_tables.py` and `conftest.py`.

### `documents` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | PRIMARY KEY | Document UUID |
| `source_id` | VARCHAR | UNIQUE, INDEXED | Deterministic source identifier: `upl:<uuid>` |
| `filename` | VARCHAR | NOT NULL | Sanitized display name (traversal-safe) |
| `kind` | VARCHAR | NOT NULL | `pdf` \| `image` \| `csv` \| `text` |
| `size_bytes` | INTEGER | NOT NULL | File size in bytes |
| `sha256` | VARCHAR(64) | INDEXED | Hash for owner-scoped deduplication |
| `owner_id` | VARCHAR | INDEXED, FK(users.id) | Uploader user UUID |
| `status` | VARCHAR | NOT NULL | `queued` \| `processing` \| `ready` \| `failed` |
| `reason_code` | VARCHAR | NULLABLE | Reason code for failures (e.g. `interrupted`) |
| `chunk_count` | INTEGER | DEFAULT 0 | Count of indexed chunks |
| `sensitive_columns` | JSON | NULLABLE | List of sensitive column names for CSVs |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Timestamp of upload |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Timestamp of last modification |
| `deleted_at` | TIMESTAMPTZ | NULLABLE | Soft deletion timestamp |

### `document_shares` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR(36) | PRIMARY KEY | Share grant UUID |
| `document_id` | VARCHAR(36) | FK(documents.id) | Associated document |
| `grantee_type` | VARCHAR | CHECK(`user` \| `role` \| `department`) | Share type |
| `grantee_value` | VARCHAR | NOT NULL | User UUID, role name, or department |
| `include_sensitive`| BOOLEAN | DEFAULT FALSE | Grants access to sensitive CSV chunks |
| `granted_by` | VARCHAR | FK(users.id) | Granting user UUID |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Timestamp of share creation |

*Unique constraint*: `uq_document_shares_grantee (document_id, grantee_type, grantee_value)`.

---

## 3. Canonical Token Model & In-Place Qdrant Updates

Canonical ACL is always derived dynamically from the PostgreSQL state:
1. **Base Chunks**:
   $$\text{Tokens} = \{\text{usr:}\langle\text{owner\_id}\rangle\} \cup \{\text{usr:}\langle\text{id}\rangle \mid \text{user share}\} \cup \{\text{role:}\langle\text{role}\rangle \mid \text{role share}\} \cup \{\text{dept:}\langle\text{dept}\rangle \mid \text{dept share}\} \cup \{\text{role:admin}\}$$
   appended via `finalize_acl_tokens`.
2. **Sensitive CSV Chunks**:
   $$\text{Tokens}_{\text{sens}} = \{\text{usr:}\langle\text{owner\_id}\rangle, \text{role:admin}\} \cup \{\text{grantee tokens with } \text{include\_sensitive}=\text{True}\}$$
   Standard shares never widen sensitive column chunks unless `include_sensitive=True` was explicitly specified.
3. **In-Place Updates**:
   `SecureStore.set_acl_by_source_id(source_id, tokens, sensitive_tokens)` issues a `SetPayloadOperation` targeting Qdrant points matching `source_id`. Points with `is_sensitive=True` receive `sensitive_tokens`, while all base points receive `tokens`. Points are never re-embedded on sharing or revocation.

---

## 4. API Endpoints Table

| Method | Path | Auth / Role | Status | Description |
|---|---|---|---|---|
| `POST` | `/documents` | Auth (`UPLOAD_ROLES`) | 202 / 200 | Multipart upload. Magic-byte verification (415), size limit (413), rate limit (429), owner+sha256 dedupe (200), enqueued (202). |
| `GET` | `/documents?scope=` | Auth | 200 | List documents (`scope=mine\|shared\|all`). `scope=all` is admin-only (403 for others). Includes `shared_with_count` and `can_manage`. |
| `GET` | `/documents/{id}` | Owner / Grantee / Admin | 200 / 404 | Document detail with `chunk_count`. Returns identical 404 for nonexistent and forbidden documents. |
| `DELETE` | `/documents/{id}` | Owner / Admin | 204 / 404 | Deletes Qdrant points via `delete_by_source_id`, removes original file and render cache, marks `deleted_at`. |
| `GET` | `/documents/{id}/shares` | Owner / Admin | 200 / 404 | Lists active shares. Non-owners (including grantees) receive identical 404. |
| `POST` | `/documents/{id}/shares` | Owner / Admin | 201 / 404 | Adds user/role/department share. Recomputes and updates Qdrant ACL payload before returning. |
| `DELETE` | `/documents/{id}/shares/{share_id}` | Owner / Admin | 204 / 404 | Revokes share and immediately updates Qdrant ACL payload in-place before returning. |
| `GET` | `/sharing/targets?q=` | Auth | 200 | Rate-limited autocomplete for users, roles, and departments. Zero leak of user emails or private roles. |
| `GET` | `/admin/audit/summary?days=7`| Admin only | 200 / 403 | Aggregated telemetry: totals, refusal rate, avg/p95 latency, daily series, reason codes, top users. |
| `GET` | `/admin/queries?limit=&before=` | Admin only | 200 / 403 | Query logs with timestamp, user name, event type, latency, chunk count, reason code, question hash. NEVER logs question text. |
| `GET` | `/admin/uploads` | Admin only | 200 / 403 | Administrative list of all documents with owner name, status, size, share count, and deleted status. |
| `POST` | `/ask` & `/search` | Auth | 200 | Accepts optional `source_ids: list[str]` (max 10). ANDed with the principal ACL filter; invalid/forbidden IDs match nothing. |

---

## 5. Security Decisions & Zero-Leak Guarantees

1. **What is Audited**:
   - `event_type`: `upload`, `upload_ingest`, `share`, `unshare`, `delete`, `ask`, `search`.
   - `user_id`, `details` containing UUIDs, reason codes (`READY`, `INTERRUPTED`, `PROCESSING_ERROR`), latency in milliseconds, chunk counts, query length, and SHA-256 question hash.
   - `admin_access=True` whenever a platform admin accesses document detail, shares, or administrative monitoring endpoints.
2. **What is NEVER Logged or Stored**:
   - Raw question text is never written to the audit log or returned in admin queries (only `question_hash` and `question_length`).
   - Document chunk text is never written to audit tables.
   - User passwords, authorization tokens, or internal `acl_tokens` are never exposed in any API response or audit record.
   - Internal filesystem paths (e.g. `storage/uploads/...`) are stripped; asset paths use relative whitelisted refs.
3. **Magic-Byte Sniffing**:
   - Formats are validated strictly by magic bytes (`%PDF` for PDF, `\x89PNG\r\n\x1a\n` for PNG, `\xff\xd8\xff` for JPEG, text sniffer for CSV/TXT/MD). Client-supplied `Content-Type` headers and file extensions are ignored.
4. **Prompt Injection Ingestion**:
   - Chunks matching canary strings or injection patterns are flagged with payload `flagged=True`.
   - Flagged chunks remain searchable and context-eligible, but the output guard serves as defense-in-depth, blocking canary leakage and emitting refusal reason `output_guard`.

---

## 6. Real API Outputs (JSON Samples)

### 1. Document Upload Response (`POST /documents` -> 202 Accepted)
```json
{
  "id": "425e21aa-8da0-49b8-8784-a85be61b4f6e",
  "status": "queued"
}
```

### 2. Document List Response (`GET /documents?scope=mine` -> 200 OK)
```json
[
  {
    "id": "425e21aa-8da0-49b8-8784-a85be61b4f6e",
    "filename": "roadmap_2027.pdf",
    "kind": "pdf",
    "status": "ready",
    "reason_code": null,
    "size_bytes": 894,
    "created_at": "2026-10-09T16:36:12.144163Z",
    "owner": {
      "id": "99b297ae-a42c-4019-b34b-70f24dd59159",
      "name": "Asha Patel"
    },
    "shared_with_count": 0,
    "can_manage": true
  }
]
```

### 3. Share Response (`POST /documents/{id}/shares` -> 201 Created)
```json
{
  "id": "aaa648e5-9b29-43cb-b208-86eaeed1c7e2",
  "grantee_type": "user",
  "grantee_value": "50ecd387-e000-49a1-b3bd-940502dd3f0a",
  "include_sensitive": false,
  "created_at": "2026-10-09T16:36:12.687217Z",
  "granted_by": "99b297ae-a42c-4019-b34b-70f24dd59159"
}
```

### 4. Revocation Response (`DELETE /documents/{id}/shares/{share_id}` -> 204 No Content)
```text
HTTP/1.1 204 No Content
(Empty body; access revoked in Qdrant before response return)
```

### 5. Forbidden 404 Response (`GET /documents/{id}` as Non-Grantee -> 404 Not Found)
```json
{
  "detail": "Document not found"
}
```

### 6. Admin Audit Summary (`GET /admin/audit/summary?days=7` -> 200 OK)
```json
{
  "days": 7,
  "totals": {
    "asks": 73,
    "searches": 7,
    "refusals": 42,
    "refusal_rate": 0.525,
    "avg_latency_ms": 3426.49,
    "p95_latency_ms": 13404.6,
    "uploads": 102,
    "active_users": 9
  },
  "per_day_series": [
    {
      "date": "2026-10-08",
      "asks": 27,
      "searches": 2,
      "refusals": 6,
      "uploads": 57
    },
    {
      "date": "2026-10-09",
      "asks": 46,
      "searches": 5,
      "refusals": 36,
      "uploads": 45
    }
  ],
  "counts_by_reason_code": {
    "no_relevant_context": 17,
    "not_found_or_forbidden": 17,
    "IMAGE_INGESTED": 21,
    "verification_failed": 2,
    "llm_not_answerable": 4,
    "authorized": 3,
    "PAGE_IMAGE_SERVED": 12,
    "SOURCE_PAGES_LISTED": 7,
    "QUEUED": 5,
    "READY": 5,
    "SHARE_GRANTED": 3,
    "SHARE_REVOKED": 2,
    "DELETED": 4,
    "output_guard": 2
  },
  "top_users": [
    {
      "name": "Karan Shah",
      "count": 31
    },
    {
      "name": "Asha Patel",
      "count": 24
    },
    {
      "name": "Meera Iyer",
      "count": 14
    },
    {
      "name": "Neha Desai",
      "count": 5
    },
    {
      "name": "Ravi Menon",
      "count": 4
    },
    {
      "name": "System Admin",
      "count": 2
    }
  ]
}
```

### 7. Admin Query Logs (`GET /admin/queries?limit=3` -> 200 OK, Zero Text Leaks)
```json
[
  {
    "time": "2026-10-09T16:35:12.339888Z",
    "user_name": "Asha Patel",
    "event_type": "ask",
    "refused": true,
    "reason_code": "no_relevant_context",
    "latency_ms": 3646.51,
    "chunk_count": 0,
    "admin_access": false,
    "question_hash": "1823f0fa96b6a66b",
    "question_length": 59
  },
  {
    "time": "2026-10-09T16:35:08.404662Z",
    "user_name": "Asha Patel",
    "event_type": "search",
    "refused": false,
    "reason_code": null,
    "latency_ms": 272.45,
    "chunk_count": 5,
    "admin_access": false,
    "question_hash": "bc6d91f33f069d2a",
    "question_length": 16
  },
  {
    "time": "2026-10-09T16:35:08.122788Z",
    "user_name": "Neha Desai",
    "event_type": "search",
    "refused": false,
    "reason_code": null,
    "latency_ms": 279.39,
    "chunk_count": 5,
    "admin_access": false,
    "question_hash": "bc6d91f33f069d2a",
    "question_length": 16
  }
]
```

---

## 7. Verification & Test Results

| Test Suite / Script | Command | Result | Details |
|---|---|---|---|
| Step 6 Upload & Sharing Suite | `pytest backend/tests/test_upload_sharing.py -v` | **10 / 10 PASSED** (100%) | PDF, share cycle, delete, CSV sensitive cols, image OCR, injection, rejections, restart recovery, zero leak, source_ids filter. |
| Regression Test Suite | `pytest backend/tests -m "not llm and not ocr" -v` | **132 / 132 PASSED** (100%) | Auth, dataset ingestion, DB ingest, health, principals, search, source view, uploads. |
| OCR Test Suite | `pytest backend/tests -m ocr -v` | **3 / 3 PASSED** (100%) | Real OCR on clear and rotated scan images, coordinate mapping. |
| LLM Test Suite | `pytest backend/tests -m llm -v` | **1 / 1 PASSED** (100%) | Grounded answer generation and access control under local Ollama. |
| Security Leak Audit | `python backend/scripts/leak_check.py` | **0 ACL VIOLATIONS** | 672 searches, 3,360 chunks inspected. Overall Hit@5 = 97.7%. Image violations = 0. |
| Reference ACL Matrix | `python backend/scripts/acl_matrix.py` | **100% MATCH** | 140 document checks, 1,260 database checks replicated. |
| Live End-to-End Demo | `python backend/scripts/live_upload_demo.py` | **ALL 7 STEPS PASS** | Ran against live Uvicorn API (`http://127.0.0.1:8000`) with real ingestion and real `/ask`. |

---

## 8. Known Limitations

1. **Sequential Worker Concurrency**: Uploaded files are processed one at a time via a single background worker to prevent Ollama GPU thrashing. During bulk uploads, jobs wait in the FIFO queue (`status: queued`).
2. **Text File Highlighting**: Plain text and markdown files do not produce PDF visual bounding boxes or raster pages; `/source/{chunk_id}/view` delivers rendered text with start/end character highlights.
3. **CSV Column Header Detection**: CSV sensitive column handling matches exact case-sensitive column header names provided in `sensitive_columns`.

---

## 9. Files Modified & Created

- `backend/app/config.py`: Added `UPLOAD_ROLES`, `MAX_UPLOAD_MB`, `UPLOADS_PER_HOUR`, `STORAGE_DIR`, and helper methods.
- `backend/app/db/models.py`: Added `Document` and `DocumentShare` models with foreign keys, indexes, and constraints.
- `backend/scripts/create_tables.py` & `backend/tests/conftest.py`: Idempotent SQL migrations for `documents` and `document_shares`.
- `backend/app/index/schema.py`: Extended `source_type` with `"csv"` and `"text"`; added `flagged` and `is_sensitive` to `Chunk`.
- `backend/app/index/store.py`: Added `set_acl_by_source_id`, `delete_by_source_id`, `count_by_source_id`, `flagged`/`is_sensitive` fields, and `source_ids` filter support.
- `backend/app/rag/answer.py`: Passed `source_ids` parameter down to `store.search`.
- `backend/app/api/ask.py` & `backend/app/api/search.py`: Added `source_ids` schema validation.
- `backend/app/storage/assets.py`: Whitelisted `settings.storage_path()` and `storage/uploads` directory.
- `backend/app/ingestion/live_upload.py`: Created complete ingestion pipeline (magic bytes detector, filename sanitizer, prompt injection detector, sequential queue worker, RapidOCR box converter, CSV splitter, chunker).
- `backend/app/api/documents.py`: Created live upload, list, detail, deletion, sharing, target autocomplete, and Qdrant in-place update handlers.
- `backend/app/api/admin.py`: Added `/admin/audit/summary`, `/admin/queries`, and `/admin/uploads` endpoints.
- `backend/app/api/source.py`: Added support for `kind="text"` rendering and relative file resolution for uploaded PDFs.
- `backend/app/main.py`: Registered `documents.router`, updated CORS to allow `DELETE, PUT, PATCH, OPTIONS`, and added startup recovery for interrupted documents.
- `backend/tests/test_upload_sharing.py`: Comprehensive test suite verifying all 10 specifications.
- `backend/scripts/live_upload_demo.py`: Automated live demonstration script against the running server.
- `backend/scripts/leak_check.py`: Updated to handle `upl:` source identifiers cleanly.
