"""
HTML document loader for dataset documents and poison files.

Extracts text including hidden elements (e.g. style="display:none") using standard
library html.parser.
"""

from html.parser import HTMLParser
from pathlib import Path


class _TextExtractingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._in_ignored = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style"):
            self._in_ignored = True
        elif tag_lower in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "br"):
            self._chunks.append("\n")

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style"):
            self._in_ignored = False
        elif tag_lower in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr"):
            self._chunks.append("\n")

    def handle_data(self, data: str):
        if not self._in_ignored:
            self._chunks.append(data)

    def get_text(self) -> str:
        raw = "".join(self._chunks)
        # Normalize whitespace while preserving paragraphs
        lines = [line.strip() for line in raw.splitlines()]
        non_empty = [l for l in lines if l]
        return "\n\n".join(non_empty)


def load_html(file_path: str | Path) -> dict:
    """
    Load an HTML file and return standard document page format.
    Extracts text from all visible and hidden content tags (like display:none).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"HTML file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        html_content = f.read()

    parser = _TextExtractingParser()
    parser.feed(html_content)
    text = parser.get_text().strip()

    is_empty = len(text) == 0

    return {
        "source_name": path.name,
        "total_pages": 1,
        "pages": [
            {
                "page": 1,
                "text": text,
                "tables": [],
                "is_empty": is_empty,
            }
        ],
        "empty_pages": [1] if is_empty else [],
    }
