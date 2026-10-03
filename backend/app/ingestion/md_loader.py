"""
Markdown loader for dataset documents and poison files.

Reads raw markdown files preserving all comments and hidden prompt injections.
"""

from pathlib import Path


def load_md(file_path: str | Path) -> dict:
    """
    Load a markdown file and return standard document page format.
    Preserves HTML comments and raw formatting.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Markdown file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    cleaned = content.strip()
    is_empty = len(cleaned) == 0

    return {
        "source_name": path.name,
        "total_pages": 1,
        "pages": [
            {
                "page": 1,
                "text": cleaned,
                "tables": [],
                "is_empty": is_empty,
            }
        ],
        "empty_pages": [1] if is_empty else [],
    }
