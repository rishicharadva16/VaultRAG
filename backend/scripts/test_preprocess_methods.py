import cv2
import numpy as np
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()

def deskew(img_cv):
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    # Threshold to binary inverted
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    # Find all foreground pixels
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return img_cv, 0.0
    angle = cv2.minAreaRect(coords)[-1]
    # minAreaRect angle is [-90, 0)
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) > 15: # only small angles
        # try Hough lines instead
        lines = cv2.HoughLinesP(thresh, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
        angles = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                ang = np.degrees(np.arctan2(y2 - y1, x2 - x1))
                if abs(ang) < 15:
                    angles.append(ang)
        if angles:
            angle = float(np.median(angles))
        else:
            angle = 0.0

    if abs(angle) > 0.5:
        (h, w) = img_cv.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img_cv, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated, angle
    return img_cv, 0.0

def test_preprocess():
    p_rot = r"d:\VaultRAG\data\northwind\rag_demo_dataset\dataset\corpus\images\invoice_05_rotated_scan.jpg"
    img_cv = cv2.imread(p_rot)
    res_orig, _ = ocr(img_cv)
    print("Rotated scan orig lines:", len(res_orig) if res_orig else 0)
    
    deskewed, ang = deskew(img_cv)
    print(f"Detected deskew angle: {ang:.2f}")
    res_deskew, _ = ocr(deskewed)
    print("Rotated scan deskewed lines:", len(res_deskew) if res_deskew else 0)

    # Test blurry image enhancement
    p_blur = r"d:\VaultRAG\data\northwind\rag_demo_dataset\dataset\corpus\images\invoice_04_apex_may_blurry.jpg"
    img_b = Image.open(p_blur)
    res_b_orig, _ = ocr(np.array(img_b))
    print("Blurry orig lines:", len(res_b_orig) if res_b_orig else 0)
    
    # Sharpness / CLAHE
    enh = ImageEnhance.Sharpness(img_b).enhance(2.0)
    enh = ImageEnhance.Contrast(enh).enhance(1.5)
    res_enh, _ = ocr(np.array(enh))
    print("Blurry enhanced lines:", len(res_enh) if res_enh else 0)

test_preprocess()
