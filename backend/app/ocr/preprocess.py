"""
Image preprocessing for OCR.
All preprocessing operates on copies so the original image remains untouched.
Steps are individually switchable for benchmarking and ablation.
"""

from io import BytesIO
from pathlib import Path
from typing import Any
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def load_image(image_input: str | Path | bytes | Image.Image | np.ndarray) -> Image.Image:
    """Load any image input into a PIL RGB Image."""
    if isinstance(image_input, Image.Image):
        return image_input.convert("RGB")
    if isinstance(image_input, np.ndarray):
        if len(image_input.shape) == 2:
            return Image.fromarray(image_input).convert("RGB")
        if image_input.shape[2] == 4:
            return Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGRA2RGBA)).convert("RGB")
        return Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
    if isinstance(image_input, (str, Path)):
        return Image.open(str(image_input)).convert("RGB")
    if isinstance(image_input, (bytes, bytearray)):
        return Image.open(BytesIO(image_input)).convert("RGB")
    raise ValueError(f"Unsupported image input type: {type(image_input)}")


def apply_exif(img: Image.Image) -> tuple[Image.Image, bool]:
    """Apply EXIF orientation tag."""
    transposed = ImageOps.exif_transpose(img)
    applied = transposed is not img
    return transposed, applied


def detect_rotation_90(img: Image.Image, ocr_fn=None) -> tuple[Image.Image, int]:
    """
    Test 4 coarse rotations (0, 90, 180, 270) on a downscaled copy.
    Select angle with the highest score (lines * mean_conf).
    """
    if ocr_fn is None:
        return img, 0

    # Downscale copy for fast evaluation
    w, h = img.size
    scale = min(1.0, 600.0 / max(w, h))
    thumb = img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)

    best_angle = 0
    best_score = -1.0

    for angle in [0, 90, 180, 270]:
        rotated_thumb = thumb.rotate(angle, expand=True) if angle != 0 else thumb
        res = ocr_fn(rotated_thumb)
        if not res:
            score = 0.0
        else:
            confs = [r[2] for r in res]
            mean_c = sum(confs) / len(confs)
            score = len(res) * mean_c

        if score > best_score:
            best_score = score
            best_angle = angle

    if best_angle != 0:
        return img.rotate(best_angle, expand=True), best_angle
    return img, 0


import math

def detect_deskew(img: Image.Image, max_angle: float = 15.0) -> tuple[Image.Image, float, Any]:
    """
    Deskew small angular tilts (|angle| <= max_angle).
    Uses OpenCV minAreaRect / Hough lines on Otsu threshold.
    Returns (deskewed_img, angle, M_inv).
    """
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return img, 0.0, None

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) > max_angle:
        # Fall back to Hough lines
        lines = cv2.HoughLinesP(thresh, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)
        angles = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                ang = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                if abs(ang) <= max_angle:
                    angles.append(ang)
        angle = float(np.median(angles)) if angles else 0.0

    if abs(angle) > 0.5 and abs(angle) <= max_angle:
        h, w = img_cv.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        M_inv = cv2.invertAffineTransform(M)
        rotated_cv = cv2.warpAffine(
            img_cv, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
        )
        return Image.fromarray(cv2.cvtColor(rotated_cv, cv2.COLOR_BGR2RGB)), angle, M_inv

    return img, 0.0, None


def upscale_low_res(img: Image.Image, min_dim: int = 800) -> tuple[Image.Image, float]:
    """
    Upscale image if smaller dimension is below min_dim to ensure adequate text pixel height.
    """
    w, h = img.size
    min_current = min(w, h)
    if min_current < min_dim and min_current > 0:
        scale = float(min_dim) / min_current
        new_w, new_h = int(w * scale), int(h * scale)
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS), scale
    return img, 1.0


def enhance_contrast_and_sharpen(
    img: Image.Image, contrast_factor: float = 1.3, sharpness_factor: float = 1.8
) -> Image.Image:
    """Enhance contrast and sharpness for blurry or low-contrast scans."""
    enh = ImageEnhance.Contrast(img).enhance(contrast_factor)
    enh = ImageEnhance.Sharpness(enh).enhance(sharpness_factor)
    return enh


def map_points_to_original(pts: list[list[float]], meta: dict[str, Any]) -> list[list[float]]:
    """
    Map polygon corner points from preprocessed image coordinates back to original image pixel coordinates.
    Applies inverse transforms in reverse order of application.
    """
    transforms = meta.get("transforms", [])
    current_pts = [list(p) for p in pts]

    for t in reversed(transforms):
        t_type = t.get("type")
        if t_type == "scale":
            s = float(t["scale"])
            if s > 0:
                current_pts = [[p[0] / s, p[1] / s] for p in current_pts]
        elif t_type == "affine":
            M_inv = t["M_inv"]
            mapped = []
            for p in current_pts:
                v = M_inv @ np.array([p[0], p[1], 1.0])
                mapped.append([float(v[0]), float(v[1])])
            current_pts = mapped
        elif t_type == "rotate":
            angle = float(t["angle"])
            sb = t["size_before"]
            sa = t["size_after"]
            th = math.radians(angle)
            c, s = math.cos(th), math.sin(th)
            cx0, cy0 = sb[0] / 2.0, sb[1] / 2.0
            cx1, cy1 = sa[0] / 2.0, sa[1] / 2.0
            mapped = []
            for p in current_pts:
                dx1, dy1 = p[0] - cx1, p[1] - cy1
                x0 = dx1 * c - dy1 * s + cx0
                y0 = dx1 * s + dy1 * c + cy0
                mapped.append([float(x0), float(y0)])
            current_pts = mapped

    return current_pts


def preprocess_image(
    image_input: str | Path | bytes | Image.Image | np.ndarray,
    steps: dict[str, bool] | None = None,
    ocr_coarse_fn: Any = None,
) -> tuple[Image.Image, dict[str, Any]]:
    """
    Run switchable preprocessing pipeline on an image copy.
    Returns: (preprocessed_image, metadata_dict)
    """
    config = {
        "exif": True,
        "rotation_90": False,  # disabled by default unless requested (RapidOCR handles vertical orientation)
        "deskew": True,
        "upscale": True,
        "enhance": False,      # disabled by default; RapidOCR handles standard digital text well
    }
    if steps:
        config.update(steps)

    img = load_image(image_input)
    meta: dict[str, Any] = {
        "orig_size": img.size,
        "steps_applied": [],
        "transforms": [],
        "rotation_angle": 0,
        "deskew_angle": 0.0,
        "upscale_factor": 1.0,
    }

    if config.get("exif"):
        img, applied = apply_exif(img)
        if applied:
            meta["steps_applied"].append("exif")

    if config.get("rotation_90") and ocr_coarse_fn:
        w_before, h_before = img.size
        img, angle = detect_rotation_90(img, ocr_coarse_fn)
        if angle != 0:
            meta["rotation_angle"] = angle
            meta["steps_applied"].append(f"rot_{angle}")
            meta["transforms"].append({
                "type": "rotate",
                "angle": angle,
                "size_before": (w_before, h_before),
                "size_after": img.size,
            })

    if config.get("deskew"):
        img, angle, M_inv = detect_deskew(img)
        if abs(angle) > 0.5:
            meta["deskew_angle"] = round(angle, 2)
            meta["steps_applied"].append(f"deskew_{meta['deskew_angle']}")
            if M_inv is not None:
                meta["transforms"].append({"type": "affine", "M_inv": M_inv})

    if config.get("upscale"):
        img, scale = upscale_low_res(img, min_dim=800)
        if scale > 1.0:
            meta["upscale_factor"] = round(scale, 2)
            meta["steps_applied"].append(f"upscale_{meta['upscale_factor']}")
            meta["transforms"].append({"type": "scale", "scale": scale})

    if config.get("enhance"):
        img = enhance_contrast_and_sharpen(img)
        meta["steps_applied"].append("enhance")

    meta["final_size"] = img.size
    return img, meta

