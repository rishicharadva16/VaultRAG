import math
import numpy as np

def forward_pil_rot(x, y, angle, size_before, size_after):
    th = math.radians(angle)
    c, s = math.cos(th), math.sin(th)
    cx0, cy0 = size_before[0] / 2.0, size_before[1] / 2.0
    cx1, cy1 = size_after[0] / 2.0, size_after[1] / 2.0
    dx, dy = x - cx0, y - cy0
    return dx * c + dy * s + cx1, -dx * s + dy * c + cy1

def inverse_pil_rot(x_rot, y_rot, angle, size_before, size_after):
    th = math.radians(angle)
    c, s = math.cos(th), math.sin(th)
    cx0, cy0 = size_before[0] / 2.0, size_before[1] / 2.0
    cx1, cy1 = size_after[0] / 2.0, size_after[1] / 2.0
    dx1, dy1 = x_rot - cx1, y_rot - cy1
    # Inverse rotation matrix has transpose: [c, -s; s, c]
    x_orig = dx1 * c - dy1 * s + cx0
    y_orig = dx1 * s + dy1 * c + cy0
    return x_orig, y_orig

# Test with angle = 7.0 and size_before = (900, 1200)
from PIL import Image
img = Image.new("RGB", (900, 1200))
rot = img.rotate(7.0, expand=True)
size_before = img.size
size_after = rot.size

pt = (350.0, 450.0)
rot_pt = forward_pil_rot(pt[0], pt[1], 7.0, size_before, size_after)
rec_pt = inverse_pil_rot(rot_pt[0], rot_pt[1], 7.0, size_before, size_after)

print("Original:", pt)
print("Rotated:", rot_pt)
print("Recovered:", rec_pt)
assert np.isclose(pt[0], rec_pt[0]) and np.isclose(pt[1], rec_pt[1])
print("SUCCESS: forward and inverse PIL rotation match perfectly!")
