# VaultRAG Step 5e: Department Access Model, Single Admin & Salary Rule Implementation Summary

## 1. Executive Summary & Verification Matrix

Step 5e transitions VaultRAG from a role-centric evaluation access model to a production **Department Access Model** with strict separation of financial and human resource authorities, centralized single-admin governance, and dual-model backward compatibility.

### Key Achievements
1. **Department Access Model & Canonical Tokens**:
   - Replaced multi-admin legacy roles (`hr_admin`, `finance_admin`, `manager`) with department-based scoping (`dept:HR`, `dept:Finance`, `dept:Engineering`, `dept:Sales`).
   - Standardized principal tokens: `org:northwind`, `dept:<Dept>`, `emp:<id>`, `usr:<uuid>`, and `role:employee` or `role:admin`.
   - Inactive accounts fail closed immediately (`tokens = []`).
2. **The Salary Rule Enforced**:
   - Members of the **Finance** department (`dept:Finance`) can read all employees' salaries.
   - **HR members are strictly forbidden** from reading other employees' salaries.
   - Employees can always read their own salary (`emp:<id>`).
   - HR retains exclusive responsibility for personal employee records (e.g. `db:employees:sensitive`, ID cards, onboarding, leave).
3. **Single Platform Admin (`ADMIN_SEES_ALL`)**:
   - Exactly one user has the role `admin` (`u_admin`). All other users are `role:employee`.
   - Access is enforced inside Qdrant via `MatchAny` on `acl_tokens` across dense prefetch, sparse prefetch, and final search.
   - Zero bypass in query filters: Admin sees all points solely because `role:admin` is appended to every chunk's ACL token set.
4. **Dual-Model Compatibility (`ACCESS_MODEL`)**:
   - Configurable via `ACCESS_MODEL=department|dataset` in `.env` and `app/config.py`.
   - Allows instant switching between production department ACLs and legacy evaluation dataset ACLs without re-embedding vectors.
5. **Demo User Exposure & Admin User Management**:
   - All 7 Northwind accounts remain active in the database; exactly 4 are exposed in the demo interface (`shown_in_demo = True`).
   - Added public sanitized endpoint `GET /auth/demo-users`.
   - Added administrative user lifecycle management (`GET /admin/users`, `POST /admin/users`, `PATCH /admin/users/{id}`) protected by neutral `404 Not Found` guards for non-admins, self-deactivation blocks, duplicate email checks, and immediate JWT rejection upon account deactivation.
6. **Frontend Experience & Security Alignment**:
   - Login page renders one-click demo chips fetched dynamically from `/auth/demo-users`.
   - Replaced role badges across the application with `DepartmentBadge` (no internal role names exposed in the UI).

---

### Verification Matrix

| Verification Check | Target / Rule | Actual Live Result | Status |
|---|---|---|:---:|
| **`test_department_acl_matrix.py`** | 14 test cases covering salary rule, policies, boards, ID cards | **14 passed** (0.64s) | ✅ PASS |
| **`test_step5e_endpoints.py`** | 5 test cases for demo-users, admin guards, create & patch user | **5 passed** (1.37s) | ✅ PASS |
| **Full Backend Suite** | `pytest -m "not llm and not ocr and not dataset_model"` | **136 passed, 19 deselected** (152.09s) | ✅ PASS |
| **`scripts/acl_matrix.py`** | 100% match with dataset `acl.py` in dataset mode | **140/140 doc cells, 1260/1260 DB checks (0 mismatches)** | ✅ PASS |
| **`leak_check.py --model department`** | 0 ACL leaks across 672 cross-user queries (3,360 chunks) | **0 violations, 0 image violations (63/63 clean)** | ✅ PASS |
| **`leak_check.py --model dataset`** | 0 ACL leaks across 672 cross-user queries in dataset mode | **0 violations, 0 image violations (63/63 clean)** | ✅ PASS |
| **Frontend Typecheck** | `npm run typecheck` (tsc -b) | **0 type errors (exit code 0)** | ✅ PASS |
| **Frontend Vitest** | `npm test` across all 10 frontend test suites | **42 passed (10 files, 2.46s)** | ✅ PASS |
| **Frontend Production Build** | `npm run build` (tsc -b && vite build) | **0 errors (built in 1.91s)** | ✅ PASS |

---

## 2. Access Policy Specification

### 1. Single Admin Architecture
- **Single Admin Principle**: Only one account (`u_admin`, `admin@northwind.example`) possesses the `admin` role. All other accounts are strictly `employee`.
- **Zero Filter Bypass**: The backend search pipeline constructs a single filter for all users:
  ```python
  qmodels.Filter(
      must=[
          qmodels.FieldCondition(
              key="acl_tokens",
              match=qmodels.MatchAny(any=principal.tokens)
          )
      ]
  )
  ```
  The platform admin is never exempted from this filter. Instead, the ingestion pipeline and retagging scripts append the token `role:admin` to every chunk (`ADMIN_SEES_ALL`). If `role:admin` is missing from a chunk, even the admin cannot retrieve it.

### 2. Canonical Principal Tokens
On every incoming request, `build_principal(user)` queries the database directly to synthesize the active principal. Never trusting client JWT claims, the principal consists of:
1. `org:northwind`: Granted to all active Northwind employees for company-wide policies, handbooks, and announcements.
2. `dept:<Dept>`: Granted based on the employee's department (`dept:HR`, `dept:Finance`, `dept:Engineering`, `dept:Sales`).
3. `emp:<id>`: Granted to uniquely identify the employee (e.g. `emp:E1001`, `emp:E1004`) for personal records, expense claims, approvals, and receipts.
4. `usr:<uuid>`: Internal primary key for personal uploaded documents and granular sharing.
5. `role:employee` or `role:admin`: Role token.
6. **Deactivated Users**: For any user with `active=False`, `build_principal()` immediately assigns `tokens=[]`, causing Qdrant's `MatchAny` filter to fail closed and retrieve zero chunks.

### 3. The Salary Rule
- **Financial Access**: Members of `dept:Finance` have operational necessity to audit and disburse payroll; they are authorized to read all salary records (`db:salaries:base` and `db:salaries:sensitive`).
- **HR Exclusion**: Members of `dept:HR` are strictly barred from querying or retrieving compensation data of other employees. Their principal lacks `dept:Finance` and other employees' `emp:<id>` tokens.
- **Self-Inspection**: Every employee can read their own salary records via their unique `emp:<id>` token (e.g. Asha Patel can query her own CTC via `emp:E1004`).
- **HR Domain Scope**: HR manages human capital governance rather than payroll disbursement. HR retains exclusive access to:
  - Personal identifiable information (`db:employees:sensitive`).
  - Employee ID cards (`img:id_card_E1004.png`, `img:id_card_E1010.png`).
  - Onboarding checklists, leave policies, and board minutes (co-managed with Finance).

### 4. Document Uploads & Live Sharing
- Uploaded files (`upl:<uuid>`) are tagged with the creator's `usr:<uuid>` and `role:admin`.
- When shared to a department, `dept:<Dept>` is appended to the chunk's `acl_tokens` in Qdrant.
- When shared with specific users, `usr:<grantee_uuid>` is appended.
- Revocation immediately removes the corresponding token using `store.batch_update_acl_tokens()`.

---

## 3. Applied ACL Mapping Table

The dataset points (244 chunks) were retagged in-place using `backend/scripts/retag_acl.py --model department`. The mapping converts legacy role-based tokens into canonical department tokens while preserving the `ADMIN_SEES_ALL` guarantee (`role:admin`):

| Source Pattern | Legacy Dataset Tokens | Department Model Tokens (Step 5e) | Access Rationale |
|---|---|---|---|
| `pdf:hr_policy.pdf`<br>`pdf:leave_policy.pdf`<br>`pdf:travel_expense_policy.pdf`<br>`pdf:it_security_policy.pdf`<br>`poison:poison_01_*.pdf`<br>`poison:poison_02_*.md`<br>`poison:poison_03_*.html` | `['role:employee', 'role:admin']` | `['org:northwind', 'role:admin']` | General company-wide documents readable by any active employee. |
| `pdf:board_minutes_2026_08.pdf` | `['role:hr_admin', 'role:finance_admin', 'role:admin']` | `['dept:HR', 'dept:Finance', 'role:admin']` | Strategic executive minutes accessible only to HR and Finance leadership. |
| `pdf:vendor_contract_apex.pdf` | `['role:manager', 'role:finance_admin', 'role:admin']` | `['dept:Finance', 'role:admin']` | Commercial procurement contract restricted to Finance. |
| `pdf:finance_memo_q2_fy27.pdf` | `['role:finance_admin', 'role:admin']` | `['dept:Finance', 'role:admin']` | Internal financial variance memo restricted to Finance. |
| `img:invoice_*.png`<br>`img:purchase_order_*.png` | `['role:finance_admin', 'role:admin']` | `['dept:Finance', 'role:admin']` | Accounts payable and procurement records restricted to Finance. |
| `img:receipt_hotel_lotus.png` | `['role:finance_admin', 'rolemp:employee@E1010', 'role:admin']` | `['dept:Finance', 'emp:E1010', 'role:admin']` | Expense receipt accessible to Finance and the submitting employee (`E1010`). |
| `img:id_card_E1004.png`<br>`img:id_card_E1010.png` | `['role:hr_admin', 'rolemp:employee@<id>', 'role:admin']` | `['dept:HR', 'emp:<id>', 'role:admin']` | Personal identity badges accessible to HR and the individual employee. |
| `img:whiteboard_sprint.jpg` | `['role:manager', 'role:employee', 'role:hr_admin', 'role:admin']` | `['dept:Engineering', 'dept:HR', 'role:admin']` | Technical roadmap diagram accessible to Engineering and HR. |
| `db:employees:base` | `['role:employee', 'role:admin']` | `['org:northwind', 'role:admin']` | Directory baseline (name, department, role, email) visible company-wide. |
| `db:employees:sensitive` | `['role:hr_admin', 'rolemp:employee@<id>', 'role:admin']` | `['dept:HR', 'emp:<id>', 'role:admin']` | Personal PII (phone, address, emergency contact) restricted to HR and individual. |
| `db:salaries:base` | `['role:hr_admin', 'role:finance_admin', 'rolemp:employee@<id>', 'role:admin']` | `['dept:Finance', 'emp:<id>', 'role:admin']` | **Salary Rule**: HR excluded. Accessible only to Finance and individual. |
| `db:salaries:sensitive` | `['role:finance_admin', 'rolemp:employee@<id>', 'role:admin']` | `['dept:Finance', 'emp:<id>', 'role:admin']` | **Salary Rule**: Tax/bonus details accessible only to Finance and individual. |
| `db:expenses:base` | `['role:finance_admin', 'role:manager', 'rolemp:employee@<id>', 'role:admin']` | `['dept:Finance', 'emp:<submitter>', 'role:admin']` | Operational reimbursement claims visible to Finance and submitter. |
| `db:approvals:base` | `['role:finance_admin', 'role:manager', 'rolemp:employee@<id>', 'role:admin']` | `['dept:Finance', 'emp:<submitter>', 'role:admin']` | Approval hierarchy logs visible to Finance and expense claimant. |

---

## 4. Retagging Statistics & Token Distributions

The retagging tool (`scripts/retag_acl.py`) operates directly against Qdrant point payloads via `set_payload`, eliminating any need for vector recalculations.

```
===============================================================================================
VaultRAG In-Place ACL Retagging Tool (Model: DEPARTMENT)
Total points in collection: 297 (Dataset: 244, Uploads skipped: 53)
Dry Run: False
===============================================================================================
[OK] Backup of 244 point ACLs saved to D:\VaultRAG\backend\scripts\retag_backup.json
[SUCCESS] Successfully updated 244 points in Qdrant with DEPARTMENT ACL tokens!
```

### Unique Token Set Distributions
Before retagging (legacy dataset model), the collection contained **55** unique token sets. Under the Department Model, the collection contains **54** canonical token sets:

| Token Set Payload | Chunks Count | Description |
|---|:---:|---|
| `['org:northwind', 'role:admin']` | 57 | Company policies, poison docs, employee directory base |
| `['dept:Finance', 'role:admin']` | 21 | Invoices, purchase orders, vendor contracts, finance memos |
| `['dept:Finance', 'emp:E1004', 'role:admin']` | 14 | Asha Patel salaries and expense items |
| `['dept:Finance', 'emp:E1003', 'role:admin']` | 10 | Ravi Menon salaries and expense items |
| `['dept:Finance', 'emp:E1009', 'role:admin']` | 10 | Vikram Malhotra salaries and expense items |
| `['dept:Finance', 'emp:E1010', 'role:admin']` | 9 | Sneha Reddy salaries, expenses, hotel receipt |
| `['dept:Finance', 'emp:E1023', 'role:admin']` | 8 | Manisha Rao salaries and expenses |
| `['dept:Finance', 'dept:HR', 'role:admin']` | 7 | August 2026 Board minutes |
| `['dept:Finance', 'emp:E1024', 'role:admin']` | 6 | Ananya Roy salaries and expenses |
| `['dept:Finance', 'emp:E1019', 'role:admin']` | 6 | Amit Verma salaries and expenses |
| Other `['dept:Finance', 'emp:<id>', 'role:admin']` sets | 64 | Individual employee compensation and reimbursement claims |
| `['dept:HR', 'emp:<id>', 'role:admin']` sets | 28 | Individual employee sensitive PII and photo ID badges |
| `['dept:Engineering', 'dept:HR', 'role:admin']` | 4 | Sprint architecture whiteboard chunks |
| **Total Dataset Points** | **244** | **100% Retagged** |

---

## 5. Northwind User Accounts Configuration

All 7 core Northwind accounts are registered in the PostgreSQL database. Exactly one user has the role `admin`, and exactly 4 accounts are flagged as visible in the login interface (`shown_in_demo = True`):

| User ID (UUID) | Full Name | Email Address | Roles | Department | Employee ID | Active | Shown in Demo |
|---|---|---|:---:|:---:|:---:|:---:|:---:|
| `a99f22fd-76f2-4d61-9e95-b2f842c8bc68` | **System Admin** | `admin@northwind.example` | `['admin']` | *None* | *None* | `True` | **`True`** |
| `1180fb86-5a54-4481-982c-e7db6a63ae05` | **Meera Iyer** | `meera.iyer@northwind.example` | `['employee']` | `HR` | `E1001` | `True` | **`True`** |
| `6c43cfdf-f63f-4792-98ce-53156a8a79ba` | **Karan Shah** | `karan.shah@northwind.example` | `['employee']` | `Finance` | `E1002` | `True` | **`True`** |
| `99b297ae-a42c-4019-b34b-70f24dd59159` | **Asha Patel** | `asha.patel@northwind.example` | `['employee']` | `Engineering` | `E1004` | `True` | **`True`** |
| `bd7a24a5-643f-439d-bcb0-86535b783cec` | **Ravi Menon** | `ravi.menon@northwind.example` | `['employee']` | `Engineering` | `E1003` | `True` | `False` |
| `db07f09c-65d2-40eb-bfee-4027d1aaac66` | **Dev Joshi** | `dev.joshi@northwind.example` | `['employee']` | `Sales` | `E1005` | `True` | `False` |
| `50ecd387-e000-49a1-b3bd-940502dd3f0a` | **Neha Desai** | `neha.desai@northwind.example` | `['employee']` | `Sales` | `E1006` | `True` | `False` |

*Note: Legacy test fixtures from previous sessions (Arjun, Rahul, Meera, Priya) have `active = False` and `shown_in_demo = False`.*

---

## 6. Evaluation Benchmark Impact: Question Q035 Analysis

Under Step 5e, the evaluation dataset files (`dataset/acl.py`, `eval_answers_cache.json`) were preserved unchanged as specified by the standing rules.

### Behavior of Question Q035
- **Query Q035**: *"What is Asha Patel's revised CTC after the October increment?"*
- **Asker**: `u_meera` (Meera Iyer).
- **Target Data**: `db:salaries` (Asha Patel, `E1004`).
- **Legacy Dataset Model**:
  - In `ACCESS_MODEL=dataset`, Meera held the role `hr_admin`. Under the dataset's `acl.py`, `hr_admin` had access to all salary records. Thus, Q035 was answerable by Meera.
- **Department Model (`ACCESS_MODEL=department`)**:
  - Under the Salary Rule, Meera is in `HR`. **HR employees are strictly excluded from reading salaries of other employees**.
  - Meera's principal lacks both `dept:Finance` and `emp:E1004`.
  - SecureStore filters out `db:salaries#E1004` during Qdrant search.
  - The system correctly issues a refusal (`llm_not_answerable` / insufficient context) for Meera.
  - If asked by **Karan Shah** (`dept:Finance`) or **Asha Patel** herself (`emp:E1004`), the system retrieves the record and provides the exact CTC answer.

---

## 7. Complete Verification Log & Live Outputs

### 1. `test_department_acl_matrix.py` (14/14 Passed)
```
============================= test session starts =============================
collected 14 items

tests/test_department_acl_matrix.py::test_policies_and_handbook_accessible_to_all_active_users PASSED [  7%]
tests/test_department_acl_matrix.py::test_salary_rule_finance_reads_all PASSED [ 14%]
tests/test_department_acl_matrix.py::test_salary_rule_hr_cannot_read_others PASSED [ 21%]
tests/test_department_acl_matrix.py::test_salary_rule_employee_reads_only_own_salary PASSED [ 28%]
tests/test_department_acl_matrix.py::test_employees_base_columns_accessible_to_all PASSED [ 35%]
tests/test_department_acl_matrix.py::test_employees_sensitive_and_id_cards_hr_reads_all PASSED [ 42%]
tests/test_department_acl_matrix.py::test_employees_sensitive_and_id_cards_finance_cannot_read_others PASSED [ 50%]
tests/test_department_acl_matrix.py::test_employees_sensitive_employee_reads_own_only PASSED [ 57%]
tests/test_department_acl_matrix.py::test_expenses_and_approvals_finance_and_owner PASSED [ 64%]
tests/test_department_acl_matrix.py::test_invoices_and_vendor_contract_finance_only PASSED [ 71%]
tests/test_department_acl_matrix.py::test_board_minutes_hr_and_finance PASSED [ 78%]
tests/test_department_acl_matrix.py::test_whiteboard_engineering_and_hr PASSED [ 85%]
tests/test_department_acl_matrix.py::test_admin_sees_all_documents_and_tables PASSED [ 92%]
tests/test_department_acl_matrix.py::test_deactivated_user_reads_nothing PASSED [100%]

============================== 14 passed in 0.64s ==============================
```

### 2. `test_step5e_endpoints.py` (5/5 Passed)
```
============================= test session starts =============================
collected 5 items

tests/test_step5e_endpoints.py::test_demo_users_endpoint_public_and_sanitized PASSED [ 20%]
tests/test_step5e_endpoints.py::test_admin_users_guards_neutral_404_and_401 PASSED [ 40%]
tests/test_step5e_endpoints.py::test_admin_create_user_and_duplicate_email PASSED [ 60%]
tests/test_step5e_endpoints.py::test_patch_user_and_prevent_self_deactivation PASSED [ 80%]
tests/test_step5e_endpoints.py::test_deactivated_user_rejected_immediately_on_next_request PASSED [100%]

============================== 5 passed in 1.37s ===============================
```

### 3. Full Backend Test Suite
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\VaultRAG\backend
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, asyncio-1.4.0
collected 155 items / 19 deselected / 136 selected

tests\test_admin.py ......                                               [  4%]
tests\test_admin_access.py ......                                        [  8%]
tests\test_ask.py ..................................                     [ 33%]
tests\test_auth.py ......................                                [ 50%]
tests\test_dataset_ingestion.py .......                                  [ 55%]
tests\test_department_acl_matrix.py ..............                       [ 65%]
tests\test_health.py ...                                                 [ 67%]
tests\test_image_ingest.py ..........                                    [ 75%]
tests\test_search.py ...........                                         [ 83%]
tests\test_source_view.py ........                                       [ 88%]
tests\test_step5e_endpoints.py .....                                     [ 92%]
tests\test_upload_sharing.py ..........                                  [100%]

=============== 136 passed, 19 deselected in 152.09s (0:02:32) ================
```

### 4. `scripts/leak_check.py --model department` (0 Violations)
```
===============================================================================================
VaultRAG Comprehensive Security Leak & Retrieval Audit
Eval Questions: 50 | Adversarial Queries: 46
Top-K: 5 | Rerank: False
===============================================================================================

Running 96 queries across 7 users (672 total searches)...

===============================================================================================
AUDIT RESULTS BY USER
===============================================================================================
User       | Role            | Searches  | Chunks   | Violations | Hit@1    | Hit@3    | Hit@5   
-----------------------------------------------------------------------------------------------
u_asha     | employee        | 96        | 480      | 0          | 9/10 (90.0%) | 10/10 (100.0%) | 10/10 (100.0%)
u_neha     | employee        | 96        | 480      | 0          | 4/5 (80.0%) | 5/5 (100.0%) | 5/5 (100.0%)
u_ravi     | employee        | 96        | 480      | 0          | 5/8 (62.5%) | 5/8 (62.5%) | 5/8 (62.5%)
u_dev      | employee        | 96        | 480      | 0          | 1/1 (100.0%) | 1/1 (100.0%) | 1/1 (100.0%)
u_meera    | employee        | 96        | 480      | 0          | 3/4 (75.0%) | 3/4 (75.0%) | 3/4 (75.0%)
u_karan    | employee        | 96        | 480      | 0          | 9/15 (60.0%) | 13/15 (86.7%) | 14/15 (93.3%)
u_admin    | admin           | 96        | 480      | 0          | N/A      | N/A      | N/A     
===============================================================================================
TOTAL SEARCH CHECKS PERFORMED : 672
TOTAL CHUNKS INSPECTED        : 3360
TOTAL ACL VIOLATIONS          : 0
OVERALL HIT@1 (Authorized Queries): 31/43 (72.1%)
OVERALL HIT@3 (Authorized Queries): 37/43 (86.0%)
OVERALL HIT@5 (Authorized Queries): 38/43 (88.4%)
===============================================================================================

===============================================================================================
IMAGE-TARGETED ACL AUDIT (Every User x Every Image Question Q041-Q049)
===============================================================================================
Total Image Questions: 9 | Total Cross-User Checks: 63
TOTAL IMAGE SEARCH CHECKS    : 63
TOTAL IMAGE ACL VIOLATIONS    : 0
===============================================================================================

[SUCCESS] ZERO ACL VIOLATIONS: SecureStore perfectly enforced access control across all queries!
```

### 5. `scripts/acl_matrix.py` (Dataset Reference Match)
```
===============================================================================================
VaultRAG vs Reference ACL Access Matrix (20 Documents [10 Images, 10 Text/Poison] × 7 Accounts = 140 Cells)
===============================================================================================
Total document checks: 140 (70 image checks across 7 users)
Document mismatches on dataset user rules: 0

===============================================================================================
VaultRAG vs Reference Database ACL Matrix (4 Tables, 180 Chunks × 7 Accounts)
===============================================================================================
Total database checks: 1260
Database mismatches on dataset user rules: 0
[INTENDED EXCEPTION] Platform admin (u_admin) can read all 180 database chunks (180 allowed via ADMIN_SEES_ALL role:admin chunk ACL token; dataset acl.py reference grants admin no database access).

[SUCCESS] 100% MATCH: Documents + Database records perfectly replicate dataset ACL rules (with intended admin exceptions)!
```

### 6. Frontend Test Suite & Build
```
> vaultrag-frontend@0.1.0 test
> vitest run

 ✓ src/test/parseAnswer.test.ts (5 tests) 3ms
 ✓ src/test/highlight.test.ts (5 tests) 4ms
 ✓ src/test/client.test.ts (4 tests) 7ms
 ✓ src/test/RefusalNotice.test.tsx (2 tests) 30ms
 ✓ src/test/ProtectedRoute.test.tsx (2 tests) 28ms
 ✓ src/test/AnswerCard.test.tsx (3 tests) 85ms
 ✓ src/test/sourceViewer.test.tsx (6 tests) 175ms
 ✓ src/test/adminDashboard.test.tsx (4 tests) 259ms
 ✓ src/test/documents.test.tsx (7 tests) 311ms
 ✓ src/test/shareDialog.test.tsx (4 tests) 484ms

 Test Files  10 passed (10)
      Tests  42 passed (42)
   Duration  2.46s

> vaultrag-frontend@0.1.0 build
> tsc -b && vite build

vite v6.4.4 building for production...
✓ 1605 modules transformed.
dist/index.html                           0.53 kB │ gzip:  0.34 kB
dist/assets/index-DbEQE0_V.css           32.87 kB │ gzip:  7.17 kB
dist/assets/index-DIbNYaJ0.js           316.37 kB │ gzip: 87.14 kB
✓ built in 1.91s
```
