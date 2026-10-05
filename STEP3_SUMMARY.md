# VaultRAG Step 3: Secure Hybrid Search & ACL Enforcement Summary

## 1. Executive Summary

Step 3 implements **secure hybrid search with row- and document-level access control** for VaultRAG. Every search query evaluates user permission tokens against chunk ACL tokens directly inside Qdrant vector retrieval using Reciprocal Rank Fusion (RRF). Unauthorized chunks are never retrieved or loaded into server memory.

All 55 tests pass, 0 ACL leaks were detected across 672 evaluation and attack queries, and re-ingestion was proved to be completely idempotent.

---

## 2. Deliverables & Acceptance Checklist

| Section | Feature / Task | Status | Details |
|---|---|:---:|---|
| **Cleanup** | A1. Remove `clearance` | ✅ Complete | Dropped from DB, `User` model, schemas, and admin routes. |
| **Cleanup** | A2. `ALLOW_SELF_REGISTER` gate | ✅ Complete | Default `False`. 403 on register. When True, assigns 0 roles / 0 tokens. |
| **Cleanup** | A3. Inactive user handling | ✅ Complete | 401 on login and immediate revocation on next request via DB reload. |
| **Part B** | `build_principal(user)` | ✅ Complete | Fresh from DB on every request (`role:*`, `emp:*`, `dept:*`, `rolemp:*`, `usr:*`). |
| **Part B** | Admin token isolation | ✅ Complete | `u_admin` receives only `role:admin`, ensuring 0 document access. |
| **Part C** | `SecureStore.search` | ✅ Complete | Required `principal`, no raw filters, hybrid dense + sparse with RRF fusion. |
| **Part C** | Fail-closed & query bounds | ✅ Complete | Empty tokens -> `[]` without Qdrant call; `top_k` clamped to 1..20; max 500 chars. |
| **Part C** | Poison corpus exclusion | ✅ Complete | `corpus != "poison_test"` enforced by default in Qdrant filter. |
| **Part D** | Cross-encoder reranker | ✅ Complete | `BAAI/bge-reranker-v2-m3` behind `RERANK_ENABLED` and `RERANK_CANDIDATES`. |
| **Part D** | Reranker safety & fallback | ✅ Complete | Runs only on filtered hits; graceful fallback to fused order if missing. |
| **Part E** | `POST /search` endpoint | ✅ Complete | Authenticated, rate-limited, audit logged, returns plain search results. |
| **Part E** | Identical empty responses | ✅ Complete | Byte-for-byte identical output for forbidden and nonexistent topics. |
| **Part F** | `scripts/compare_users.py` | ✅ Complete | Compares search results across all 7 accounts in an ASCII table. |
| **Part F** | `scripts/leak_check.py` | ✅ Complete | 672 query audits, 0 violations, evaluates Hit@1, Hit@3, and Hit@5. |
| **Part G** | Test suite expansion | ✅ Complete | 55 passing tests (43 baseline + 12 new search/ACL tests). |
| **Part H** | Documentation updates | ✅ Complete | `README.md` and `.env.example` updated with cmd instructions and settings. |

---

## 3. Detailed Changes by Module

### Part A: Cleanup of Leftovers
1. **Clearance Removal**:
   - `backend/app/db/models.py`: Removed `clearance` from `User`.
   - `backend/app/api/auth.py`: Removed from `UserOut` and `UserCreate`.
   - `backend/app/api/admin.py`: Removed from `CreateUserRequest`, `UserOut`, and `UpdateRolesRequest`.
   - `backend/scripts/create_tables.py` & `backend/tests/conftest.py`: Added `ALTER TABLE users DROP COLUMN IF EXISTS clearance;`.
2. **Public Self-Registration Gate (`ALLOW_SELF_REGISTER`)**:
   - `backend/app/config.py`: Added setting `ALLOW_SELF_REGISTER: bool = False`.
   - `backend/app/api/auth.py`: When disabled, `POST /auth/register` returns `403 Forbidden` (`"Registration is disabled"`). When enabled, creates users with `roles=[]` and `employee_id=None` (zero document tokens).
3. **Inactive User Invalidation**:
   - Checked in `backend/app/security/deps.py`: `get_current_user` re-queries the user on every request. If `user.active == False`, raises `401 Unauthorized` immediately.

### Part B: Security Principals & Permission Tokens
- `backend/app/security/principals.py`:
  - Exposed `build_principal(user) -> Principal`: Returns `@dataclass(frozen=True) class Principal` with `user_id` and sorted `tokens`.
  - Built fresh from the database user model or dictionary on every request.
  - Generated token syntax:
    - `role:<role>` for each role in `ROLES`
    - `emp:<employee_id>`
    - `dept:<department>`
    - `rolemp:<role>@<employee_id>`
    - `usr:<user_id>`
  - Empty or null source attributes are skipped.
  - Platform admin role (`admin`) receives strictly `["role:admin"]`, which never appears in any document ACL, giving admins zero document access.

### Part C: `SecureStore.search`
- `backend/app/index/store.py`:
  - Signature: `search(principal, query, top_k=5, include_poison=False) -> list[SearchResult]`.
  - Mandatory `principal` argument with no caller-supplied raw filters.
  - Fail-closed: If `not principal or not principal.tokens`, immediately returns `[]` without querying Qdrant.
  - Top-K clamped to `1..20`. Query text trimmed and limited to 500 characters.
  - Hybrid retrieval using Qdrant's `query_points`:
    - Dense prefetch: `bge-m3` (1024-dim, cosine)
    - Sparse prefetch: `Qdrant/bm25` with IDF modifier
    - Reciprocal Rank Fusion (`models.FusionQuery(fusion=models.Fusion.RRF)`)
  - Access control filter (`MatchAny("acl_tokens", principal.tokens)`) applied to **both prefetches and outer query**.
  - `must_not` excludes `deleted=True` and `corpus="poison_test"` (unless `include_poison=True`).
  - Returns plain `SearchResult` objects: `chunk_id`, `source_id`, `file`, `page`, `corpus`, `text`, `score`. `acl_tokens` are never exposed to callers.

### Part D: Cross-Encoder Reranker
- `backend/app/rag/reranker.py`:
  - Added `Reranker` class wrapping `CrossEncoder("BAAI/bge-reranker-v2-m3", device="cpu")`.
  - Controlled by settings `RERANK_ENABLED` (default `False`) and `RERANK_CANDIDATES` (default `20`).
  - Runs strictly on candidates that have already passed Qdrant access filtering.
  - Graceful fallback: If model fails to load or inference errors, logs a warning and falls back to fused RRF order.

### Part E: `POST /search` Endpoint
- `backend/app/api/search.py`:
  - Authenticated route requiring Bearer JWT.
  - In-memory sliding-window rate limiter (60 req/min per user), returning `429 Too Many Requests`.
  - Audit logging via `write_audit`: Logs `user_id`, `timestamp`, `query` (truncated to 200 chars), returned `chunk_ids`, and `count`. Never logs document text.
  - Side-channel defense: Missing topics and forbidden topics return byte-for-byte identical output:
    ```json
    {
      "results": [],
      "count": 0,
      "message": "No accessible results found."
    }
    ```

### Part F: Demo & Verification Scripts
- `backend/scripts/compare_users.py`:
  - Takes `"question" [--top-k 5] [--rerank]`.
  - Searches for each of the 7 seeded users and prints an ASCII table.
  - Validates every result against reference `acl.py`.
- `backend/scripts/leak_check.py`:
  - Evaluates all 50 evaluation questions and 46 adversarial queries as every user (672 searches).
  - Verifies zero unauthorized chunks. Reports Hit@1, Hit@3, and Hit@5 for authorized queries.

---

## 4. Qdrant Point Count & Ingestion Idempotency Proof

### Cause of 54 vs 46 Points
- **Corpus `main`**: 7 PDFs = 46 chunks total.
- **Corpus `poison_test`**: 3 poison files = 8 chunks total.
- **Total Points in Collection**: 54 chunks.

```
Point Breakdown by Corpus & Document:
  corpus=main         pdf:board_minutes_2026_08.pdf                   count=7
  corpus=main         pdf:finance_memo_q2_fy27.pdf                    count=8
  corpus=main         pdf:hr_policy.pdf                               count=6
  corpus=main         pdf:it_security_policy.pdf                      count=2
  corpus=main         pdf:leave_policy.pdf                            count=8
  corpus=main         pdf:travel_expense_policy.pdf                   count=8
  corpus=main         pdf:vendor_contract_apex.pdf                    count=7
  corpus=poison_test  poison:poison_01_vendor_onboarding_checklist.pdf count=6
  corpus=poison_test  poison:poison_02_helpdesk_faq.md                 count=1
  corpus=poison_test  poison:poison_03_cafeteria_holiday_notice.html   count=1
```

### Idempotency Proof
Point IDs are deterministic UUID5 hashes of `chunk_id`. Re-running `ingest_corpus.py` overwrites points in place without expanding the collection.
```cmd
python scripts\ingest_corpus.py --include-poison
```
- **Points before execution**: 54
- **Points ingested**: 54
- **Points after execution**: 54

---

## 5. Test Suite Verification (55 Passing Tests)

```cmd
pytest tests/ -v
```

```
tests/test_admin.py::test_non_admin_gets_403 PASSED                      [  1%]
tests/test_admin.py::test_admin_creates_user_who_can_login PASSED        [  3%]
tests/test_admin.py::test_self_registered_user_has_no_roles PASSED       [  5%]
tests/test_admin.py::test_register_ignores_roles_in_body PASSED          [  7%]
tests/test_admin.py::test_deactivating_user_makes_token_return_401 PASSED [  9%]
tests/test_admin.py::test_admin_actions_appear_in_audit_log PASSED       [ 10%]
tests/test_auth.py::test_login_succeeds_for_all_seeded_users PASSED      [ 12%]
tests/test_auth.py::test_login_with_northwind_example_domain PASSED      [ 14%]
tests/test_auth.py::test_wrong_password_returns_401 PASSED               [ 16%]
tests/test_auth.py::test_unknown_email_returns_401_same_message PASSED   [ 18%]
tests/test_auth.py::test_me_returns_correct_role_for_all_users PASSED    [ 20%]
tests/test_auth.py::test_me_returns_employee_id_and_dept_for_asha PASSED [ 21%]
tests/test_auth.py::test_me_admin_has_none_employee_id_and_dept PASSED   [ 23%]
tests/test_auth.py::test_register_disabled_by_default_returns_403 PASSED [ 25%]
tests/test_auth.py::test_user_with_empty_roles_gets_200_on_me PASSED     [ 27%]
tests/test_auth.py::test_tampered_token_returns_401 PASSED               [ 29%]
tests/test_auth.py::test_expired_token_returns_401 PASSED                [ 30%]
tests/test_auth.py::test_inactive_user_returns_401 PASSED                [ 32%]
tests/test_auth.py::test_role_change_reflected_without_new_token PASSED  [ 34%]
tests/test_auth.py::test_me_and_auth_me_return_identical_bodies PASSED   [ 36%]
tests/test_auth.py::test_openapi_has_bearer_scheme PASSED                [ 38%]
tests/test_auth.py::test_no_auth_header_returns_401 PASSED               [ 40%]
tests/test_auth.py::test_cors_allows_valid_origin PASSED                 [ 41%]
tests/test_auth.py::test_cors_blocks_evil_origin PASSED                  [ 43%]
tests/test_auth.py::test_register_rejects_7_char_password PASSED         [ 45%]
tests/test_auth.py::test_register_accepts_8_char_password PASSED         [ 47%]
tests/test_auth.py::test_register_rejects_73_byte_password PASSED        [ 49%]
tests/test_auth.py::test_login_overlong_password_returns_401 PASSED      [ 50%]
tests/test_dataset_ingestion.py::test_payload_indexes_present_in_collection PASSED [ 52%]
tests/test_dataset_ingestion.py::test_ingest_7_main_pdfs_with_fake_embedder PASSED [ 54%]
tests/test_dataset_ingestion.py::test_eval_questions_ground_truth_coverage PASSED [ 56%]
tests/test_dataset_ingestion.py::test_poison_files_ingestion_and_content PASSED [ 58%]
tests/test_dataset_ingestion.py::test_ingestion_idempotency PASSED       [ 60%]
tests/test_dataset_ingestion.py::test_unlisted_document_fails_closed PASSED [ 61%]
tests/test_dataset_ingestion.py::test_bge_m3_embedding_dimension PASSED  [ 63%]
tests/test_health.py::test_health_reports_ok PASSED                      [ 65%]
tests/test_health.py::test_root_reports_ok PASSED                        [ 67%]
tests/test_principals.py::test_user_tokens_generation PASSED             [ 69%]
tests/test_principals.py::test_admin_has_no_document_tokens PASSED       [ 70%]
tests/test_principals.py::test_empty_user_has_no_tokens PASSED           [ 72%]
tests/test_principals.py::test_doc_tokens_hr_policy PASSED               [ 74%]
tests/test_principals.py::test_doc_tokens_with_employee_and_dept PASSED  [ 76%]
tests/test_principals.py::test_all_19_documents_match_reference_acl_for_all_users PASSED [ 78%]
tests/test_search.py::test_filter_construction_empty_tokens_no_qdrant_call PASSED [ 80%]
tests/test_search.py::test_filter_construction_present_on_prefetches_and_query PASSED [ 81%]
tests/test_search.py::test_principal_role_change_reflected_without_relogin[asyncio] PASSED [ 83%]
tests/test_search.py::test_search_without_token_returns_401[asyncio] PASSED [ 85%]
tests/test_search.py::test_search_with_tampered_token_returns_401[asyncio] PASSED [ 87%]
tests/test_search.py::test_search_with_deactivated_user_returns_401[asyncio] PASSED [ 89%]
tests/test_search.py::test_acl_separation_vendor_contract[asyncio] PASSED [ 90%]
tests/test_search.py::test_acl_separation_finance_memo_and_board_minutes[asyncio] PASSED [ 92%]
tests/test_search.py::test_admin_gets_zero_results[asyncio] PASSED       [ 94%]
tests/test_search.py::test_identical_empty_response_forbidden_vs_nonexistent[asyncio] PASSED [ 96%]
tests/test_search.py::test_poison_corpus_never_returned_by_default[asyncio] PASSED [ 98%]
tests/test_search.py::test_search_rate_limiting[asyncio] PASSED          [100%]

============================= 55 passed in 57.60s =============================
```

---

## 6. Security Leak Audit (`scripts/leak_check.py`)

```
===============================================================================================
AUDIT RESULTS BY USER
===============================================================================================
User       | Role            | Searches  | Chunks   | Violations | Hit@1        | Hit@3        | Hit@5   
-----------------------------------------------------------------------------------------------
u_asha     | employee        | 96        | 480      | 0          | 8/8 (100.0%) | 8/8 (100.0%) | 8/8 (100.0%)
u_neha     | employee        | 96        | 480      | 0          | 4/5 (80.0%)  | 5/5 (100.0%) | 5/5 (100.0%)
u_ravi     | manager         | 96        | 480      | 0          | 6/6 (100.0%) | 6/6 (100.0%) | 6/6 (100.0%)
u_dev      | manager         | 96        | 480      | 0          | 1/1 (100.0%) | 1/1 (100.0%) | 1/1 (100.0%)
u_meera    | hr_admin        | 96        | 480      | 0          | 2/2 (100.0%) | 2/2 (100.0%) | 2/2 (100.0%)
u_karan    | finance_admin   | 96        | 480      | 0          | 7/10 (70.0%) | 10/10 (100%) | 10/10 (100%)
u_admin    | admin           | 96        | 0        | 0          | N/A          | N/A          | N/A     
===============================================================================================
TOTAL SEARCH CHECKS PERFORMED : 672
TOTAL CHUNKS INSPECTED        : 2,880
TOTAL ACL VIOLATIONS          : 0
OVERALL HIT@1 (PDF Queries)   : 28/32 (87.5%)
OVERALL HIT@3 (PDF Queries)   : 32/32 (100.0%)
OVERALL HIT@5 (PDF Queries)   : 32/32 (100.0%)
===============================================================================================
[SUCCESS] ZERO ACL VIOLATIONS: SecureStore perfectly enforced access control across all queries!
```

---

## 7. Multi-User Comparison Outputs (`scripts/compare_users.py`)

### 1. "What is the notice period for confirmed employees?"
All authorized roles (`employee`, `manager`, `hr_admin`, `finance_admin`) retrieve `pdf:hr_policy.pdf`. Admin retrieves 0.
```
User       | Role            | Results | Top Sources (Source ID:Page)                                     
---------------------------------------------------------------------------------------------------------
u_asha     | employee        | 5       | pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2 
u_neha     | employee        | 5       | pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2 
u_ravi     | manager         | 5       | pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2 
u_dev      | manager         | 5       | pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2 
u_meera    | hr_admin        | 5       | pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2 
u_karan    | finance_admin   | 5       | pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2, pdf:hr_policy.pdf:p2 
u_admin    | admin           | 0       | (none)                                                           
```

### 2. "What is the Apex vendor contract value?"
Employees (`u_asha`, `u_neha`) and HR (`u_meera`) receive zero chunks from `vendor_contract_apex.pdf`. Managers (`u_ravi`, `u_dev`) and Finance (`u_karan`) retrieve the confidential contract.
```
User       | Role            | Results | Top Sources (Source ID:Page)                                     
---------------------------------------------------------------------------------------------------------
u_asha     | employee        | 5       | pdf:travel_expense_policy.pdf:p2, pdf:travel_expense_policy.pdf:p2
u_neha     | employee        | 5       | pdf:travel_expense_policy.pdf:p2, pdf:travel_expense_policy.pdf:p2
u_ravi     | manager         | 5       | pdf:vendor_contract_apex.pdf:p1, pdf:vendor_contract_apex.pdf:p1 
u_dev      | manager         | 5       | pdf:vendor_contract_apex.pdf:p1, pdf:vendor_contract_apex.pdf:p1 
u_meera    | hr_admin        | 5       | pdf:board_minutes_2026_08.pdf:p2, pdf:travel_expense_policy.pdf:p2
u_karan    | finance_admin   | 5       | pdf:vendor_contract_apex.pdf:p1, pdf:board_minutes_2026_08.pdf:p2 
u_admin    | admin           | 0       | (none)                                                           
```

### 3. "What was decided in the August board meeting?"
Only HR Admin (`u_meera`) and Finance Admin (`u_karan`) retrieve `pdf:board_minutes_2026_08.pdf`. Employees and managers receive general policies.
```
User       | Role            | Results | Top Sources (Source ID:Page)                                     
---------------------------------------------------------------------------------------------------------
u_asha     | employee        | 5       | pdf:hr_policy.pdf:p3, pdf:travel_expense_policy.pdf:p2           
u_neha     | employee        | 5       | pdf:hr_policy.pdf:p3, pdf:travel_expense_policy.pdf:p2           
u_ravi     | manager         | 5       | pdf:hr_policy.pdf:p3, pdf:travel_expense_policy.pdf:p2           
u_dev      | manager         | 5       | pdf:hr_policy.pdf:p3, pdf:travel_expense_policy.pdf:p2           
u_meera    | hr_admin        | 5       | pdf:board_minutes_2026_08.pdf:p2, pdf:board_minutes_2026_08.pdf:p1
u_karan    | finance_admin   | 5       | pdf:board_minutes_2026_08.pdf:p2, pdf:board_minutes_2026_08.pdf:p1
u_admin    | admin           | 0       | (none)                                                           
```

---

## 8. CPU Latency Benchmarks

Measured on host CPU across multiple runs with warmup:

| Method | Mean Latency | Added Overhead |
|---|---|---|
| **Hybrid Search (Dense `bge-m3` + Sparse `BM25` + RRF)** | **224.35 ms** | Baseline |
| **Hybrid Search + CrossEncoder Reranker (`bge-reranker-v2-m3`)** | **1,737.33 ms** | +1,512.98 ms |

---

## 9. API Walkthrough: Asha vs. Karan

### Query: *"What is the Apex vendor contract value?"*

#### 1. `u_asha` (Role: `employee`)
```cmd
curl -X POST "http://127.0.0.1:8000/search" ^
     -H "Authorization: Bearer <ASHA_TOKEN>" ^
     -H "Content-Type: application/json" ^
     -d "{\"query\":\"What is the Apex vendor contract value?\",\"top_k\":3}"
```
**Response (Asha receives only general travel expense chunks; no Apex contract)**:
```json
{
  "results": [
    {
      "chunk_id": "travel_expense_policy-p2-c3",
      "source_id": "pdf:travel_expense_policy.pdf",
      "file": "travel_expense_policy.pdf",
      "page": 2,
      "text": "Grade band: L4 to L5; Tier 1 city: Rs 6,500; Tier 2 city: Rs 4,800",
      "score": 0.5
    },
    {
      "chunk_id": "travel_expense_policy-p2-c2",
      "source_id": "pdf:travel_expense_policy.pdf",
      "file": "travel_expense_policy.pdf",
      "page": 2,
      "text": "Grade band: L1 to L3; Tier 1 city: Rs 4,500; Tier 2 city: Rs 3,200",
      "score": 0.333333
    },
    {
      "chunk_id": "travel_expense_policy-p2-c1",
      "source_id": "pdf:travel_expense_policy.pdf",
      "file": "travel_expense_policy.pdf",
      "page": 2,
      "text": "Northwind Industrial Pvt Ltd | Travel and Expense Policy FIN-POL-007 v4.0 | Internal Page 2 of 3 2. Hotel Caps and Approval Limits...",
      "score": 0.25
    }
  ],
  "count": 3
}
```

#### 2. `u_karan` (Role: `finance_admin`)
```cmd
curl -X POST "http://127.0.0.1:8000/search" ^
     -H "Authorization: Bearer <KARAN_TOKEN>" ^
     -H "Content-Type: application/json" ^
     -d "{\"query\":\"What is the Apex vendor contract value?\",\"top_k\":3}"
```
**Response (Karan retrieves the confidential contract and board approval)**:
```json
{
  "results": [
    {
      "chunk_id": "board_minutes_2026_08-p2-c1",
      "source_id": "pdf:board_minutes_2026_08.pdf",
      "file": "board_minutes_2026_08.pdf",
      "page": 2,
      "text": "Northwind Industrial Pvt Ltd | Minutes of Board Meeting - 14 August 2026 BRD-MIN-2026-03 | Confidential | CONF-BRD-7731 Page 2 of 3 Resolutions Passed R1. Resolved that the contract VC-2026-014 with Apex Logistics Pvt Ltd for logistics services, at an annual value of Rs 48,00,000 for 24 months from 1 April 2026, be and is hereby approved...",
      "score": 0.833333
    },
    {
      "chunk_id": "vendor_contract_apex-p1-c1",
      "source_id": "pdf:vendor_contract_apex.pdf",
      "file": "vendor_contract_apex.pdf",
      "page": 1,
      "text": "Northwind Industrial Pvt Ltd | Master Logistics Services Agreement VC-2026-014 | Confidential | CONF-VC-3340 Page 1 of 4 Master Logistics Services Agreement This Agreement is made between Northwind Industrial Pvt Ltd (the Company) and Apex Logistics Pvt Ltd (the Vendor), contract reference VC-2026-014. 1. Term The Agreement is effective for a term of 24 months, from 1 Apr 2026 - 31 Mar 2028, unless terminated earlier under Clause 7. 2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%.",
      "score": 0.833333
    },
    {
      "chunk_id": "finance_memo_q2_fy27-p2-c1",
      "source_id": "pdf:finance_memo_q2_fy27.pdf",
      "file": "finance_memo_q2_fy27.pdf",
      "page": 2,
      "text": "Northwind Industrial Pvt Ltd | Finance Memo - Q2 FY27 Spend Review FIN-MEMO-2026-09 | Confidential | FIN-CONF-5520 Page 2 of 2 Actions... Payments to Apex Logistics above the contract rate, including fuel surcharges above the contractual cap, are on hold until the vendor provides supporting documents...",
      "score": 0.45
    }
  ],
  "count": 3
}
```
