# VaultRAG Step 4c Comprehensive Implementation Summary: Interactive Source Viewer

## Executive Summary
In **Step 4c**, VaultRAG was enhanced from a simple quotation snippet side-drawer to a full interactive **Source Viewer**. When a user clicks a citation `[n]`, the system now renders the **real source page** (PDF page image rendered at 150 DPI or high-resolution document image) with cited text bounding boxes overlaid directly onto the page, auto-scrolled to center the highlight with a subtle pulse animation. For database query results (`db_row`), the viewer presents a structured record card with field key-value pairs and highlighted passage text.

All core architectural and security invariants remain rigorously enforced:
1. **Zero Access-Control Bypass**: `SecureStore` remains the sole module importing `qdrant_client`. Every chunk lookup checks the user's principal ACL tokens retrieved fresh from PostgreSQL against the chunk's stored `acl_tokens`.
2. **Identical 404 Response**: Inaccessible chunks and non-existent chunks return the exact same HTTP 404 error payload: `{"detail": "Chunk not found"}`. No information is leaked regarding chunk existence.
3. **Zero Secret Leaks**: File system paths and `acl_tokens` are never exposed to the frontend or clients. File resolution is performed exclusively via the server-side `AssetStore` whitelist; traversal attempts (e.g. `..`) are strictly rejected.
4. **Zero Token / Document Text Logging**: Audit logs record only event types, hashed query IDs, audit IDs, chunk IDs, and the `admin_access` boolean flag.
5. **Read-Only Dataset**: The `data/northwind/rag_demo_dataset/dataset` directory remains untouched and strictly read-only.
6. **XSS Protection**: Frontend answers remain strictly plain text without `dangerouslySetInnerHTML`.

---

## 1. Architectural Design & Security Enforcement

### 1.1 Fresh Principal Construction & Chunk Resolution
Every request to `/source/*` extracts the user's JWT bearer token, resolves the user identity from PostgreSQL, builds their active `Principal` object (including roles, department, and employee ID tokens), and queries `SecureStore.get_chunk(principal, chunk_id)`:
```python
# backend/app/api/source.py
chunk = store.get_chunk(principal, chunk_id)
if not chunk:
    # Fail-closed: returns identical 404 whether chunk does not exist or user lacks tokens
    raise HTTPException(status_code=404, detail="Chunk not found")
```

### 1.2 AssetStore Whitelist & Path Traversal Prevention
Files referenced by `source_id` are resolved only through trusted registered asset roots (`data/northwind/rag_demo_dataset/dataset` and `data/poison`):
- Any filename containing path traversal sequences (`..`, `/`, `\`) or resolving outside registered roots triggers a `ValueError` which maps to an immediate 404.
- Clients never provide file paths; the backend looks up the canonical file path from the indexed chunk metadata inside `SecureStore`.

### 1.3 Identical 404 Contract
| Scenario | HTTP Status | Response Body |
| :--- | :--- | :--- |
| Chunk does not exist | `404 Not Found` | `{"detail": "Chunk not found"}` |
| User lacks ACL tokens (Forbidden) | `404 Not Found` | `{"detail": "Chunk not found"}` |
| Page out of bounds / unreadable | `404 Not Found` | `{"detail": "Chunk not found"}` |
| Path traversal attempt | `404 Not Found` | `{"detail": "Chunk not found"}` |

### 1.4 Audit Logging
Every access attempt to `/source/{chunk_id}/view`, `/source/{chunk_id}/page.png`, and `/source/{chunk_id}/pages` is recorded in the PostgreSQL audit log:
- `event_type`: `"source_view"`, `"source_page_png"`, or `"source_pages"`
- `user_id`: Authenticated user ID (e.g., `u_karan`, `u_admin`, `u_asha`)
- `admin_access`: Set to `True` if accessed by `u_admin` when exercising platform admin privileges, `False` otherwise.
- Zero raw text, prompt contents, or ACL tokens are written to audit logs.

---

## 2. API Endpoints & Real Verified Outputs

The `/source` router exposes three endpoints:

### 2.1 `GET /source/{chunk_id}/view?hl=start-end,start-end`
Returns metadata and normalized highlight bounding boxes `(x, y, w, h)` in `[0, 1]` coordinates relative to page dimensions:
```http
GET /source/vendor_contract_apex-p1-c1/view?hl=437-590 HTTP/1.1
Host: localhost:8000
Authorization: Bearer <karan_token>
```
**Response (200 OK):**
```json
{
  "kind": "pdf_text",
  "file": "vendor_contract_apex.pdf",
  "page": 1,
  "row_id": null,
  "page_width": 595.28,
  "page_height": 841.89,
  "rects": [
    {
      "x": 0.1053,
      "y": 0.2144,
      "w": 0.075,
      "h": 0.0131
    },
    {
      "x": 0.1053,
      "y": 0.2365,
      "w": 0.7791,
      "h": 0.0113
    },
    {
      "x": 0.1053,
      "y": 0.2532,
      "w": 0.4078,
      "h": 0.0113
    }
  ],
  "match": "exact",
  "text": "Northwind Industrial Pvt Ltd | Master Logistics Services Agreement VC-2026-014 | Confidential | CONF-VC-3340 Page 1 of 4 Master Logistics Services Agreement This Agreement is made between Northwind Industrial Pvt Ltd (the Company) and Apex Logistics Pvt Ltd (the Vendor), contract reference VC-2026-014. 1. Term The Agreement is effective for a term of 24 months, from 1 Apr 2026 - 31 Mar 2028, unless terminated earlier under Clause 7. 2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%.",
  "page_image_url": "/source/vendor_contract_apex-p1-c1/page.png?page=1"
}
```

### 2.2 `GET /source/{chunk_id}/page.png?page=N`
Renders the given page of a multi-page PDF at 150 DPI or returns raw document image bytes.
```http
GET /source/vendor_contract_apex-p1-c1/page.png?page=1 HTTP/1.1
Host: localhost:8000
Authorization: Bearer <karan_token>
```
**Response (200 OK):**
- **Status:** `200 OK`
- **Content-Type:** `image/png`
- **Cache-Control:** `private, max-age=300`
- **Content-Length:** `74,669 bytes`
- **Disk Cache Location:** `backend/data/cache/page_renders/8eeef0865c63ed65b6f04d026fe8276f_p1_150dpi.png`

### 2.3 `GET /source/{chunk_id}/pages`
Returns multi-page document pagination information and readable page numbers permitted by the user's ACL tokens:
```http
GET /source/vendor_contract_apex-p1-c1/pages HTTP/1.1
Host: localhost:8000
Authorization: Bearer <karan_token>
```
**Response (200 OK):**
```json
{
  "page_count": 4,
  "readable_pages": [1, 2, 3, 4]
}
```

### 2.4 Live Access Control Verification (Smoke Test)
When Asha (`asha.patel@northwind.example`, role `employee`) requests the exact same endpoints for the Apex Logistics contract (restricted to `finance_admin`):
```http
GET /source/vendor_contract_apex-p1-c1/view?hl=437-590 HTTP/1.1
Authorization: Bearer <asha_token>
--> HTTP/1.1 404 Not Found
--> {"detail":"Chunk not found"}

GET /source/vendor_contract_apex-p1-c1/page.png?page=1 HTTP/1.1
Authorization: Bearer <asha_token>
--> HTTP/1.1 404 Not Found
--> {"detail":"Chunk not found"}
```

---

## 3. Highlight Coordinate Alignment & Match Rate Audit

### 3.1 Bounding Box Calculation Algorithm
1. **PyMuPDF Word Stream Extraction**:
   Each PDF page is parsed using `page.get_text("words")`, yielding `(x0, y0, x1, y1, word, block_no, line_no, word_no)`.
2. **Text Normalization**:
   Punctuation, case, and whitespace are normalized across both the target passage and the PDF word stream.
3. **Sliding Window Sequence Match**:
   The engine locates the longest matching sequence of contiguous words from the passage in the page word stream.
4. **Line-Level Bounding Box Union**:
   Matched word bounding boxes on the same line are unified into a single line rectangle to eliminate jagged micro-boxes.
5. **Coordinate Normalization**:
   Final bounding boxes are converted to `{x, y, w, h}` normalized in `[0, 1]` relative to `page.rect.width` and `page.rect.height`.

### 3.2 Evaluation Benchmark Match Rate Audit
Audit conducted across **35 unique PDF citations** extracted from the evaluation query set (`backend/scripts/check_highlight_rects.py`):

| Match Category | Count | Percentage | Description |
| :--- | :--- | :--- | :--- |
| **Exact Matches** | **28** | **80.0%** | 100% of the cited passage words aligned directly to line bounding boxes on the page. |
| **Partial Matches** | **6** | **17.1%** | Citations from Markdown table rows (`leave_policy.pdf`, `hr_policy.pdf`, `travel_expense_policy.pdf`). Word sequences match the cell contents, with pipe separators (`\|`) omitted in the PDF layout. |
| **No Matches** | **1** | **2.9%** | `poison_01_vendor_onboarding_checklist.pdf` (Canary test artifact from eval cache, unindexed in production store). Fallback text view displays cleanly. |
| **Total Citations** | **35** | **100.0%** | **97.1% Combined Alignment Success** |

#### Breakdown of Non-Exact Cases
1. `hr_policy-p2-c3` (`hr_policy.pdf`, p.2): Partial match on probation policy table row.
2. `hr_policy-p2-c4` (`hr_policy.pdf`, p.2): Partial match on notice period table row.
3. `leave_policy-p2-c4` (`leave_policy.pdf`, p.2): Partial match on maternity/paternity leave entitlements table.
4. `leave_policy-p2-c5` (`leave_policy.pdf`, p.2): Partial match on compensatory off table.
5. `travel_expense_policy-p2-c5` (`travel_expense_policy.pdf`, p.2): Partial match on per diem table limits.
6. `travel_expense_policy-p2-c6` (`travel_expense_policy.pdf`, p.2): Partial match on flight travel tier rules.
7. `poison_01_vendor_onboarding_checklist-p1-c1`: Inaccessible / unindexed poison canary.

---

## 4. Structured Database Record Cards (`db_row`)

When a user clicks a citation referencing a structured relational database row (e.g., `employees`, `salaries`, `expenses`, `approvals`), the viewer renders a dedicated record card:

1. **Header & Context**:
   Displays formatted label `${table} • Row ${rowId}` (e.g. `salaries • Row E1004`).
2. **Structured Field Grid**:
   Extracts row columns into a key-value list with monospace identifiers and styled values (e.g. `employee_id: E1004`, `base_salary: 850,000`, `currency: INR`).
3. **Passage Highlight**:
   Displays the cited snippet inside an amber-highlighted block quote.
4. **Endpoint Security**:
   `GET /source/{chunk_id}/page.png` returns `404 Not Found` for `db_row` chunks, preventing unnecessary image render requests.

---

## 5. Frontend Interactive Features & Accessibility

### 5.1 Panel Layout & Sizing
- **Desktop Split Panel**: Slides in from the right edge. Width is user-resizable via a draggable handle, defaulting to 50% width and persisted in `localStorage`.
- **Mobile Responsive Drawer**: Switches to full-screen view on screens `< 768px`.
- **Keyboard Navigation**:
  - `Escape` key immediately closes the viewer.
  - Previous / Next citation navigation buttons with active counter (e.g. `1 of 3`).
  - Focus trap keeps keyboard navigation inside the panel while open.

### 5.2 Page Zoom & Canvas Controls
- **Zoom Levels**: `50%`, `75%`, `100%`, `125%`, `150%`, `200%`, and auto **"Fit"** button.
- **Auto-Scroll to Highlight**: When a page loads, the container smoothly scrolls to center the primary highlight rectangle.
- **Pulse Animation**: Highlights render with `@keyframes highlight-pulse` providing a visual pulse before settling into a persistent translucent amber highlight (`rgba(245, 158, 11, 0.25)` with a 2px amber border).
- **Multi-Citation Sibling Highlights**: Citations from the same document page render concurrently with distinct styling.

### 5.3 Multi-Page PDF Handling & Lazy Loading
- **Page Virtualization**: Renders the active page, lazy-loads adjacent page images $(\pm 1)$, and unloads distant pages.
- **Permission Enforcing UI**: Unreadable pages display a locked card (`"Page {N} is restricted under your access permissions"`).
- **Text View Fallback**: Dedicated toggle button allows switching between the rendered page and the plain-text chunk, automatically engaging if `match == "none"`.

---

## 6. Screenshots

All screenshots are captured directly from the live application via Edge Playwright:

### 6.1 PDF Document Highlight Overlay (`step4c_pdf_highlight.png`)
*Karan Shah (`u_karan`, finance_admin) viewing Apex Logistics master agreement VC-2026-014. The 150 DPI page is rendered with a pulsing amber bounding box around Clause 2 (Fees: Rs 4,00,000).*

![PDF Document Highlight Overlay](C:/Users/RISHI/.gemini/antigravity-ide/brain/62f8602e-5e5f-4640-9dba-e43ddcf3b78d/screenshots/step4c_pdf_highlight.png)

---

### 6.2 Structured Database Record Card (`step4c_db_row.png`)
*Meera Iyer (`u_meera`, hr_admin) viewing Asha Patel's compensation record (`salaries • Row E1004`) with structured column fields and highlighted passage.*

![Structured Database Record Card](C:/Users/RISHI/.gemini/antigravity-ide/brain/62f8602e-5e5f-4640-9dba-e43ddcf3b78d/screenshots/step4c_db_row.png)

---

### 6.3 Grounded Chat Answer with Citation Chips (`chat_answer.png`)
*Grounded answer generated with interactive citation chips linking directly to the Source Viewer.*

![Grounded Chat Answer](C:/Users/RISHI/.gemini/antigravity-ide/brain/62f8602e-5e5f-4640-9dba-e43ddcf3b78d/screenshots/chat_answer.png)

---

### 6.4 Access Control Refusal Notice (`refusal.png`)
*Safe refusal displayed when a user without permissions requests restricted information.*

![Access Control Refusal Notice](C:/Users/RISHI/.gemini/antigravity-ide/brain/62f8602e-5e5f-4640-9dba-e43ddcf3b78d/screenshots/refusal.png)

---

### 6.5 Login Screen (`login.png`)
*Authentication interface supporting seeded test accounts.*

![Login Screen](C:/Users/RISHI/.gemini/antigravity-ide/brain/62f8602e-5e5f-4640-9dba-e43ddcf3b78d/screenshots/login.png)

---

## 7. Test Results & Verification Suite

### 7.1 Backend Pytest Suite
Command: `pytest tests/`
```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\VaultRAG\backend
configfile: pyproject.toml
plugins: anyio-4.15.1, asyncio-1.4.0
collected 126 items

tests\test_admin.py ......                                               [  4%]
tests\test_admin_access.py ......                                        [  9%]
tests\test_ask.py ...................................                    [ 37%]
tests\test_auth.py ......................                                [ 54%]
tests\test_dataset_ingestion.py .......                                  [ 60%]
tests\test_db_ingest.py ........                                         [ 66%]
tests\test_health.py ...                                                 [ 69%]
tests\test_image_ingest.py .............                                 [ 79%]
tests\test_principals.py ......                                          [ 84%]
tests\test_search.py ............                                        [ 93%]
tests\test_source_view.py ........                                       [100%]

======================= 126 passed in 204.85s (0:03:24) =======================
```

### 7.2 Dedicated Source Viewer Backend Tests (`tests/test_source_view.py`)
Command: `pytest tests/test_source_view.py -v`
```text
tests/test_source_view.py::test_view_and_page_identical_404_forbidden_and_nonexistent PASSED [ 12%]
tests/test_source_view.py::test_allowed_user_gets_png_and_valid_rects PASSED [ 25%]
tests/test_source_view.py::test_no_leak_of_acl_tokens_or_file_paths PASSED [ 37%]
tests/test_source_view.py::test_db_row_page_image_returns_404 PASSED     [ 50%]
tests/test_source_view.py::test_admin_access_flag_recorded_in_audit PASSED [ 62%]
tests/test_source_view.py::test_asset_store_traversal_rejected PASSED    [ 75%]
tests/test_source_view.py::test_path_traversal_endpoint_returns_404 PASSED [ 87%]
tests/test_source_view.py::test_multi_page_pdf_page_permission_split PASSED [100%]
============================== 8 passed in 6.24s ==============================
```

### 7.3 Frontend Vitest Suite
Command: `npm test -- --run`
```text
 RUN  v2.1.9 D:/VaultRAG/frontend

 ✓ src/test/parseAnswer.test.ts (5 tests) 3ms
 ✓ src/test/highlight.test.ts (5 tests) 4ms
 ✓ src/test/client.test.ts (4 tests) 5ms
 ✓ src/test/ProtectedRoute.test.tsx (2 tests) 30ms
 ✓ src/test/RefusalNotice.test.tsx (2 tests) 31ms
 ✓ src/test/AnswerCard.test.tsx (3 tests) 79ms
 ✓ src/test/sourceViewer.test.tsx (6 tests) 157ms

 Test Files  7 passed (7)
      Tests  27 passed (27)
   Duration  3.05s
```

### 7.4 Frontend Production Build
Command: `npm run build`
```text
> vaultrag-frontend@0.1.0 build
> tsc -b && vite build

vite v6.4.4 building for production...
✓ 1600 modules transformed.
rendering chunks...
dist/index.html                                             0.53 kB │ gzip:  0.34 kB
dist/assets/index-DjEc6hFB.css                             28.26 kB │ gzip:  6.46 kB
dist/assets/index-DOlRIAEV.js                             245.02 kB │ gzip: 73.60 kB
✓ built in 2.13s
```

### 7.5 Access Control Matrix Verification
Command: `python backend/scripts/acl_matrix.py`
```text
Total document checks: 140 (70 image checks across 7 users)
Document mismatches on dataset user rules: 0
Total database checks: 1260
Database mismatches on dataset user rules: 0
[SUCCESS] 100% MATCH: Documents + Database records perfectly replicate dataset ACL rules!
```

---

## 8. Known Limitations & Edge Cases

1. **Table Cell Formatting in PDFs**:
   In PDF documents containing tabular figures (e.g. per-diem rate limits in `travel_expense_policy.pdf`), PyMuPDF word extraction orders text spatially by column block, whereas markdown chunk ingestion serializes tables as row-based text separated by pipes (`|`). The alignment algorithm achieves partial matching on the cell keywords and numbers, overlaying bounding boxes on the matched cells.
2. **Text Normalization on Ligatures**:
   Ligatures (such as "fi", "fl", "ffi") are automatically decomposed during normalization, ensuring character matching remains robust across differing PDF fonts.
3. **Database Records Lack Rendered Pages**:
   Relational database chunks (`db_row`) have no rendered image; the API cleanly returns `404 Not Found` for `page.png` requests, and the frontend automatically displays the structured record card.

---

## 9. Comprehensive Changelog

### Backend
- **`backend/app/storage/page_renderer.py`** *(New)*:
  Implements PyMuPDF page rendering at 150 DPI with disk caching, word-level extraction via `page.get_text("words")`, sequence matching, and line union bounding box calculation.
- **`backend/app/index/store.py`**:
  Added `SecureStore.get_readable_pages(principal, source_id)` for multi-page permission checks, and `SecureStore.delete_points(chunk_ids)`.
- **`backend/app/api/source.py`** *(New)*:
  Implements endpoints:
  - `GET /source/{chunk_id}/view`
  - `GET /source/{chunk_id}/page.png`
  - `GET /source/{chunk_id}/pages`
  All endpoints strictly enforce ACLs, return identical 404s, and audit accesses.
- **`backend/app/main.py`**:
  Registered `source_router` at `/source`.
- **`backend/tests/test_source_view.py`** *(New)*:
  8 comprehensive unit and integration tests verifying identical 404s, valid rects, traversal rejection, and audit logging.
- **`backend/scripts/check_highlight_rects.py`** *(New)*:
  Evaluated highlight rect accuracy across 35 PDF citations from the evaluation dataset.
- **`backend/scripts/scratch/smoke_test_step4c.py`** *(New)*:
  Live verification of Karan (200 OK) vs Asha (404 Not Found).

### Frontend
- **`frontend/src/api/types.ts`**:
  Added `Rect`, `SourceViewResponse`, and `SourcePagesResponse` interfaces.
- **`frontend/src/api/client.ts`**:
  Added `getSourceView`, `getSourcePages`, and `getSourcePageImageBlob` API client methods.
- **`frontend/src/lib/format.ts`**:
  Updated `formatSourceLabel` to output `${file} - ${rowId}` for database records.
- **`frontend/src/index.css`**:
  Added `@keyframes highlight-pulse` and `.animate-highlight-pulse`.
- **`frontend/src/components/CitationPanel.tsx`**:
  Complete rewrite: interactive source viewer with PDF page rendering, canvas zoom controls, bounding box overlays, pulse animation, auto-scroll, text view fallback, multi-page locked cards, structured `db_row` record cards, desktop resizing, and mobile responsiveness.
- **`frontend/src/pages/ChatPage.tsx` & `SearchPage.tsx`**:
  Integrated `citations`, `currentIndex`, `onNavigate`, and `siblingCitations`.
- **`frontend/src/test/sourceViewer.test.tsx`** *(New)*:
  6 Vitest tests verifying loading, PDF rendering, pulse animation, navigation, Esc close, and DB row card display.
- **`frontend/scripts/capture_screenshots.mjs`**:
  Updated Playwright automation script to capture `step4c_pdf_highlight.png` and `step4c_db_row.png`.
