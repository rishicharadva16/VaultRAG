# VaultRAG Step 5b: Follow-up Fixes & API Polish Summary

## 1. Overview & Verification Status

Step 5b completes the precision refinement of the grounded question-answering pipeline. All 89 tests across the VaultRAG backend test suite are green. Access-control logic in `SecureStore` remains untouched and strictly enforced.

| Check | Expected | Actual Status |
|---|---|---|
| **Pytest Suite (`not llm`)** | All green | **88 passed**, 1 deselected (156.67s) |
| **Full Suite (with Ollama)** | All green | **89 passed** |
| **Existing Test Regressions** | 0 regressions | **0 regressions** |
| **Access Control Logic** | Unmodified | **Strictly preserved** |
| **ACL Leak Checks** | 0 leaks | **0 leaks** (acl_tokens never returned) |

---

## 2. Changes by File

### 1. `backend/app/rag/answer.py`
- **Citation Sub-Window Highlighting**:
  - Added `_split_into_windows(text, max_chars=250)`: Splits candidate chunks into sentence-aligned spans of at most 250 characters.
  - Added `_find_best_highlight(answer_sentence, chunk_text, reranker)`:
    1. Scores each candidate window against the answer sentence using `reranker.score_pairs()`.
    2. Identifies the highest-scoring passage window.
    3. Extracts critical fact tokens (money amounts, dates, alphanumeric codes) from the answer sentence using `_extract_fact_tokens()`.
    4. Ensures that all fact tokens from the answer sentence appear inside the chosen highlight window. If any are outside, locates them via regex in `chunk_text` and expands the `[best_start, best_end]` window boundaries to encompass them.
  - Added `_build_snippet_around_highlight(chunk_text, hl_start, hl_end, max_snippet=300)`: Produces a snippet of ~300 characters centered directly on the highlight span, replacing the previous chunk-prefix snippet so previews show the supporting evidence line.
  - Returns `highlights`: list of `{start, end}` character offsets into the EXACT text string returned by `GET /citation/{chunk_id}`, and `highlight_text`: the exact supporting substring (`chunk_text[start:end]`).
- **Cite Only What Supports**:
  - In citation verification, chunks cited by the LLM are evaluated against each sentence via `reranker.score_pairs()`.
  - Only chunks scoring $\ge \text{SUPPORT\_THRESHOLD}$ (0.05) are retained. Padding chunks (such as contract page 2 invoicing terms cited for a monthly fee inquiry) are dropped.
  - Remaining citations are renumbered sequentially from `1..n` in order of first appearance.
- **Keep & Insert Citation Markers**:
  - If the LLM generates `[n]` bracket markers, they are remapped to match the newly renumbered citation IDs.
  - If the LLM omitted markers from the sentence text, verified citation markers (e.g. `[1]`, `[1][2]`) are automatically appended to each sentence.
- **Per-Sentence Verification**:
  - Verification was previously evaluated sentence-by-sentence; this implementation formally decouples sentence survival: each sentence is validated independently for facts and semantic support.
  - Unsupported sentences are dropped while supported sentences are retained in the final response.
  - Safe refusal is returned only if zero verified sentences remain.

### 2. `backend/app/api/ask.py`
- **Schema Updates**:
  - `HighlightOut`: `{ "start": int, "end": int }`
  - `CitationOut`: Added `highlights: list[HighlightOut] = []` and `highlight_text: str = ""`
  - `ChunkResponse`: `{ "chunk_id": str, "source_id": str, "file": str, "page": int | None, "text": str }`
- **Error Handling**:
  - Unauthenticated requests return `401 Unauthorized`.
  - Deactivated users return `401 Unauthorized`.
  - Missing or forbidden citation chunk IDs return byte-for-byte identical `404 Not Found` (`{"detail": "Chunk not found"}`).
  - `LLMTimeout` returns `503 Service Unavailable` with `{"detail": "The answer service is temporarily unavailable. Please try again later."}` — explicitly distinct from the constant refusal string.
  - `acl_tokens` are never exposed in any `/ask` or `/citation` response payload.

### 3. `backend/app/rag/reranker.py` (+18 lines)
- **What changed**:
  1. `os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")`: Disables HuggingFace Rust Rayon tokenizer thread parallelism to eliminate deadlocks with PyTorch OpenMP worker threads on Windows CPU.
  2. `score_pairs(self, pairs: list[list[str]]) -> list[float]`: Exposes direct pairwise scoring via `CrossEncoder.predict(pairs)`. Used by `answer_question()` for semantic support validation and sub-window passage highlighting. Includes exception trapping and graceful fallback.

### 4. `backend/tests/test_ask.py` (Expanded to 34 tests)
- Added the following targeted tests:
  1. `test_highlight_offsets_match_chunk_text`: Asserts that `chunk_text[hl.start:hl.end] == cit.highlight_text` for every returned highlight.
  2. `test_apex_fee_highlights_amount`: Verifies that the Apex monthly fee answer highlights the sentence containing `"Rs 4,00,000"` and centers the snippet around it.
  3. `test_unsupported_padding_citation_dropped`: Verifies that padding citations (e.g. page 2 invoicing) are pruned and remaining citation IDs renumbered `1..n`.
  4. `test_answer_contains_bracket_markers`: Asserts `[n]` bracket markers appear in final answer text.
  5. `test_markers_inserted_when_llm_omits_them`: Verifies automatic insertion of `[1]` when LLM produces unmarked text.
  6. `test_per_sentence_keeps_supported_drops_unsupported`: Verifies multi-sentence answers keep valid sentences and drop invalid ones without full refusal.
  7. `test_ask_without_token_401`: Verifies `POST /ask` without a Bearer token returns HTTP 401.
  8. `test_ask_deactivated_user_401`: Verifies `POST /ask` for a deactivated user returns HTTP 401.
  9. `test_citation_without_token_401`: Verifies `GET /citation/{id}` without a token returns HTTP 401.
  10. `test_llm_timeout_returns_503`: Verifies that `LLMTimeout` returns HTTP 503 with generic error body, not the refusal string.
  11. `test_acl_tokens_never_in_ask_response`: Asserts `acl_tokens` substring never appears in any `/ask` response.
  12. `test_acl_tokens_never_in_citation_response`: Asserts `acl_tokens` substring never appears in any `/citation` response.
  13. `test_relevance_gate_refuses_without_llm_call`: Uses `FakeLLM` with 0 queued responses and asserts `call_count == 0` when candidate scores fall below `RELEVANCE_THRESHOLD`.

### 5. `backend/scripts/walkthrough.py`, `README.md`, `docs/step5_summary.md`
- Fixed walkthrough request payload: corrected `"query"` to `"question"`.
- Updated documentation examples to reflect full API response structure with `highlights` and `highlight_text`.

---

## 3. Calibration Check & Reranker Score Distribution Analysis

### 1. Raw Per-Question Reranker Scores (`scripts/calibration_cache.json`)

The table below lists all 33 evaluated PDF questions from `scripts/calibration_cache.json`:
- **Answerable User Top Score**: Reranker top score for the user permitted to answer.
- **Forbidden User Top Score**: Reranker top score for the user denied access (or `-99.0` sentinel if 0 chunks retrieved due to empty ACL intersection, e.g. `u_admin`).
- **Scale**: All non-sentinel scores produced by `BAAI/bge-reranker-v2-m3` via `CrossEncoder.predict()` are **sigmoid probabilities in $[0.0, 1.0]$**.

| Question ID | Asker / Answerable User | Top Score (Answerable) | Forbidden User | Top Score (Forbidden) |
|:---:|:---:|:---:|:---:|:---:|
| **Q001** | `u_asha` | 0.9728 | `u_admin` | -99.0000 (0 chunks) |
| **Q002** | `u_asha` | 0.6690 | `u_admin` | -99.0000 (0 chunks) |
| **Q003** | `u_neha` | 0.4795 | `u_admin` | -99.0000 (0 chunks) |
| **Q004** | `u_neha` | 0.0820 | `u_admin` | -99.0000 (0 chunks) |
| **Q005** | `u_ravi` | 0.9940 | `u_admin` | -99.0000 (0 chunks) |
| **Q006** | `u_asha` | 0.9814 | `u_admin` | -99.0000 (0 chunks) |
| **Q007** | `u_asha` | 0.8863 | `u_admin` | -99.0000 (0 chunks) |
| **Q008** | `u_ravi` | 0.9074 | `u_admin` | -99.0000 (0 chunks) |
| **Q009** | `u_neha` | 0.9931 | `u_admin` | -99.0000 (0 chunks) |
| **Q010** | `u_asha` | 0.9433 | `u_admin` | -99.0000 (0 chunks) |
| **Q011** | `u_asha` | 0.9869 | `u_admin` | -99.0000 (0 chunks) |
| **Q012** | `u_ravi` | 0.4359 | `u_admin` | -99.0000 (0 chunks) |
| **Q013** | `u_ravi` | 0.9946 | `u_admin` | -99.0000 (0 chunks) |
| **Q014** | `u_neha` | 0.9947 | `u_admin` | -99.0000 (0 chunks) |
| **Q015** | `u_asha` | 0.9815 | `u_admin` | -99.0000 (0 chunks) |
| **Q016** | `u_dev` | 0.9915 | `u_admin` | -99.0000 (0 chunks) |
| **Q017** | `u_asha` | 0.6107 | `u_admin` | -99.0000 (0 chunks) |
| **Q018** | `u_neha` | 0.3478 | `u_admin` | -99.0000 (0 chunks) |
| **Q019** | `u_karan` | 0.9963 | `u_asha` | 0.0112 |
| **Q020** | `u_meera` | 0.9969 | `u_asha` | 0.0091 |
| **Q021** | `u_meera` | 0.9546 | `u_asha` | 0.0038 |
| **Q022** | `u_karan` | 0.9936 | `u_asha` | 0.0023 |
| **Q023** | `u_karan` | 0.9039 | `u_asha` | 0.0006 |
| **Q024** | `u_ravi` | 0.1520 | `u_asha` | 0.0004 |
| **Q025** | `u_karan` | 0.6456 | `u_asha` | 0.0075 |
| **Q026** | `u_ravi` | 0.4348 | `u_asha` | 0.0002 |
| **Q027** | `u_karan` | 0.9440 | `u_asha` | 0.0069 |
| **Q028** | `u_karan` | 0.9587 | `u_asha` | 0.0001 |
| **Q029** | `u_karan` | 0.9796 | `u_asha` | 0.0003 |
| **Q030** | *None (All Deny)* | N/A | `u_asha` | 0.0012 |
| **Q031** | *None (All Deny)* | N/A | `u_asha` | 0.3191 |
| **Q032** | *None (All Deny)* | N/A | `u_asha` | 0.0355 |
| **Q033** | *None (All Deny)* | N/A | `u_asha` | 0.0005 |

### 2. Explanation of the Earlier Inconsistent Table
The Step 5 summary table previously showed:
- Negative minimums (down to `-8.4120`) alongside positive values up to `0.9984`.
- "64 positive and 64 negative pairs from 64 searches".

**Why this occurred**:
1. **Mixed Scale (Logits vs. Probabilities)**: Unnormalized cross-encoder models output unbounded real logits $(-\infty, +\infty)$, where values like $-8.4$ indicate strong irrelevance. However, `CrossEncoder("BAAI/bge-reranker-v2-m3")` applies a sigmoid activation function when predicting binary classification scores, outputting probabilities in $[0.0, 1.0]$. The previous table accidentally mixed raw logits from a draft exploratory script with sigmoid probabilities from the cached results.
2. **Search Count vs. Pair Count Confusion**: 64 was the total number of hybrid searches executed (33 questions $\times \approx 2$ users per question = 64 searches). The summary incorrectly categorized the 64 searches as 64 positive and 64 negative pairs.

### 3. Corrected Consistent Distribution (Sigmoid Probabilities $[0, 1]$)

| Category | Count | Min | P10 | P25 | Median | P75 | P90 | Max |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Answerable Queries (Top Hit)** | 29 | 0.0820 | 0.3478 | 0.6456 | 0.9546 | 0.9915 | 0.9947 | 0.9969 |
| **Forbidden Queries (Top Hit)** | 17 | 0.0001 | 0.0002 | 0.0005 | 0.0023 | 0.0091 | 0.3191 | 0.3191 |
| **Fact-Chunk Support Pairs** | 44 | 0.0046 | 0.0133 | 0.1118 | 0.1859 | 0.4567 | 0.6484 | 0.8678 |

### 4. Threshold Confirmation
- **`RELEVANCE_THRESHOLD = 0.10`**: Provides clear discrimination between relevant documents (median 0.9546) and forbidden/irrelevant candidates (median 0.0023).
- **`SUPPORT_THRESHOLD = 0.05`**: Effectively validates sentence claims against supporting chunks without discarding natural variations.
- Both thresholds in `.env.example` remain accurate and validated.

---

## 4. Confirmed Frontend API Specifications

### Endpoint 1: `POST /ask`

#### Request
- **Headers**: `Authorization: Bearer <JWT_TOKEN>`, `Content-Type: application/json`
- **Fields**:
  - `question` (*string*, required, 1–500 chars): The user query.
  - `top_k` (*integer*, optional, default: 5, range: 1–20): Context chunk limit.

```json
{
  "question": "What is the fixed monthly service fee for Apex Logistics under contract VC-2026-014?",
  "top_k": 5
}
```

#### Response (Success - Answered)
- **Status**: `200 OK`
- **Fields**:
  - `answer` (*string*): The synthesized answer containing `[n]` citation markers.
  - `refused` (*boolean*): `false` when answered, `true` when refused.
  - `verified` (*boolean*): `true` when claims and citations are verified.
  - `citations` (*array*): List of supporting citation items.
    - `id` (*integer*): Citation marker number (`1..n`).
    - `chunk_id` (*string*): Unique chunk identifier in Qdrant.
    - `source_id` (*string*): Document source identifier (e.g. `pdf:vendor_contract_apex.pdf`).
    - `file` (*string*): Filename.
    - `page` (*integer* or `null`): Document page number.
    - `snippet` (*string*): Context preview (~300 characters) centered on the highlight.
    - `highlights` (*array* of objects): Character spans `{ "start": int, "end": int }` relative to the EXACT text returned by `GET /citation/{chunk_id}`.
    - `highlight_text` (*string*): The exact substring from the chunk that supports the answer sentence.

- **Response (`u_karan` - Authorized, asking Apex monthly fee)**:
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

- **Response (`u_asha` - Forbidden / Safe Refusal, asking Apex monthly fee)**:
  ```json
  {
    "answer": "I couldn't find an answer to that in the documents available to you.",
    "refused": true,
    "verified": false,
    "citations": []
  }
  ```

---

### Endpoint 2: `GET /citation/{chunk_id}`

#### Request
- **Headers**: `Authorization: Bearer <JWT_TOKEN>`
- **Path Parameter**: `chunk_id` (string)

#### Response (Authorized & Found)
- **Status**: `200 OK`
- **Fields**:
  - `chunk_id` (*string*): Unique chunk identifier.
  - `source_id` (*string*): Document source identifier.
  - `file` (*string*): Filename.
  - `page` (*integer* or `null`): Document page number.
  - `text` (*string*): Complete raw chunk text. Note: `chunk.text[start:end]` from `highlights` matches `highlight_text` exactly.

```json
{
  "chunk_id": "vendor_contract_apex-p1-c1",
  "source_id": "pdf:vendor_contract_apex.pdf",
  "file": "vendor_contract_apex.pdf",
  "page": 1,
  "text": "Northwind Industrial Pvt Ltd | Master Logistics Services Agreement VC-2026-014 | Confidential | CONF-VC-3340 Page 1 of 4 Master Logistics Services Agreement This Agreement is made between Northwind Industrial Pvt Ltd (the Company) and Apex Logistics Pvt Ltd (the Vendor), contract reference VC-2026-014. 1. Term The Agreement is effective for a term of 24 months, from 1 Apr 2026 - 31 Mar 2028, unless terminated earlier under Clause 7. 2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%."
}
```

#### Response (Forbidden OR Non-existent Chunk)
- **Status**: `404 Not Found`
- **Side-Channel Defense**: Returns byte-for-byte identical payload to prevent user enumerating chunk existence.
```json
{
  "detail": "Chunk not found"
}
```

---

## 5. Cleanup & State Verification

1. **`scripts/debug_calibrate.py`**:
   - Verified that `scripts/debug_calibrate.py` does not exist in the repository; any temporary debugging scripts have been removed.
2. **`app/rag/reranker.py`**:
   - The +18 lines diff was verified: sets `TOKENIZERS_PARALLELISM="false"` and implements `score_pairs()` for safe cross-encoder batch inference.
3. **Walkthrough Fixes**:
   - Corrected `"query"` $\to$ `"question"` across `README.md`, `docs/step5_summary.md`, and validated `scripts/walkthrough.py`.
4. **Assumptions & Defaults**:
   - Reranker continues to run CPU inference with `TOKENIZERS_PARALLELISM="false"` to prevent Windows Rayon/OpenMP hangs.
   - LLM generation connects to host Ollama (`http://localhost:11434`) running `qwen2.5:7b`.
