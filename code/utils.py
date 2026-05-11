"""图像预处理：灰度化、二值化、去噪。"""

import cv2
import numpy as np


def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"无法读取图像: {path}")
    return img


def preprocess(img: np.ndarray) -> np.ndarray:
    """灰度化 → Otsu二值化 → 中值滤波去噪，返回二值图 (0/255)。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    denoised = cv2.medianBlur(binary, 3)
    return denoised
