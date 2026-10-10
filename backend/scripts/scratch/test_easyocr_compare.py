import json
import sys
import time
from pathlib import Path
import numpy as np

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.ocr.engine import ocr_image
from app.ocr.preprocess import load_image

ds_path = settings.dataset_path()
img_dir = ds_path / "dataset" / "corpus" / "images"
gt_file = img_dir / "image_ground_truth.json"

with open(gt_file, "r", encoding="utf-8") as f:
    gt_data = json.load(f)

img_files = sorted([p for p in img_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")])

def norm_str(s: str) -> str:
    return "".join(c.lower() for c in s if c.isalnum())

print("Loading EasyOCR Reader (CPU)...")
import easyocr
reader = easyocr.Reader(["en"], gpu=False, verbose=False)

print("\n" + "=" * 110)
print(f"{'OCR ENGINE COMPARISON: RapidOCR vs EasyOCR (10 Images)':^110}")
print("=" * 110)
print(f"{'IMAGE':<32} {'RAPID KF':<14} {'RAPID SEC':<12} {'EASY KF':<14} {'EASY SEC':<12} {'WINNER'}")
print("-" * 110)

rapid_recalls = []
rapid_times = []
easy_recalls = []
easy_times = []

for p in img_files:
    fname = p.name
    gt_entry = gt_data.get(fname, {})
    gt_regions = gt_entry.get("text_regions", [])
    key_fields = [r for r in gt_regions if r.get("field") is not None] or gt_regions

    # 1. RapidOCR (with standard preprocessing)
    t0 = time.time()
    rapid_lines, _, _ = ocr_image(p, preprocess=True)
    t_rapid = round(time.time() - t0, 2)
    rapid_full = norm_str(" ".join(l.text for l in rapid_lines))
    rapid_hits = sum(1 for kf in key_fields if norm_str(kf["text"]) in rapid_full)
    rapid_rec = rapid_hits / len(key_fields) if key_fields else 1.0

    # 2. EasyOCR (on original image)
    img_pil = load_image(p)
    t0 = time.time()
    easy_results = reader.readtext(np.array(img_pil))
    t_easy = round(time.time() - t0, 2)
    easy_full = norm_str(" ".join(r[1] for r in easy_results))
    easy_hits = sum(1 for kf in key_fields if norm_str(kf["text"]) in easy_full)
    easy_rec = easy_hits / len(key_fields) if key_fields else 1.0

    rapid_recalls.append(rapid_rec)
    rapid_times.append(t_rapid)
    easy_recalls.append(easy_rec)
    easy_times.append(t_easy)

    if rapid_rec > easy_rec:
        winner = "RapidOCR (Recall)"
    elif easy_rec > rapid_rec:
        winner = "EasyOCR (Recall)"
    elif t_rapid < t_easy:
        winner = "RapidOCR (Speed)"
    else:
        winner = "Tie"

    rap_str = f"{rapid_hits}/{len(key_fields)} ({rapid_rec*100:.1f}%)"
    eas_str = f"{easy_hits}/{len(key_fields)} ({easy_rec*100:.1f}%)"
    print(f"{fname:<32} {rap_str:<14} {t_rapid:<12.2f} {eas_str:<14} {t_easy:<12.2f} {winner}")

print("-" * 110)
avg_rapid_rec = sum(rapid_recalls) / len(rapid_recalls)
avg_easy_rec = sum(easy_recalls) / len(easy_recalls)
avg_rapid_time = sum(rapid_times) / len(rapid_times)
avg_easy_time = sum(easy_times) / len(easy_times)

print(f"Overall Average Recall: RapidOCR = {avg_rapid_rec*100:.2f}% | EasyOCR = {avg_easy_rec*100:.2f}%")
print(f"Overall Average Time  : RapidOCR = {avg_rapid_time:.2f}s    | EasyOCR = {avg_easy_time:.2f}s")
print("=" * 110)
