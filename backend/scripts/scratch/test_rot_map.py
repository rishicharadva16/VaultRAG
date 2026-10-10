import numpy as np
import cv2
from PIL import Image

def test_rotation_inversion():
    w, h = 500, 700
    img = Image.new("RGB", (w, h), (255, 255, 255))
    x0, y0 = 120.0, 240.0
    
    for angle in [90, 180, 270]:
        rot = img.rotate(angle, expand=True)
        w_rot, h_rot = rot.size
        
        # Test mapping
        if angle == 90:
            # In PIL rotate(90), (x, y) -> (y, w - 1 - x)? Let's check!
            pass

test_rotation_inversion()
