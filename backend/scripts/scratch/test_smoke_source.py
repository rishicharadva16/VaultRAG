import urllib.request
import urllib.error
import json
from urllib.parse import quote

def get_token(email, password="changeme123"):
    req = urllib.request.Request(
        'http://localhost:8000/auth/login',
        data=json.dumps({'email': email, 'password': password}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    res = urllib.request.urlopen(req)
    return json.loads(res.read())['access_token']

token_karan = get_token("karan.shah@northwind.example")
token_asha = get_token("asha.patel@northwind.example")

chunk_id = "vendor_contract_apex-p1-c1"
quoted_id = quote(chunk_id, safe='')

print("=== 1. KARAN (FINANCE ADMIN - AUTHORIZED) ===")
# 1. View
req_v = urllib.request.Request(
    f"http://localhost:8000/source/{quoted_id}/view?hl=437-590",
    headers={"Authorization": f"Bearer {token_karan}"}
)
res_v = urllib.request.urlopen(req_v)
view_data = json.loads(res_v.read())
print("Karan View status:", res_v.status)
print("  kind:", view_data.get("kind"))
print("  file:", view_data.get("file"))
print("  page:", view_data.get("page"))
print("  match:", view_data.get("match"))
print("  page_image_url:", view_data.get("page_image_url"))
print("  rects count:", len(view_data.get("rects", [])))
for r in view_data.get("rects", []):
    print("    rect:", r)

# 2. Page image
req_img = urllib.request.Request(
    f"http://localhost:8000/source/{quoted_id}/page.png?page=1",
    headers={"Authorization": f"Bearer {token_karan}"}
)
res_img = urllib.request.urlopen(req_img)
img_bytes = res_img.read()
print("Karan Page Image status:", res_img.status)
print("  content-type:", res_img.headers.get("content-type"))
print("  cache-control:", res_img.headers.get("cache-control"))
print("  bytes len:", len(img_bytes))

# 3. Pages
req_p = urllib.request.Request(
    f"http://localhost:8000/source/{quoted_id}/pages",
    headers={"Authorization": f"Bearer {token_karan}"}
)
res_p = urllib.request.urlopen(req_p)
pages_data = json.loads(res_p.read())
print("Karan Pages status:", res_p.status)
print("  page_count:", pages_data.get("page_count"))
print("  readable_pages:", pages_data.get("readable_pages"))

print("\n=== 2. ASHA (EMPLOYEE - FORBIDDEN) ===")
for ep in [f"/source/{quoted_id}/view?hl=437-590", f"/source/{quoted_id}/page.png?page=1", f"/source/{quoted_id}/pages"]:
    try:
        req_a = urllib.request.Request(
            f"http://localhost:8000{ep}",
            headers={"Authorization": f"Bearer {token_asha}"}
        )
        urllib.request.urlopen(req_a)
        print(f"ERROR: Asha unexpectedly accessed {ep}")
    except urllib.error.HTTPError as e:
        print(f"Asha {ep} status: {e.code} (detail: {e.read().decode('utf-8')})")

print("\n=== 3. NONEXISTENT CHUNK ===")
try:
    req_none = urllib.request.Request(
        "http://localhost:8000/source/nonexistent_chunk_9999/view",
        headers={"Authorization": f"Bearer {token_karan}"}
    )
    urllib.request.urlopen(req_none)
except urllib.error.HTTPError as e:
    print(f"Nonexistent status: {e.code} (detail: {e.read().decode('utf-8')})")
