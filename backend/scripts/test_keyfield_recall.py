import os, json
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()
img_dir = r"d:\VaultRAG\data\northwind\rag_demo_dataset\dataset\corpus\images"

eval_checks = {
    "invoice_01_apex_apr.png": ["INV-APX-0412", "4,72,000", "06 May 2026", "Apex Logistics"],
    "invoice_02_brightbyte.png": ["INV-BB-2291", "1,18,000", "PO-2026-077", "BrightByte"],
    "invoice_03_quickprint.png": ["INV-QP-0388", "8,260", "27 Jul 2026", "QuickPrint"],
    "invoice_04_apex_may_blurry.jpg": ["INV-APX-0431", "4,95,600", "20,000", "4,00,000"],
    "invoice_05_rotated_scan.jpg": ["INV-SGS-5517", "3,540", "02 Aug 2026", "Shree Ganesh"],
    "purchase_order_PO-2026-077.png": ["PO-2026-077", "1,18,000", "02 Jul 2026", "DevTools Suite"],
    "receipt_hotel_lotus.png": ["LGH-PN-20931", "12,320", "5,500", "Lotus Grand Hotel", "Sneha Reddy"],
    "id_card_E1004.png": ["E1004", "Asha Patel", "Software Engineer", "Engineering"],
    "id_card_E1010.png": ["E1010", "Sneha Reddy", "DevOps Engineer", "Engineering"],
    "whiteboard_sprint.jpg": ["SPRINT 14 PLAN", "15 Nov", "Asha", "Ravi", "Apex SLA", "Hire 12"]
}

for fname, fields in eval_checks.items():
    p = os.path.join(img_dir, fname)
    res, _ = ocr(p)
    full_text = " ".join(line[1] for line in res or [])
    norm_text = full_text.lower().replace(" ", "").replace(".", "").replace(",", "")
    print(f"\n=== {fname} ===")
    for fld in fields:
        norm_fld = fld.lower().replace(" ", "").replace(".", "").replace(",", "")
        found = norm_fld in norm_text
        print(f"  [{'OK' if found else 'MISS'}] {fld}")
