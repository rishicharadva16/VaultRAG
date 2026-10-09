# VaultRAG Frontend Part 1 Summary

## 1. Confirmed Backend API Endpoint Shapes

Inspected directly from FastAPI backend code (`app/api/*.py`, schemas, and live OpenAPI spec):

| Endpoint | Method | Request Shape | Response Shape | Auth Required |
|---|---|---|---|---|
| `/auth/login` | `POST` | JSON: `{"email": "string", "password": "string"}` (Note: standard JSON, not OAuth2 form data) | `{"access_token": "string", "token_type": "bearer"}` | No |
| `/auth/me` | `GET` | Header: `Authorization: Bearer <token>` | `{"id": "uuid", "name": "string", "email": "string", "roles": ["string"], "employee_id": "string\|null", "department": "string\|null", "external_id": "string\|null"}` | Yes |
| `/ask` | `POST` | Header: `Authorization: Bearer <token>`<br>JSON: `{"question": "string"}` | `{"answer": "string", "refused": boolean, "verified": boolean, "citations": [{"id": int, "chunk_id": "string", "source_id": "string", "file": "string", "page": int\|null, "row_id": "string\|null", "snippet": "string", "highlights": [{"start": int, "end": int}], "highlight_text": "string"}]}` | Yes |
| `/search` | `POST` | Header: `Authorization: Bearer <token>`<br>JSON: `{"query": "string", "top_k": int (def 5), "rerank": boolean (def true)}` | `{"query": "string", "latency_ms": float, "results": [{"chunk_id": "string", "source_id": "string", "file": "string", "page": int\|null, "text": "string", "score": float, "rerank_score": float, "rank": int}]}` | Yes |
| `/citation/{chunk_id}` | `GET` | Header: `Authorization: Bearer <token>`<br>Path: `chunk_id` (URL-encoded to handle `#` in database IDs like `db:salaries#E1004:base`) | `{"chunk_id": "string", "source_id": "string", "file": "string", "page": int\|null, "text": "string"}` (or 404 `{"detail": "Source chunk not found"}`) | Yes |
| `/health` | `GET` | None | `{"postgres": {"status": "ok"}, "qdrant": {"status": "ok"}, "llm": {"status": "ok", "models": ["qwen2.5:3b", "qwen2.5:7b"]}}` | No |

---

## 2. Frontend Project Structure

```
D:\VaultRAG\frontend
├── .env
├── .env.example
├── .gitignore
├── index.html
├── package.json
├── postcss.config.js
├── tailwind.config.js
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── vite.config.ts
├── docs/
│   └── screenshots/
│       ├── chat_answer.png
│       ├── citation_panel.png
│       ├── login.png
│       └── refusal.png
├── scripts/
│   ├── capture_screenshots.mjs
│   └── smoke_test.mjs
└── src/
    ├── App.tsx
    ├── main.tsx
    ├── api/
    │   ├── client.ts
    │   └── types.ts
    ├── auth/
    │   ├── AuthContext.tsx
    │   └── ProtectedRoute.tsx
    ├── components/
    │   ├── AnswerCard.tsx
    │   ├── AppShell.tsx
    │   ├── CitationChip.tsx
    │   ├── CitationPanel.tsx
    │   ├── Composer.tsx
    │   ├── EmptyState.tsx
    │   ├── ErrorBanner.tsx
    │   ├── HighlightedText.tsx
    │   ├── MessageList.tsx
    │   ├── RefusalNotice.tsx
    │   ├── RoleBadge.tsx
    │   ├── Sidebar.tsx
    │   ├── Skeleton.tsx
    │   ├── ThemeToggle.tsx
    │   └── UserCard.tsx
    ├── lib/
    │   ├── format.ts
    │   ├── highlight.ts
    │   └── parseAnswer.ts
    ├── pages/
    │   ├── ChatPage.tsx
    │   ├── LoginPage.tsx
    │   └── SearchPage.tsx
    ├── styles/
    │   └── tokens.css
    └── test/
        ├── AnswerCard.test.tsx
        ├── ProtectedRoute.test.tsx
        ├── RefusalNotice.test.tsx
        ├── client.test.ts
        ├── highlight.test.ts
        ├── parseAnswer.test.ts
        └── setup.ts
```

---

## 3. Design Tokens & Accessibility

Implemented in `src/styles/tokens.css` with CSS variables and mapped into `tailwind.config.js`:

| Token | Light Theme Value | Dark Theme Value | Purpose & Contrast |
|---|---|---|---|
| `--color-bg` | `#f8fafc` (slate-50) | `#0b0f17` (rich dark slate) | Page background |
| `--color-surface` | `#ffffff` (pure white) | `#131b26` (elevated dark navy) | Card & container surface |
| `--color-surface-raised` | `#f1f5f9` (slate-100) | `#1b2636` (raised navy) | Headers, chips, panels |
| `--color-border` | `#e2e8f0` (slate-200) | `#233247` (subtle dark line) | Structural borders |
| `--color-text` | `#0f172a` (slate-900) | `#f1f5f9` (slate-100) | Primary text (>= 12:1 contrast ratio) |
| `--color-text-muted` | `#475569` (slate-600) | `#94a3b8` (slate-400) | Secondary text (>= 4.5:1 WCAG AA) |
| `--color-accent` | `#0284c7` (sky-600) | `#38bdf8` (sky-400) | Primary interactive actions |
| `--color-accent-contrast` | `#ffffff` | `#0b0f17` | Text on top of accent buttons |
| `--color-highlight` | `#fef08a` (amber-200, 80% opacity) | `#ca8a04` (amber-600, 45% opacity) | Highlighted cited spans |
| `--color-success` | `#16a34a` (green-600) | `#4ade80` (green-400) | Verified badges, success alerts |
| `--color-warning` | `#d97706` (amber-600) | `#fbbf24` (amber-400) | Warning indicators |
| `--color-danger` | `#dc2626` (red-600) | `#f87171` (red-400) | Error banners, session expirations |
| `--color-focus-ring` | `#0284c7` (2px outline) | `#38bdf8` (2px outline) | Accessible keyboard focus rings |

- **Typography**: Inter (via `@fontsource/inter` bundle; no CDN links). Scale: 12, 14 (body, line-height 1.5), 16, 20, 24, 32 px.
- **Grid & Radii**: 4 px grid; 8 px for cards, 6 px for buttons/inputs, full pill for role badges.
- **Theme Support**: Default matches `prefers-color-scheme`, persisted toggle in `localStorage`.
- **Untrusted Plain Text Rule**: Model answers are strictly parsed and rendered as plain text nodes plus `CitationChip` buttons. `dangerouslySetInnerHTML` is never used.

---

## 4. State Handling Matrix

| State / Code | Component Used | User Presentation & Behavior |
|---|---|---|
| **Loading (Chat)** | `Skeleton`, `Composer` | Displays a pulsing skeleton card with `"Searching your documents..."` and an elapsed timer (`Xs elapsed`). Composer Send is disabled; Stop button cancels the request via `AbortController`. Auto-aborts after 130 s with: `"The AI service took too long. Please try again."` |
| **Loading (Citation)**| `CitationPanel`, `Skeleton` | Header opens immediately with file and page/row; body displays a 5-bar shimmer skeleton with `"Fetching verified chunk text..."`. |
| **Refusal** | `RefusalNotice` | Neutral styled container (neither red nor green) with an info icon, displaying the exact API refusal message: `"I couldn't find an answer to that in the documents available to you."` followed by the static note: `"Answers come only from documents available to you."` Indistinguishable across different document denial reasons. |
| **401 Unauthorized**| `ErrorBanner`, `AuthContext` | Clears in-memory and `sessionStorage` tokens, redirects to `/login` with an amber alert banner: `"Your session expired. Please sign in again."` |
| **422 Validation** | `ErrorBanner` | Distinct rose/red alert card: `"Invalid input. Please check your request."` with a **Retry** button. |
| **429 Rate Limit** | `ErrorBanner` | Distinct rose/red alert card: `"You are asking too quickly. Wait a moment and try again."` with a **Retry** button. |
| **503 Unavailable**| `ErrorBanner` | Distinct rose/red alert card: `"The AI service is busy or unavailable. Try again shortly."` with a **Retry** button. |
| **Network Error** | `ErrorBanner` | Distinct rose/red alert card: `"Cannot reach the VaultRAG server. Is the backend running?"` with a **Retry** button. |
| **404 Citation** | `CitationPanel` | Body shows an alert box with: `"This source is no longer available."` (identical for all missing or purged chunks). |

---

## 5. Verification & Test Results

### Automated Test Suite Summary

| Check / Suite | Tool | Result | Details |
|---|---|---|---|
| TypeScript Typecheck | `tsc -b` | **PASS** | 0 errors across all frontend files |
| Unit & Component Tests | `vitest run` | **PASS (21/21)** | 6 test files, 100% pass in 2.42s |
| Production Bundle Build | `vite build` | **PASS** | HTML, CSS (26.28 kB), JS (226.45 kB) generated in 2.39s |
| Backend CORS & Health | `pytest tests/test_health.py -v` | **PASS (3/3)** | Allowed origin accepted; forbidden rejected; health OK |

### Vitest Test Breakdown

```
 ✓ src/test/parseAnswer.test.ts (5 tests)
   - parses plain text without markers
   - parses single citation marker [1]
   - parses adjacent markers [1][2]
   - parses comma-separated markers [1, 2]
   - renders unknown marker numbers as plain text

 ✓ src/test/highlight.test.ts (5 tests)
   - handles normal single and multiple ranges
   - merges overlapping and touching ranges
   - clamps out-of-bounds offsets safely without throwing
   - handles empty or missing ranges
   - preserves unicode characters and multi-byte offsets

 ✓ src/test/client.test.ts (4 tests)
   - clears token and triggers onUnauthorized callback on 401
   - maps 429 response to rate-limit error message
   - maps 503 response to service busy error message
   - handles network failure with backend unreachable error

 ✓ src/test/ProtectedRoute.test.tsx (2 tests)
   - redirects to /login when user is not authenticated
   - renders children when authenticated

 ✓ src/test/RefusalNotice.test.tsx (2 tests)
   - renders neutral refusal message with accessibility aria-live
   - renders identical style and document availability note across different refusal strings

 ✓ src/test/AnswerCard.test.tsx (3 tests)
   - renders citation markers as clickable buttons and calls onSelectCitation
   - renders verified badge with shield icon when verified: true
   - renders answer as untrusted text and NEVER executes or renders HTML (<script>, <img onerror>)
```

---

## 6. Live Backend Smoke Test & End-to-End Verification

Executed against the live FastAPI backend (`http://127.0.0.1:8000`) and Vite dev server (`http://127.0.0.1:5173`):

### Smoke Test Console Output (`scripts/smoke_test.mjs`)
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
- Text preview: Northwind Industrial Pvt Ltd | Master Logistics Services Agreement VC-2026-014 | Confidential | CONF-VC-3340 Page 1 of 4...
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

========================================
ALL SMOKE TEST CHECKS PASSED SUCCESSFULLY!
========================================
```

### Browser Automated UI Screenshots (`frontend/docs/screenshots/`)

Captured using automated headless Microsoft Edge on Windows 11 (`scripts/capture_screenshots.mjs`):
1. **`login.png`**: Login card with email/password fields, show/hide password, sign-in button, and the 7 quick-login seed user chips.
2. **`chat_answer.png`**: Karan Shah's chat session showing the Apex monthly fee answer with verified shield badge, inline `[1]` button, and bottom sources list.
3. **`citation_panel.png`**: Slide-over citation panel displaying `vendor_contract_apex.pdf (page 1)`, cited passage blockquote, and chunk text with `<mark>` highlight over fee terms.
4. **`refusal.png`**: Asha Patel's chat session displaying the identical neutral refusal notice for the same question.

---

## 7. Commands to Run (Windows cmd)

Open two command prompt windows:

### Terminal 1: Backend
```cmd
cd /d D:\VaultRAG\backend
D:\VaultRAG\.venv\Scripts\activate.bat
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Terminal 2: Frontend
```cmd
cd /d D:\VaultRAG\frontend
npm install
npm run dev
```

Open browser to: **`http://localhost:5173`** (or `http://127.0.0.1:5173`).

---

## 8. Known Gaps & Out of Scope (Deferred to Future Parts)

As specified in the prompt requirements for Part 1:
1. **Document Upload**: No file upload modal or ingestion triggers in the UI yet.
2. **Sharing & Access Delegation**: No UI controls for sharing documents or modifying ACLs.
3. **Admin Monitoring Dashboard**: No telemetry or query audit logs screen yet.
4. **Persistent Chat History**: Chat history is kept in React state in memory only per session.
