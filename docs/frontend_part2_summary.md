# VaultRAG Frontend Part 2 Summary: Document Upload, Sharing & Admin Dashboard

**Project**: VaultRAG (Enterprise Secure RAG)  
**Scope**: Frontend Part 2 (Document Upload, Sharing, and Admin Monitoring)  
**Stack**: React 18 + Vite + TypeScript (strict) + Tailwind CSS + Lucide Icons  
**Date**: October 9, 2026  
**Status**: All requirements implemented, verified, built, and tested green.

---

## 1. Screens & Capabilities Overview

### 1.1 My Documents (`/documents`)
- **Navigation**: New sidebar navigation link `My Documents` with `Files` icon.
- **Two Tabs**:
  - `My uploads` (`scope=mine`): Shows all documents uploaded by the current user.
  - `Shared with me` (`scope=shared`): Shows documents explicitly shared with the current user or their role/department.
- **Table & Responsive Cards**:
  - Desktop view: Semantic HTML `<table>` with headers: File Name, Size, Uploaded, Status, Sharing/Owner, and Actions.
  - Mobile view: Compact card layout with file icon, metadata badges, and responsive action icon buttons.
  - Plain-text rendering only (zero `dangerouslySetInnerHTML`) to prevent XSS.
- **Status Chips**:
  - `Ready`: Emerald pill with checkmark.
  - `Processing`: Amber pill with animated spinner.
  - `Queued`: Blue pill with clock icon.
  - `Failed`: Red pill showing neutral reason code (e.g., `extraction_failed`).
- **Auto-Refresh Polling**:
  - Automatically polls `/documents` every 2,000 ms while any document is `queued` or `processing`.
  - Automatically stops polling when all documents are `ready` or `failed`.
- **Upload Zone & Client Validation**:
  - Drag-and-drop zone + native file browser button.
  - Allowed extensions validated: `pdf, png, jpg, jpeg, csv, txt, md`.
  - Size limit enforced: ≤ 20 MB (`20 * 1024 * 1024` bytes, matching backend setting).
  - CSV Client-Side Header Parsing: For CSV files, uses `FileReader.readAsText()` on the first 8 KB to extract column headers without uploading the whole file. Shows checkbox list: *"Mark as sensitive (only you and admins will see these columns)"*.
  - Upload Progress: Uses `XMLHttpRequest.upload.onprogress` to display real-time percentage progress bar (0–100%).
  - In-flight Cancel: Dedicated `Cancel` button triggers `xhr.abort()`.
  - Duplicate detection: Server status 200 displays *"You already uploaded this file."*
  - Error handling: Displays user-friendly messages for 403, 413, 415, 422, 429, 503, and network failures.
- **Row Actions**:
  - **Ask**: Navigates to `/chat` with state `{ source_ids: [doc.id], source_filename: doc.filename }`. Displays removable chip *"Asking only about: <filename>"* and passes `source_ids` to `/ask`.
  - **Open**: Opens verified citation viewer slide-over (`CitationPanel`) at page 1 using chunk `upl:<id>#0`.
  - **Share**: Opens accessible `ShareDialog` (restricted to document owner or platform administrator).
  - **Delete**: Confirmation modal stating: *"This document will be permanently removed for you and everyone it was shared with."* Upon 204 response, the row disappears immediately.

---

### 1.2 Share Dialog (`<ShareDialog />`)
- **Security Statement**: Top banner reads: *"Only you and platform administrators can see this document until you share it."*
- **Three Add-Access Tabs**:
  - **People**: Search input calling `/sharing/targets?q=` debounced at 300 ms (min 2 chars) with accessible keyboard-navigable autocomplete list.
  - **Roles**: Select dropdown populated from available tenant roles (`admin`, `finance_admin`, `hr_admin`, `legal_admin`, `engineer`, `employee`, etc.).
  - **Departments**: Select dropdown populated from available departments (`Executive`, `Finance`, `HR`, `Legal`, `Engineering`, `Sales`).
- **Sensitive Columns Option**: For CSV files, displays checkbox: *"Also share sensitive columns"*, default unchecked.
- **Current Access List**:
  - Displays owner as permanent non-removable entry.
  - Displays each active grantee with type icon (user, role, or department) and sensitive flag badge.
  - Individual `Remove` buttons trigger `DELETE /documents/{id}/shares/{share_id}`.
  - Immediate visual feedback: Shows *"Shared with <name>"* on addition, *"Access removed"* on deletion.
  - Strict zero-leak rule: Never displays or stores internal `acl_tokens` in DOM or storage.
- **Neutral Error Handling**: 403 or 404 responses render neutral message: *"You can't manage sharing for this document."*

---

### 1.3 Admin Dashboard (`/admin`) & Admin Route Guard
- **Strict Role-Based Routing**:
  - Sidebar link `Admin Dashboard` is visible only when `user.roles.includes('admin')`.
  - Route guarded by `<AdminRouteGuard>`. Any non-admin navigating to `/admin` receives the exact same neutral 404 *"Page not found"* page as non-existent routes. The backend enforces 403 independently.
- **Top KPI Metric Tiles**:
  - Period selector: `1 day`, `7 days`, `30 days` calling `GET /admin/audit/summary?days=N`.
  - Total Asks (+ total searches count).
  - Refusal Rate (percentage + refused query count).
  - Average Latency (ms).
  - P95 Latency (ms).
  - Total Uploads (files ingested).
  - Active Users in selected period.
- **Zero-Dependency SVG Activity Chart**:
  - Clean inline SVG chart plotting daily Asks line (blue) with Refusals overlay (red dashed line).
  - Fully accessible table view fallback toggle (`Show accessible table view`) with semantic table headers.
- **Breakdown Sections**:
  - `Top Active Users`: Ranked list with user names and query counts.
  - `Refusals by Reason Code`: Distribution of refusals by reason (e.g., `no_relevant_context`, `acl_denied`, `output_guard`).
- **Recent Queries Audit Table**:
  - Columns: Time, User, Event (`ask`/`search`), Outcome (`Answered`/`Refused`), Reason Code, Latency, Chunks, Admin Access flag, Question Hash & Length.
  - Zero Text Leaks: Never displays or requests raw question text or answer text.
  - Filters: Outcome filter (`All`, `Answered`, `Refused`) and Event filter (`All`, `ask`, `search`).
  - Cursor Pagination: `Load more` button fetching older logs via `before=<timestamp>`.
- **Uploads Audit Table**:
  - Platform-wide document inventory: File Name, Owner, Kind, Size, Status, Shared Count, Deleted flag, and Upload Date.
- **Real-Time Controls**:
  - Manual `Refresh` button.
  - `Auto-refresh (10s)` toggle button for unattended operations monitoring.

---

### 1.4 Chat & Search Document Filter Integration
- When navigating from "Ask about this document", `/chat` mounts a removable filter chip above the composer:
  `Asking only about: <filename>` with an `(X)` clear button.
- All `/ask` requests include `source_ids: [selectedDocId]`.
- Clearing the chip returns the chat session to full corpus querying.
- Demo user switching immediately resets active document filters, conversations, and cache.

---

## 2. Backend Endpoint Usage & Mapping

| Endpoint | Method | Frontend Caller | Payload / Query | Response / Handling |
|---|---|---|---|---|
| `/documents` | `POST` | `api.uploadDocument` | Multipart `FormData` (`file`, `sensitive_columns`) | `202 Accepted` (`{ id, status }`) or `200` duplicate; tracks progress via XHR; abortable |
| `/documents` | `GET` | `api.listDocuments` | `?scope=mine\|shared\|all` | Array of `DocumentItem`; auto-polled every 2s while queued/processing |
| `/documents/{id}` | `GET` | `api.getDocument` | Path `id` | `DocumentDetail` (`status`, `chunk_count`, `can_manage`) |
| `/documents/{id}` | `DELETE` | `api.deleteDocument` | Path `id` | `204 No Content`; immediately removes row from UI |
| `/documents/{id}/shares` | `GET` | `api.getDocumentShares` | Path `id` | Array of `DocumentShare` (`grantee_type`, `grantee_value`, `include_sensitive`) |
| `/documents/{id}/shares` | `POST` | `api.createDocumentShare`| `{ grantee_type, value, include_sensitive }` | `201 Created`; adds to active access list |
| `/documents/{id}/shares/{share_id}` | `DELETE` | `api.deleteDocumentShare` | Path `id`, `share_id` | `204 No Content`; removes grantee immediately |
| `/sharing/targets` | `GET` | `api.getSharingTargets` | `?q=` (debounced 300 ms) | `{ users: [...], roles: [...], departments: [...] }` |
| `/admin/audit/summary` | `GET` | `api.getAdminAuditSummary` | `?days=1\|7\|30` | `AuditSummary` (`totals`, `per_day_series`, `counts_by_reason_code`, `top_users`) |
| `/admin/queries` | `GET` | `api.getAdminQueries` | `?limit=50&before=<iso>` | Array of `AdminQueryLog`; cursor pagination |
| `/admin/uploads` | `GET` | `api.getAdminUploads` | None | Array of `AdminUploadItem` (active + deleted) |
| `/ask` | `POST` | `api.ask` | `{ question, top_k, source_ids }` | Answer + citations filtered by allowed document |
| `/search` | `POST` | `api.search` | `{ query, top_k, rerank, source_ids }` | Retrieval results filtered by allowed document |

---

## 3. UI State Handling Table

| State / Condition | User Experience / Visual State | Error Handling / Recovery |
|---|---|---|
| **File Drag & Drop** | Dashed dropzone highlights in accent color with subtle background tint | Rejects disallowed extensions before upload attempt |
| **Invalid File Type** | Error alert: *"Unsupported file type. Allowed: PDF, PNG, JPG, JPEG, CSV, TXT, MD"* | Upload button disabled; file input cleared |
| **File > 20 MB** | Error alert: *"File exceeds maximum upload size (20 MB)"* | File not uploaded; user prompted to choose smaller file |
| **CSV Upload** | Reads header row in memory; displays grid of column checkboxes | User selects which columns to restrict to self + admins |
| **Upload in Progress** | Linear progress bar (0–100%) with percentage text and Cancel button | Clicking Cancel invokes `xhr.abort()`; displays *"Upload cancelled."* |
| **Duplicate Upload** | Status 200 response | Inline notice: *"You already uploaded this file."* |
| **Ingestion Queued** | Blue badge `Queued`; auto-refresh timer active | 2s polling monitors state transition |
| **Ingestion Processing**| Amber badge `Processing` with animated spinner | 2s polling monitors background worker completion |
| **Ingestion Ready** | Green badge `Ready` with checkmark icon | "Ask", "Open", "Share", and "Delete" buttons become active |
| **Ingestion Failed** | Red badge `Failed: <reason_code>` | Displays neutral failure reason code |
| **Non-Admin on `/admin`** | Neutral *"Page not found"* page (identical to 404 routes) | No clue given that `/admin` exists; backend enforces 403 independently |
| **Share Autocomplete** | Debounced 300ms autocomplete with spinner | Min 2 chars enforced; handles empty results cleanly |
| **Share Forbidden/404**| Modal alert: *"You can't manage sharing for this document."* | Share form disabled |
| **Document Deletion** | Confirmation dialog with clear scope warning | On confirm, calls `DELETE /documents/{id}` and removes row |
| **Demo User Switch** | Clears conversation messages, active source filters, and document lists | Immediate re-fetch under newly selected demo identity |

---

## 4. Test Verification & Real Command Outputs

### 4.1 TypeScript Compiler (`tsc -b`)
```
> vaultrag-frontend@0.1.0 typecheck
> tsc -b
[Process completed with exit code 0]
```

### 4.2 Vitest / React Testing Library (`npm test`)
```
> vaultrag-frontend@0.1.0 test
> vitest run

 RUN  v2.1.9 D:/VaultRAG/frontend

 ✓ src/test/parseAnswer.test.ts (5 tests) 4ms
 ✓ src/test/highlight.test.ts (5 tests) 6ms
 ✓ src/test/client.test.ts (4 tests) 7ms
 ✓ src/test/RefusalNotice.test.tsx (2 tests) 35ms
 ✓ src/test/ProtectedRoute.test.tsx (2 tests) 34ms
 ✓ src/test/AnswerCard.test.tsx (3 tests) 125ms
 ✓ src/test/sourceViewer.test.tsx (6 tests) 255ms
 ✓ src/test/adminDashboard.test.tsx (4 tests) 338ms
 ✓ src/test/documents.test.tsx (7 tests) 376ms
 ✓ src/test/shareDialog.test.tsx (4 tests) 589ms

 Test Files  10 passed (10)
      Tests  42 passed (42)
   Duration  3.70s
```

### 4.3 Vite Production Bundle (`npm run build`)
```
> vaultrag-frontend@0.1.0 build
> tsc -b && vite build

vite v6.4.4 building for production...
transforming...
✓ 1605 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                             0.53 kB │ gzip:  0.34 kB
dist/assets/index-BcY-S3F7.css                             32.29 kB │ gzip:  7.09 kB
dist/assets/index-C6ZSlToe.js                             315.32 kB │ gzip: 86.87 kB
✓ built in 2.43s
```

### 4.4 Live Backend Smoke Test (`node scripts/smoke_test.mjs`)
```
Starting VaultRAG smoke test against http://127.0.0.1:8000...

--- 1. Health & CORS Check ---
Status: 200
CORS Access-Control-Allow-Origin: http://localhost:5173
Health: {"postgres":{"status":"ok"},"qdrant":{"status":"ok"},"llm":{"status":"ok","models":["qwen2.5:3b","qwen2.5:7b"]}}

--- 2. Login as u_karan ---
u_karan logged in successfully. Token received (length 248).
u_karan profile: {"id":"6c43cfdf-f63f-4792-98ce-53156a8a79ba","name":"Karan Shah","email":"karan.shah@northwind.example","roles":["finance_admin"],"employee_id":"E1002","department":"Finance","external_id":"u_karan"}

--- 3. Ask Apex Monthly Fee as u_karan ---
u_karan Ask response:
- Refused: false
- Answer: The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only) [1].
- Verified: true
- Citations count: 1

--- 4. Fetch First Citation: vendor_contract_apex-p1-c1 ---
Citation fetched successfully:
- File: vendor_contract_apex.pdf, Page: 1
- Highlights from /ask citation: [{"start":437,"end":590}]
- Highlight text from /ask citation: "2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%."

--- 5. Login as u_asha ---
u_asha logged in successfully. Token received.

--- 6. Ask Apex Monthly Fee as u_asha (Refusal Expected) ---
u_asha Ask response:
- Refused: true
- Answer: I couldn't find an answer to that in the documents available to you.
- Citations: []

--- 7. Request Nonexistent Citation ---
Nonexistent citation status: 404

--- 8. Asha Uploads Generated PDF ---
Document uploaded with id: 8aa57b58-f4e2-44ae-adfd-70e62aa22f01, initial status: queued
Waiting for document to reach ready state...
Document reached ready state in 1000ms!

--- 9. Asha Asks About Uploaded Document ---
Asha answer: The secret budget for Project Falcon code mv18iron is 450,000 USD [1].
Asha refused: false
Asha citations count: 1

--- 10. Login as Neha & Verify Access Denied Before Share ---
Neha user profile: id=50ecd387-e000-49a1-b3bd-940502dd3f0a, name=Neha Desai
Neha before share refused: true
Verified doc 8aa57b58-f4e2-44ae-adfd-70e62aa22f01 is not visible to Neha.

--- 11. Asha Shares Document with Neha ---
Document successfully shared with Neha. Share ID: 48253a70-917a-4c19-8d7b-aabef8093d97

--- 12. Neha Asks About Document After Share ---
Neha after share refused: false
Neha answer: The secret budget for Project Falcon code mv18iron is 450,000 USD [1].

--- 13. Asha Revokes Sharing ---
Share 48253a70-917a-4c19-8d7b-aabef8093d97 revoked successfully.

--- 14. Neha Asks Again After Revocation (Refusal Expected) ---
Neha after revoke refused: true

--- 15. Asha Deletes Document ---
Document 8aa57b58-f4e2-44ae-adfd-70e62aa22f01 deleted successfully.
Confirmed 404 on deleted document.

--- 16. Admin Monitoring & Audit Summary ---
Admin audit summary retrieved:
- Total asks: 97
- Total searches: 7
- Refusal rate: 56.7%
- Avg latency: 3518.9 ms
- P95 latency: 13927.9 ms
- Uploads: 110
- Active users: 9
- Per day series count: 2
Admin queries count: 10
Admin uploads audit count: 9

========================================
ALL FRONTEND PART 2 SMOKE TEST CHECKS PASSED!
========================================
```

---

## 5. Verified Screenshots

All screenshots were captured using Microsoft Edge via `scripts/capture_screenshots.mjs` and saved to `docs/screenshots/`:

1. `login.png` — Authentication login screen with quick demo-user chips.
2. `chat_answer.png` — Question answered with citation chip `[1]` and verified status.
3. `step4c_pdf_highlight.png` / `citation_panel.png` — Interactive PDF source viewer showing highlighted bounding boxes on page 1.
4. `step4c_db_row.png` — Citation panel showing formatted DB row fields for structured database records.
5. `refusal.png` — Security refusal banner (*"I couldn't find an answer to that in the documents available to you"*).
6. `my_documents.png` — My Documents screen with drag-and-drop upload zone, sensitive column controls, and table of uploads with Ready status chips.
7. `share_dialog.png` — Accessible Share modal with People search, Roles/Departments tabs, and Current Access list.
8. `admin_dashboard.png` — Platform Admin dashboard with 6 KPI tiles, inline SVG daily activity chart, recent queries audit log table, and uploads audit table.

---

## 6. Known Gaps & Future Enhancements

- **CSV In-Browser Multi-Page Pagination**: Currently CSV header detection reads the first 8 KB chunk to extract column names; large CSV previews in the source viewer display chunk text rather than a paginated interactive data grid.
- **WebSocket Progress Updates**: Upload progress uses standard XHR progress events; background worker status is polled every 2s via HTTP GET rather than WebSockets or SSE.
- **Batch Document Actions**: Documents are currently deleted and shared individually; batch selection can be added in a future enhancement.

---

## 7. How to Run & Verify

```bash
# 1. Typecheck the entire frontend
cd d:\VaultRAG\frontend
npm run typecheck

# 2. Run unit and integration test suite
npm test

# 3. Build production bundle
npm run build

# 4. Run live backend smoke test
node scripts/smoke_test.mjs

# 5. Capture all UI screenshots
node scripts/capture_screenshots.mjs
```
