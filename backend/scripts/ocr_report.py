"""
Measure OCR Quality on VaultRAG dataset images.
Calculates key-field recall and box IoU > 0.5 overlap against ground truth.
Outputs a structured table and summary metrics.
"""

import json
import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.ocr.engine import ocr_image
from app.ocr.preprocess import preprocess_image

HARD_IMAGES = {
    "invoice_04_apex_may_blurry.jpg",
    "invoice_05_rotated_scan.jpg",
    "whiteboard_sprint.jpg",
}


def compute_iou(box1: list[float], box2: list[float]) -> float:
    """Compute IoU between [x0, y0, x1, y1] and [x0, y0, x1, y1]."""
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


def norm_str(s: str) -> str:
    """Normalize string for robust token matching."""
    return "".join(c.lower() for c in s if c.isalnum())


def run_ocr_report():
    ds_path = settings.dataset_path()
    candidates = [
        ds_path / "dataset" / "corpus" / "images",
        ds_path / "corpus" / "images",
    ]
    img_dir = next((c for c in candidates if c.is_dir()), candidates[0])
    gt_file = img_dir / "image_ground_truth.json"

    if not gt_file.exists():
        print(f"Ground truth file not found at {gt_file}")
        sys.exit(1)

    with open(gt_file, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    img_files = sorted(
        [p for p in img_dir.iterdir() if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".jpeg")]
    )

    print("=" * 115)
    print(f"{'VAULTRAG OCR QUALITY & KEY-FIELD RECALL REPORT':^115}")
    print("=" * 115)
    print(
        f"{'IMAGE':<32} {'ROT':<4} {'PREPROCESS':<18} {'LINES':<6} {'CONF':<6} {'SEC':<6} "
        f"{'KF RECALL':<14} {'BOX IoU>0.5':<12}"
    )
    print("-" * 115)

    all_kf_recalls = []
    hard_kf_recalls = []
    all_box_ious = []
    hard_box_ious = []

    report_rows = []

    for img_path in img_files:
        fname = img_path.name
        gt_entry = gt_data.get(fname, {})
        gt_regions = gt_entry.get("text_regions", [])

        # Run OCR with full preprocessing
        t0 = time.time()
        lines, processed_img, meta = ocr_image(img_path, preprocess=True)
        elapsed = round(time.time() - t0, 3)

        num_lines = len(lines)
        mean_conf = round(sum(l.confidence for l in lines) / num_lines, 3) if num_lines else 0.0
        applied_str = ",".join(meta.get("steps_applied", [])) or "none"
        rot_val = meta.get("rotation_angle", 0)

        # 1. Key-Field Recall
        # Collect distinct expected key fields (items with non-null 'field')
        key_fields = [r for r in gt_regions if r.get("field") is not None]
        if not key_fields:
            # Fall back to all text regions if no specific field labels
            key_fields = gt_regions

        ocr_full_text = " ".join(l.text for l in lines)
        ocr_norm = norm_str(ocr_full_text)

        kf_hits = 0
        for kf in key_fields:
            exp_text = kf["text"]
            norm_exp = norm_str(exp_text)
            if norm_exp in ocr_norm:
                kf_hits += 1

        kf_recall = (kf_hits / len(key_fields)) if key_fields else 1.0
        kf_str = f"{kf_hits}/{len(key_fields)} ({kf_recall*100:.1f}%)"

        # 2. Box IoU > 0.5 hit rate
        # l.box is now in the coordinate system of the ORIGINAL image.
        ocr_boxes_xyxy = []
        for l in lines:
            xs = [pt[0] for pt in l.box]
            ys = [pt[1] for pt in l.box]
            ocr_boxes_xyxy.append([min(xs), min(ys), max(xs), max(ys)])

        box_hits = 0
        for r in gt_regions:
            gt_b = r.get("bbox", [])
            if len(gt_b) == 4:
                has_hit = any(compute_iou(gt_b, ob) >= 0.5 for ob in ocr_boxes_xyxy)
                if has_hit:
                    box_hits += 1

        box_rate = (box_hits / len(gt_regions)) if gt_regions else 1.0
        box_str = f"{box_hits}/{len(gt_regions)} ({box_rate*100:.1f}%)"

        all_kf_recalls.append(kf_recall)
        all_box_ious.append(box_rate)

        is_hard = fname in HARD_IMAGES
        if is_hard:
            hard_kf_recalls.append(kf_recall)
            hard_box_ious.append(box_rate)

        row_data = {
            "image": fname,
            "rotation": rot_val,
            "preprocessing": applied_str,
            "lines": num_lines,
            "conf": mean_conf,
            "seconds": elapsed,
            "kf_recall": kf_recall,
            "kf_str": kf_str,
            "box_rate": box_rate,
            "box_str": box_str,
            "is_hard": is_hard,
        }
        report_rows.append(row_data)

        flag = " [HARD]" if is_hard else ""
        print(
            f"{fname:<32} {rot_val:<4} {applied_str:<18} {num_lines:<6} {mean_conf:<6.3f} {elapsed:<6.2f} "
            f"{kf_str:<14} {box_str:<12}{flag}"
        )

    avg_kf_all = sum(all_kf_recalls) / len(all_kf_recalls) if all_kf_recalls else 0.0
    avg_kf_hard = sum(hard_kf_recalls) / len(hard_kf_recalls) if hard_kf_recalls else 0.0
    avg_box_all = sum(all_box_ious) / len(all_box_ious) if all_box_ious else 0.0
    avg_box_hard = sum(hard_box_ious) / len(hard_box_ious) if hard_box_ious else 0.0

    print("-" * 115)
    print(f"Overall Average Key-Field Recall: {avg_kf_all*100:.2f}% (10 images)")
    print(f"Hard Images Key-Field Recall:     {avg_kf_hard*100:.2f}% (3 images: blurry, rotated, whiteboard)")
    print(f"Overall Box IoU > 0.5 Hit Rate:   {avg_box_all*100:.2f}%")
    print(f"Hard Images Box IoU Hit Rate:     {avg_box_hard*100:.2f}%")
    print("=" * 115)


if __name__ == "__main__":
    run_ocr_report()
