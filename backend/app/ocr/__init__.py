"""OCR package for VaultRAG."""
from app.ocr.engine import OCRLine, ocr_image
from app.ocr.chunking import chunk_ocr_lines, normalize_box
from app.ocr.preprocess import preprocess_image

__all__ = ["OCRLine", "ocr_image", "chunk_ocr_lines", "normalize_box", "preprocess_image"]
