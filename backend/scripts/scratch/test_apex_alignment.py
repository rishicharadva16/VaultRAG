import pymupdf
import re
from pathlib import Path

pdf_path = Path(r"D:\VaultRAG\data\northwind\rag_demo_dataset\dataset\corpus\pdfs\vendor_contract_apex.pdf")
doc = pymupdf.open(str(pdf_path))
page = doc[0] # page 1
page_w = float(page.rect.width)
page_h = float(page.rect.height)
page_words = page.get_text("words")

hl_text = "2. Fees The Company shall pay the Vendor a fixed monthly service fee of Rs 4,00,000 (Rupees Four Lakh only), excluding GST at the applicable rate of 18%."

def normalize_token(w: str) -> str:
    return re.sub(r"[^\w]", "", w.lower())

hl_tokens = [normalize_token(w) for w in hl_text.split() if normalize_token(w)]
page_tokens = [normalize_token(w[4]) for w in page_words]

print("hl_tokens count:", len(hl_tokens))
print("page_tokens count:", len(page_tokens))

# Find match: sequence alignment / sliding window
best_match = []
best_score = 0
for i in range(len(page_tokens) - len(hl_tokens) + 1):
    matched_count = sum(1 for a, b in zip(hl_tokens, page_tokens[i:i+len(hl_tokens)]) if a == b)
    if matched_count > best_score:
        best_score = matched_count
        best_match = page_words[i:i+len(hl_tokens)]

match_ratio = best_score / len(hl_tokens)
print(f"Best match score: {best_score}/{len(hl_tokens)} ({match_ratio:.1%})")

# Group into lines
lines = {}
for w in best_match:
    # Key by block_no, line_no
    key = (w[5], w[6])
    lines.setdefault(key, []).append(w)

rects = []
for k, l_words in lines.items():
    x0 = min(w[0] for w in l_words) / page_w
    y0 = min(w[1] for w in l_words) / page_h
    x1 = max(w[2] for w in l_words) / page_w
    y1 = max(w[3] for w in l_words) / page_h
    rect = {
        "x": round(max(0.0, min(1.0, x0)), 4),
        "y": round(max(0.0, min(1.0, y0)), 4),
        "w": round(max(0.0, min(1.0, x1 - x0)), 4),
        "h": round(max(0.0, min(1.0, y1 - y0)), 4),
    }
    rects.append(rect)
    line_str = " ".join(w[4] for w in l_words)
    print(f"Line [{k}]: {rect} -> {line_str}")

print(f"Total line rects: {len(rects)}")
