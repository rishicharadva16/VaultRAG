from rapidocr_onnxruntime import RapidOCR
ocr = RapidOCR()
for fname in ['invoice_04_apex_may_blurry.jpg', 'invoice_05_rotated_scan.jpg', 'whiteboard_sprint.jpg']:
    p = rf'd:\VaultRAG\data\northwind\rag_demo_dataset\dataset\corpus\images\{fname}'
    res, _ = ocr(p)
    print(f'=== {fname} ===')
    for line in res or []:
        print(f'  {line[1]} ({line[2]:.2f})')
