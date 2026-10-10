import cv2
import numpy as np

# Test affine inverse
w, h = 1000, 1200
center = (w // 2, h // 2)
angle = -7.0
M = cv2.getRotationMatrix2D(center, angle, 1.0)
M_inv = cv2.invertAffineTransform(M)

# Original point
pt_orig = np.array([200.0, 300.0, 1.0])
pt_deskew = M @ pt_orig
pt_recovered = M_inv @ np.array([pt_deskew[0], pt_deskew[1], 1.0])
print("Original:", pt_orig[:2], "Deskewed:", pt_deskew, "Recovered:", pt_recovered)
assert np.allclose(pt_orig[:2], pt_recovered)
print("SUCCESS: Inverse transform exact match!")
