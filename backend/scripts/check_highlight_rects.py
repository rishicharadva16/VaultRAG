"""
Audit Highlight Rect Computation for all PDF citations produced by evaluation questions.
Calls GET /source/{chunk_id}/view?hl=... for every PDF citation and reports match statistics.
"""

import json
from pathlib import Path
from urllib.parse import quote
import urllib.request
import urllib.error

def main():
    base_url = "http://localhost:8000"

    # Login as admin to ensure read access across all corpus documents
    login_req = urllib.request.Request(
        f"{base_url}/auth/login",
        data=json.dumps({"email": "admin@northwind.example", "password": "changeme123"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(login_req) as resp:
        token = json.loads(resp.read())["access_token"]

    cache_file = Path(__file__).resolve().parent / "eval_answers_cache.json"
    if not cache_file.is_file():
        print(f"Error: eval_answers_cache.json not found at {cache_file}")
        return

    with open(cache_file, "r", encoding="utf-8") as f:
        cache_data = json.load(f)

    pdf_citations = []
    seen_chunk_hls = set()

    for q_key, entry in cache_data.items():
        citations = entry.get("citations", [])
        for c in citations:
            file_name = c.get("file", "")
            source_id = c.get("source_id", "")
            if file_name.endswith(".pdf") or source_id.startswith("pdf:"):
                chunk_id = c.get("chunk_id")
                highlights = c.get("highlights", [])
                hl_param = ",".join(f"{h['start']}-{h['end']}" for h in highlights if "start" in h and "end" in h)
                
                key = (chunk_id, hl_param)
                if key not in seen_chunk_hls:
                    seen_chunk_hls.add(key)
                    pdf_citations.append({
                        "chunk_id": chunk_id,
                        "file": file_name,
                        "page": c.get("page"),
                        "hl": hl_param,
                        "highlight_text": c.get("highlight_text", ""),
                        "question_key": q_key,
                    })

    print(f"Found {len(pdf_citations)} unique PDF citations across evaluation queries.\n")

    counts = {"exact": 0, "partial": 0, "none": 0}
    non_exact_cases = []

    for item in pdf_citations:
        chunk_id = item["chunk_id"]
        hl = item["hl"]
        quoted_id = quote(chunk_id, safe="")
        url = f"{base_url}/source/{quoted_id}/view"
        if hl:
            url += f"?hl={hl}"

        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )

        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
                match_val = data.get("match", "none")
                counts[match_val] = counts.get(match_val, 0) + 1

                if match_val != "exact":
                    non_exact_cases.append({
                        "chunk_id": chunk_id,
                        "file": item["file"],
                        "page": item["page"],
                        "match": match_val,
                        "rects_count": len(data.get("rects", [])),
                        "hl": hl,
                    })
        except urllib.error.HTTPError as e:
            counts["none"] = counts.get("none", 0) + 1
            non_exact_cases.append({
                "chunk_id": chunk_id,
                "file": item["file"],
                "page": item["page"],
                "match": "none (HTTP error)",
                "status": e.code,
            })

    total = sum(counts.values())
    exact_pct = (counts["exact"] / total * 100) if total else 0
    partial_pct = (counts["partial"] / total * 100) if total else 0
    none_pct = (counts["none"] / total * 100) if total else 0

    print("=" * 60)
    print("PDF HIGHLIGHT RECT COMPUTATION REPORT")
    print("=" * 60)
    print(f"Total Unique PDF Citations Audited: {total}")
    print(f"  Exact Matches:   {counts['exact']:3d} ({exact_pct:.1f}%)")
    print(f"  Partial Matches: {counts['partial']:3d} ({partial_pct:.1f}%)")
    print(f"  No Matches:      {counts['none']:3d} ({none_pct:.1f}%)")
    print("=" * 60)

    if non_exact_cases:
        print("\nNon-Exact Cases:")
        for idx, ne in enumerate(non_exact_cases, 1):
            reason = "Partial match (some words or table cells formatted differently)" if ne["match"] == "partial" else "No match found"
            print(f"  [{idx}] chunk_id={ne['chunk_id']} (file={ne.get('file')}, p.{ne.get('page')}): match={ne['match']} | {reason}")
    else:
        print("\nAll PDF citations achieved 100% exact alignment!")

if __name__ == "__main__":
    main()
