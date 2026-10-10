import json
import math
import sys
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.ocr.engine import ocr_image
from app.ocr.preprocess import preprocess_image, load_image

ds_path = settings.dataset_path()
img_dir = ds_path / "dataset" / "corpus" / "images"
gt_file = img_dir / "image_ground_truth.json"

with open(gt_file, "r", encoding="utf-8") as f:
    gt_data = json.load(f)

def compute_iou(box1, box2):
    x_left = max(box1[0], box2[0])
    y_top = max(box1[1], box2[1])
    x_right = min(box1[2], box2[2])
    y_bottom = min(box1[3], box2[3])
    if x_right <= x_left or y_bottom <= y_top:
        return 0.0
    inter = (x_right - x_left) * (y_bottom - y_top)
    area1 = max(0.0, (box1[2] - box1[0]) * (box1[3] - box1[1]))
    area2 = max(0.0, (box2[2] - box2[0]) * (box2[3] - box2[1]))
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0

img_path = img_dir / "invoice_05_rotated_scan.jpg"
orig_img = load_image(img_path)
orig_w, orig_h = orig_img.size

lines, processed_img, meta = ocr_image(img_path, preprocess=True)
deskew_angle = meta.get("deskew_angle", 0.0)
print(f"Deskew angle: {deskew_angle}, Original size: ({orig_w}, {orig_h}), Processed size: {processed_img.size}")

# GT boxes
gt_entry = gt_data["invoice_05_rotated_scan.jpg"]
gt_regions = gt_entry["text_regions"]

# BEFORE: un-mapped boxes (in processed_img coordinates)
ocr_boxes_before = []
for l in lines:
    xs = [pt[0] for pt in l.box]
    ys = [pt[1] for pt in l.box]
    ocr_boxes_before.append([min(xs), min(ys), max(xs), max(ys)])

hits_before = sum(1 for r in gt_regions if any(compute_iou(r["bbox"], ob) >= 0.5 for ob in ocr_boxes_before))
print(f"IoU hits BEFORE mapping: {hits_before}/{len(gt_regions)} ({hits_before/len(gt_regions)*100:.1f}%)")

# AFTER: mapped back via M_inv
center = (orig_w // 2, orig_h // 2)
M = cv2.getRotationMatrix2D(center, deskew_angle, 1.0)
M_inv = cv2.invertAffineTransform(M)

ocr_boxes_after = []
for l in lines:
    mapped_pts = []
    for pt in l.box:
        pt_arr = np.array([pt[0], pt[1], 1.0])
        mapped = M_inv @ pt_arr
        mapped_pts.append(mapped[:2])
    xs = [pt[0] for pt in mapped_pts]
    ys = [pt[1] for pt in mapped_pts]
    ocr_boxes_after.append([min(xs), min(ys), max(xs), max(ys)])

hits_after = sum(1 for r in gt_regions if any(compute_iou(r["bbox"], ob) >= 0.5 for ob in ocr_boxes_after))
print(f"IoU hits AFTER mapping: {hits_after}/{len(gt_regions)} ({hits_after/len(gt_regions)*100:.1f}%)")
