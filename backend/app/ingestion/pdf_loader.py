"""
PDF loader: extracts text and tables per page using PyMuPDF and pdfplumber.
"""

import logging
from pathlib import Path
from typing import Any

import pymupdf
import pdfplumber

logger = logging.getLogger(__name__)


def format_table_row(headers: list[str], row: list[Any]) -> str:
    """Format a table row as 'Header: value; Header: value'."""
    parts = []
    for h, val in zip(headers, row):
        h_clean = str(h).strip() if h is not None else ""
        v_clean = str(val).strip() if val is not None else ""
        if h_clean and v_clean:
            parts.append(f"{h_clean}: {v_clean}")
        elif v_clean:
            parts.append(v_clean)
    return "; ".join(parts)


def extract_tables_from_page(plumber_page) -> list[str]:
    """Extract and format tables from a pdfplumber page."""
    table_strings = []
    raw_tables = plumber_page.extract_tables() or []

    for table in raw_tables:
        if not table or len(table) == 0:
            continue

        # Check if first row can be used as headers (non-empty strings)
        first_row = table[0]
        has_valid_headers = (
            len(first_row) > 0
            and all(c is not None and str(c).strip() != "" for c in first_row)
        )

        if has_valid_headers and len(table) > 1:
            headers = [str(c).strip() for c in first_row]
            data_rows = table[1:]
        else:
            num_cols = max(len(row) for row in table if row)
            headers = [f"Column {i + 1}" for i in range(num_cols)]
            data_rows = table

        for row in data_rows:
            if not row or not any(c is not None and str(c).strip() != "" for c in row):
                continue
            formatted = format_table_row(headers, row)
            if formatted.strip():
                table_strings.append(formatted)

    return table_strings


def load_pdf(pdf_path: str | Path) -> dict:
    """
    Extract text and tables from a PDF file.

    Returns:
    {
        "source_name": str,
        "total_pages": int,
        "pages": [
            {
                "page": int (1-based),
                "text": str,
                "tables": list[str],
                "is_empty": bool,
            },
            ...
        ],
        "empty_pages": list[int],
    }
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {path}")

    pages_data = []
    empty_pages = []

    # Open with pymupdf for text extraction
    doc = pymupdf.open(str(path))
    # Open with pdfplumber for table extraction
    with pdfplumber.open(str(path)) as plumber_doc:
        for page_idx in range(len(doc)):
            page_num = page_idx + 1
            fitz_page = doc[page_idx]
            page_text = fitz_page.get_text("text").strip()

            plumber_page = plumber_doc.pages[page_idx]
            page_tables = extract_tables_from_page(plumber_page)

            is_empty = not bool(page_text) and not bool(page_tables)
            if is_empty:
                logger.warning("Page %d of %s has no extractable text or tables (possibly scanned)", page_num, path.name)
                empty_pages.append(page_num)

            pages_data.append({
                "page": page_num,
                "text": page_text,
                "tables": page_tables,
                "is_empty": is_empty,
            })

    doc.close()

    return {
        "source_name": path.name,
        "total_pages": len(pages_data),
        "pages": pages_data,
        "empty_pages": empty_pages,
    }
