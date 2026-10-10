import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PIL import Image, ImageDraw
from app.ocr.engine import ocr_image

# 1. Create synthetic image
w, h = 800, 500
img = Image.new("RGB", (w, h), (255, 255, 255))
draw = ImageDraw.Draw(img)
# Draw text
text = "INVOICE NUMBER: INV-TEST-9988"
draw.text((100, 200), text, fill=(0, 0, 0))

# 2. Rotate by -7 degrees (which means 7 degrees clockwise in some conventions, or counter-clockwise)
angle = -7.0
rotated_img = img.rotate(angle, expand=True, fillcolor=(255, 255, 255))
rot_w, rot_h = rotated_img.size

# 3. Run OCR pipeline
lines, proc_img, meta = ocr_image(rotated_img, preprocess=True)
print(f"Recognized {len(lines)} lines")
for l in lines:
    print(f"  Text: {l.text!r}, Box: {l.box}")
    # Verify that box coordinates are within rotated_img boundaries
    xs = [pt[0] for pt in l.box]
    ys = [pt[1] for pt in l.box]
    assert 0 <= min(xs) <= rot_w, f"x min {min(xs)} out of bounds {rot_w}"
    assert 0 <= min(ys) <= rot_h, f"y min {min(ys)} out of bounds {rot_h}"
    print(f"  xs: [{min(xs):.1f}, {max(xs):.1f}], ys: [{min(ys):.1f}, {max(ys):.1f}]")

print("SUCCESS: Synthetic rotated image test verified!")
