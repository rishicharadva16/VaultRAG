import os, glob, json, time
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()
img_dir = r"d:\VaultRAG\data\northwind\rag_demo_dataset\dataset\corpus\images"
gt_file = os.path.join(img_dir, "image_ground_truth.json")
with open(gt_file, "r", encoding="utf-8") as f:
    gt_data = json.load(f)

imgs = sorted(glob.glob(os.path.join(img_dir, "*.*")))
imgs = [i for i in imgs if not i.endswith(".json")]

print(f"{'IMAGE':<35} {'GT':<4} {'OCR':<4} {'CONF':<6} {'TIME':<6}")
print("-" * 60)

for p in imgs:
    fname = os.path.basename(p)
    t0 = time.time()
    res, el = ocr(p)
    dt = time.time() - t0
    lines = len(res) if res else 0
    conf = sum(x[2] for x in res) / lines if lines else 0.0
    gt_lines = len(gt_data.get(fname, {}).get("text_regions", []))
    print(f"{fname:<35} {gt_lines:<4} {lines:<4} {conf:<6.3f} {dt:<6.2f}s")
