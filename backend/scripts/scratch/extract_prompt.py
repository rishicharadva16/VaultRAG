import json

log_path = r"C:\Users\RISHI\.gemini\antigravity-ide\brain\62f8602e-5e5f-4640-9dba-e43ddcf3b78d\.system_generated\logs\transcript_full.jsonl"
target = None
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        if '"step_index":10346' in line:
            target = line
            break

if target:
    data = json.loads(target)
    content = data.get("content", "")
    with open(r"D:\VaultRAG\backend\scripts\scratch\prompt_5e_fix_full.txt", "w", encoding="utf-8") as out:
        out.write(content)
    print("Found! Length:", len(content))
else:
    print("Not found by step_index 10346, searching for STEP 5e-fix...")
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if "STEP 5e-fix v2" in line and '"type":"USER_INPUT"' in line:
                data = json.loads(line)
                content = data.get("content", "")
                with open(r"D:\VaultRAG\backend\scripts\scratch\prompt_5e_fix_full.txt", "w", encoding="utf-8") as out:
                    out.write(content)
                print("Found via search! Step:", data.get("step_index"), "Length:", len(content))
                break
