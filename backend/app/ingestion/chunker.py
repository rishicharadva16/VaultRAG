"""
Chunker: splits text per page into chunks of at most 500 tokens.
Never crosses page boundaries.
"""

import re
from typing import Callable, Literal

MAX_TOKENS = 500
TARGET_TOKENS = 400
OVERLAP_TOKENS = 50


def estimate_tokens(text: str) -> int:
    """Fallback word-based token estimate (~1.3 tokens per word)."""
    words = text.strip().split()
    if not words:
        return 0
    return max(1, int(len(words) * 1.3))


def make_token_counter(embedder=None) -> Callable[[str], int]:
    """Create a token counting function using embedder's tokenizer if present."""
    if embedder is not None and hasattr(embedder, "_model") and embedder._model is not None:
        model = embedder._model
        if hasattr(model, "tokenizer") and model.tokenizer is not None:
            tokenizer = model.tokenizer
            return lambda t: len(tokenizer.encode(t, add_special_tokens=False))
        if hasattr(model, "tokenize"):
            return lambda t: len(model.tokenize(t))
    return estimate_tokens


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences while preserving sentence content."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def _split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs by double newlines, normalizing intra-paragraph line breaks."""
    paragraphs = re.split(r"\n\s*\n", text)
    cleaned = []
    for p in paragraphs:
        p_clean = " ".join(p.split())
        if p_clean:
            cleaned.append(p_clean)
    return cleaned


def chunk_page_text(
    text: str,
    doc_id: str,
    page: int,
    token_counter: Callable[[str], int] = estimate_tokens,
    start_chunk_idx: int = 1,
) -> tuple[list[dict], int]:
    """
    Split text for a single page into chunks of <= 500 tokens (target ~400, overlap ~50).
    Never crosses page boundary.
    Returns (list of chunk dicts, next chunk index).
    """
    paragraphs = _split_into_paragraphs(text)
    if not paragraphs:
        return [], start_chunk_idx

    normalized_text = " ".join(paragraphs)
    total_tokens = token_counter(normalized_text)
    if total_tokens <= MAX_TOKENS:
        chunk_dict = {
            "chunk_id": f"{doc_id}-p{page}-c{start_chunk_idx}",
            "doc_id": doc_id,
            "page": page,
            "chunk_type": "text",
            "text": normalized_text,
        }
        return [chunk_dict], start_chunk_idx + 1

    # Hierarchical splitting: Paragraphs -> Sentences -> Words
    paragraphs = _split_into_paragraphs(text)
    units = []
    for p in paragraphs:
        if token_counter(p) <= TARGET_TOKENS:
            units.append(p)
        else:
            sentences = _split_into_sentences(p)
            for s in sentences:
                if token_counter(s) <= TARGET_TOKENS:
                    units.append(s)
                else:
                    # Hard word-level split if sentence is huge
                    words = s.split()
                    curr_words = []
                    for w in words:
                        curr_words.append(w)
                        if token_counter(" ".join(curr_words)) >= TARGET_TOKENS:
                            units.append(" ".join(curr_words))
                            curr_words = []
                    if curr_words:
                        units.append(" ".join(curr_words))

    chunks = []
    curr_units = []
    curr_tokens = 0
    chunk_n = start_chunk_idx

    for unit in units:
        unit_tokens = token_counter(unit)
        if curr_tokens + unit_tokens > TARGET_TOKENS and curr_units:
            chunk_text = " ".join(curr_units).strip()
            if chunk_text:
                chunks.append({
                    "chunk_id": f"{doc_id}-p{page}-c{chunk_n}",
                    "doc_id": doc_id,
                    "page": page,
                    "chunk_type": "text",
                    "text": chunk_text,
                })
                chunk_n += 1

            # Compute overlap units for the next chunk
            overlap_units = []
            overlap_count = 0
            for u in reversed(curr_units):
                u_tok = token_counter(u)
                if overlap_count + u_tok <= OVERLAP_TOKENS:
                    overlap_units.insert(0, u)
                    overlap_count += u_tok
                else:
                    break
            curr_units = overlap_units + [unit]
            curr_tokens = sum(token_counter(u) for u in curr_units)
        else:
            curr_units.append(unit)
            curr_tokens += unit_tokens

    if curr_units:
        chunk_text = " ".join(curr_units).strip()
        if chunk_text:
            chunks.append({
                "chunk_id": f"{doc_id}-p{page}-c{chunk_n}",
                "doc_id": doc_id,
                "page": page,
                "chunk_type": "text",
                "text": chunk_text,
            })
            chunk_n += 1

    return chunks, chunk_n


def chunk_page_tables(
    tables: list[str],
    doc_id: str,
    page: int,
    start_chunk_idx: int = 1,
) -> tuple[list[dict], int]:
    """
    Create chunks for table rows extracted from a page.
    Returns (list of chunk dicts, next chunk index).
    """
    chunks = []
    chunk_n = start_chunk_idx
    for table_text in tables:
        t_clean = table_text.strip()
        if not t_clean:
            continue
        chunks.append({
            "chunk_id": f"{doc_id}-p{page}-c{chunk_n}",
            "doc_id": doc_id,
            "page": page,
            "chunk_type": "table",
            "text": t_clean,
        })
        chunk_n += 1
    return chunks, chunk_n


def chunk_document(
    pages_data: list[dict],
    doc_id: str,
    token_counter: Callable[[str], int] = estimate_tokens,
) -> list[dict]:
    """
    Chunk all pages of a document.
    Chunk id numbering restarts per page (e.g. doc-p1-c1, doc-p1-c2, doc-p2-c1...).
    """
    all_chunks = []
    for page_info in pages_data:
        page_num = page_info["page"]
        chunk_idx = 1

        # Text chunks
        text_chunks, chunk_idx = chunk_page_text(
            page_info.get("text", ""),
            doc_id,
            page_num,
            token_counter=token_counter,
            start_chunk_idx=chunk_idx,
        )
        all_chunks.extend(text_chunks)

        # Table chunks
        table_chunks, chunk_idx = chunk_page_tables(
            page_info.get("tables", []),
            doc_id,
            page_num,
            start_chunk_idx=chunk_idx,
        )
        all_chunks.extend(table_chunks)

    return all_chunks
