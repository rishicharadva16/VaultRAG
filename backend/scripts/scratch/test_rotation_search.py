import json
import sys
from pathlib import Path
from PIL import Image

backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.ocr.engine import _get_rapid_ocr
from app.ocr.preprocess import load_image

ds_path = settings.dataset_path()
img_dir = ds_path / "dataset" / "corpus" / "images"
img_files = sorted([p for p in img_dir.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")])

def coarse_ocr(img):
    import numpy as np
    engine = _get_rapid_ocr()
    res, _ = engine(np.array(img))
    if not res:
        return []
    return [[r[0], r[1], float(r[2])] for r in res]

print("=== ROTATION SEARCH (0 / 90 / 180 / 270) ACROSS ALL 10 IMAGES ===")
print(f"{'IMAGE':<35} {'SCORE 0':<12} {'SCORE 90':<12} {'SCORE 180':<12} {'SCORE 270':<12} {'CHOSEN ANGLE'}")
print("-" * 95)

rotation_results = {}

for p in img_files:
    fname = p.name
    img = load_image(p)
    w, h = img.size
    scale = min(1.0, 600.0 / max(w, h))
    thumb = img.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
    
    scores = {}
    for angle in [0, 90, 180, 270]:
        rot_img = thumb.rotate(angle, expand=True) if angle != 0 else thumb
        res = coarse_ocr(rot_img)
        if not res:
            scores[angle] = 0.0
        else:
            confs = [r[2] for r in res]
            mean_c = sum(confs) / len(confs)
            scores[angle] = round(len(res) * mean_c, 2)
            
    best_ang = max(scores, key=lambda a: scores[a])
    rotation_results[fname] = {"scores": scores, "chosen": best_ang}
    print(f"{fname:<35} {scores[0]:<12.2f} {scores[90]:<12.2f} {scores[180]:<12.2f} {scores[270]:<12.2f} {best_ang} deg")
