"""
Image OCR chunking and bounding box normalization.
Groups lines into reading-order blocks and constructs Qdrant payload items.
"""

from typing import Any
from app.ocr.engine import OCRLine


def normalize_box(pts: list[list[float]], img_w: int, img_h: int) -> dict[str, float]:
    """
    Convert 4-point polygon into normalized [0..1] bounding box {x, y, w, h}.
    Clamps all values strictly between 0 and 1.
    """
    if img_w <= 0 or img_h <= 0:
        return {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}

    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    x_min = max(0.0, min(xs))
    y_min = max(0.0, min(ys))
    x_max = min(float(img_w), max(xs))
    y_max = min(float(img_h), max(ys))

    x = round(min(1.0, max(0.0, x_min / img_w)), 4)
    y = round(min(1.0, max(0.0, y_min / img_h)), 4)
    w = round(min(1.0 - x, max(0.0, (x_max - x_min) / img_w)), 4)
    h = round(min(1.0 - y, max(0.0, (y_max - y_min) / img_h)), 4)

    return {"x": x, "y": y, "w": w, "h": h}


def chunk_ocr_lines(
    lines: list[OCRLine],
    filename: str,
    img_width: int,
    img_height: int,
    file_ref: str,
    max_chunk_chars: int = 800,
) -> list[dict[str, Any]]:
    """
    Group OCR lines into reading order and produce chunk dictionaries.
    Lines are ordered top-to-bottom.
    Small images (< max_chunk_chars) yield exactly 1 chunk (chunk_id img:<filename>#0).
    Larger images split by character threshold while keeping line breaks as spaces.
    """
    if not lines:
        return []

    # Sort lines by vertical center then horizontal left
    def line_sort_key(line: OCRLine):
        ys = [pt[1] for pt in line.box]
        xs = [pt[0] for pt in line.box]
        return (min(ys), min(xs))

    sorted_lines = sorted(lines, key=line_sort_key)

    total_chars = sum(len(l.text) for l in sorted_lines) + len(sorted_lines)
    blocks: list[list[OCRLine]] = []

    if total_chars <= max_chunk_chars:
        blocks = [sorted_lines]
    else:
        current_block: list[OCRLine] = []
        current_len = 0
        for l in sorted_lines:
            line_len = len(l.text) + 1
            if current_block and (current_len + line_len > max_chunk_chars):
                blocks.append(current_block)
                current_block = [l]
                current_len = line_len
            else:
                current_block.append(l)
                current_len += line_len
        if current_block:
            blocks.append(current_block)

    chunks: list[dict[str, Any]] = []
    source_id = f"img:{filename}"

    for n, block in enumerate(blocks):
        chunk_id = f"img:{filename}#{n}"
        text_parts = [l.text for l in block]
        chunk_text = " ".join(text_parts).strip()
        mean_conf = round(sum(l.confidence for l in block) / len(block), 4)

        boxes: list[dict[str, Any]] = []
        for l in block:
            norm_b = normalize_box(l.box, img_width, img_height)
            boxes.append({
                "text": l.text,
                "x": norm_b["x"],
                "y": norm_b["y"],
                "w": norm_b["w"],
                "h": norm_b["h"],
                "conf": l.confidence,
            })

        chunks.append({
            "chunk_id": chunk_id,
            "source_id": source_id,
            "file": filename,
            "page": None,
            "kind": "image",
            "corpus": "main",
            "text": chunk_text,
            "ocr_confidence": mean_conf,
            "boxes": boxes,
            "image_width": img_width,
            "image_height": img_height,
            "file_ref": file_ref,
        })

    return chunks
