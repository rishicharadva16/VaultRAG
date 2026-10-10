"""
OCR Engine abstraction for VaultRAG.
Provides a clean interface for local OCR execution using RapidOCR (or other engines).
Sensitive text is never logged.
"""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any
import numpy as np
from PIL import Image

from app.config import settings
from app.ocr.preprocess import preprocess_image, load_image, map_points_to_original

logger = logging.getLogger(__name__)

_RAPID_OCR_INSTANCE = None


@dataclass
class OCRLine:
    text: str
    confidence: float
    box: list[list[float]]  # 4 corner points in pixels [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]


def _get_rapid_ocr():
    global _RAPID_OCR_INSTANCE
    if _RAPID_OCR_INSTANCE is None:
        from rapidocr_onnxruntime import RapidOCR
        _RAPID_OCR_INSTANCE = RapidOCR()
        logger.info("[OCR] RapidOCR engine loaded")
    return _RAPID_OCR_INSTANCE


def ocr_image(
    image_input: str | Path | bytes | Image.Image | np.ndarray,
    preprocess: bool = True,
    preprocess_steps: dict[str, bool] | None = None,
    min_confidence: float | None = None,
) -> tuple[list[OCRLine], Image.Image, dict[str, Any]]:
    """
    Perform OCR on an image.
    
    Returns:
      (lines, preprocessed_image, metadata)
      where each line has text, confidence, and 4 corner pixel coordinates on preprocessed_image.
    """
    min_conf = min_confidence if min_confidence is not None else settings.OCR_MIN_CONFIDENCE

    if preprocess:
        processed_img, meta = preprocess_image(image_input, steps=preprocess_steps)
    else:
        processed_img = load_image(image_input)
        meta = {"orig_size": processed_img.size, "final_size": processed_img.size, "steps_applied": []}

    img_np = np.array(processed_img)
    engine = _get_rapid_ocr()

    raw_results, elapse = engine(img_np)
    meta["elapse_seconds"] = sum(elapse) if elapse else 0.0

    lines: list[OCRLine] = []
    if raw_results:
        for item in raw_results:
            box, text, conf = item[0], item[1], float(item[2])
            text_str = str(text).strip()
            if not text_str:
                continue
            if conf < min_conf:
                continue
            # Ensure box is a 4-point list of [x, y] in preprocessed coordinates
            processed_points = [[float(pt[0]), float(pt[1])] for pt in box]
            orig_points = map_points_to_original(processed_points, meta)
            lines.append(OCRLine(text=text_str, confidence=round(conf, 4), box=orig_points))

    return lines, processed_img, meta
