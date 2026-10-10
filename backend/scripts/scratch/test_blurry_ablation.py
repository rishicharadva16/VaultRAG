import json
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.ocr.engine import _get_rapid_ocr
from app.ocr.preprocess import load_image

def norm_str(s: str) -> str:
    return "".join(c.lower() for c in s if c.isalnum())

ds_path = settings.dataset_path()
img_dir = ds_path / "dataset" / "corpus" / "images"
gt_file = img_dir / "image_ground_truth.json"

with open(gt_file, "r", encoding="utf-8") as f:
    gt_data = json.load(f)

gt_entry = gt_data["invoice_04_apex_may_blurry.jpg"]
key_fields = [r for r in gt_entry["text_regions"] if r.get("field") is not None]

def eval_img(img_pil, desc):
    engine = _get_rapid_ocr()
    img_np = np.array(img_pil)
    results, _ = engine(img_np)
    lines = [r[1] for r in results] if results else []
    full_text = " ".join(lines)
    norm_full = "".join(c.lower() for c in full_text if c.isalnum())
    hits = 0
    missing = []
    found = []
    for kf in key_fields:
        k_norm = "".join(c.lower() for c in kf["text"] if c.isalnum())
        if k_norm in norm_full:
            hits += 1
            found.append(kf["text"])
        else:
            missing.append(kf["text"])
    recall = hits / len(key_fields)
    print(f"{desc:<35}: {hits}/{len(key_fields)} ({recall*100:.1f}%) | Found: {found} | Missing: {missing}")
    return recall, hits

img_orig = load_image(img_dir / "invoice_04_apex_may_blurry.jpg")

print("=== EXPERIMENTING WITH BLURRY IMAGE (invoice_04_apex_may_blurry.jpg) ===")
# 0. Baseline
eval_img(img_orig, "0. Baseline (Raw Image)")

# 1. 2x upscale
w, h = img_orig.size
img_2x = img_orig.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
eval_img(img_2x, "1. 2x Upscale (Lanczos)")

img_2x_bicubic = img_orig.resize((w * 2, h * 2), Image.Resampling.BICUBIC)
eval_img(img_2x_bicubic, "1b. 2x Upscale (Bicubic)")

# 2. Mild denoise (on 2x or 1x)
# Test bilateral filter
img_np = np.array(img_orig)
denoised_cv = cv2.bilateralFilter(img_np, 9, 75, 75)
img_denoise = Image.fromarray(denoised_cv)
eval_img(img_denoise, "2a. Mild Denoise (Bilateral)")

denoised_fast = cv2.fastNlMeansDenoisingColored(img_np, None, 5, 5, 7, 21)
img_denoise_fast = Image.fromarray(denoised_fast)
eval_img(img_denoise_fast, "2b. Mild Denoise (fastNlMeans)")

# 2x + Denoise
img_2x_np = np.array(img_2x)
denoised_2x = cv2.bilateralFilter(img_2x_np, 9, 50, 50)
img_2x_denoise = Image.fromarray(denoised_2x)
eval_img(img_2x_denoise, "2c. 2x Upscale + Bilateral Denoise")

# 3. Unsharp mask
def unsharp_mask(img_pil, radius=2, percent=150, threshold=3):
    return img_pil.filter(ImageFilter.UnsharpMask(radius=radius, percent=percent, threshold=threshold))

img_unsharp = unsharp_mask(img_orig, radius=2, percent=150, threshold=3)
eval_img(img_unsharp, "3a. Unsharp Mask only")

img_2x_unsharp = unsharp_mask(img_2x, radius=2, percent=150, threshold=3)
eval_img(img_2x_unsharp, "3b. 2x Upscale + Unsharp Mask")

img_2x_denoise_unsharp = unsharp_mask(img_2x_denoise, radius=2, percent=150, threshold=3)
eval_img(img_2x_denoise_unsharp, "3c. 2x + Denoise + Unsharp")

# Test contrast enhancement
enh = ImageEnhance.Contrast(img_2x).enhance(1.4)
enh = ImageEnhance.Sharpness(enh).enhance(1.8)
eval_img(enh, "4. 2x + Contrast 1.4 + Sharpness 1.8")
