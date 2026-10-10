import pymupdf
import re
from pathlib import Path
from app.config import settings

def test():
    pdf_path = Path(r"D:\VaultRAG\data\northwind\rag_demo_dataset\dataset\corpus\pdfs\vendor_contract_apex.pdf")
    doc = pymupdf.open(str(pdf_path))
    page = doc[0]
    words = page.get_text("words")
    page_w = float(page.rect.width)
    page_h = float(page.rect.height)

    # Let's test a realistic multi-line passage from page 1:
    text = page.get_text("text")
    print("Page 1 full text sample:\n", text[:300])

    # Sample query highlight:
    hl = "Apex Logistics agrees to provide freight transportation services"
    hl_words = [re.sub(r"[^\w]", "", w.lower()) for w in hl.split() if re.sub(r"[^\w]", "", w.lower())]
    page_word_norms = [re.sub(r"[^\w]", "", w[4].lower()) for w in words]

    # Find longest contiguous match or sequence match:
    best_match = []
    # Test sliding window / exact subsequence first
    for i in range(len(page_word_norms) - len(hl_words) + 1):
        if page_word_norms[i:i+len(hl_words)] == hl_words:
            best_match = words[i:i+len(hl_words)]
            break

    print("Subsequence match found:", len(best_match) == len(hl_words))
    if best_match:
        lines = {}
        for m in best_match:
            key = (m[5], m[6])
            lines.setdefault(key, []).append(m)
        for k, l_words in lines.items():
            x0 = min(w[0] for w in l_words) / page_w
            y0 = min(w[1] for w in l_words) / page_h
            x1 = max(w[2] for w in l_words) / page_w
            y1 = max(w[3] for w in l_words) / page_h
            print("  Line rect:", {"x": round(x0, 4), "y": round(y0, 4), "w": round(x1-x0, 4), "h": round(y1-y0, 4)})

if __name__ == "__main__":
    test()
