"""图像预处理：灰度化、二值化、去噪。"""

import cv2
import numpy as np


def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"无法读取图像: {path}")
    return img


def preprocess(img: np.ndarray, blur_ksize: int = 5) -> np.ndarray:
    """灰度化 → 高斯模糊 → Otsu二值化 → 中值滤波，返回二值图 (0/255)。

    blur_ksize: 高斯核大小（奇数），3=轻微平滑，5=中等。大值让轮廓更平滑、
    骨架交叉区更干净，但可能丢失细节。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if blur_ksize > 0:
        gray = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    denoised = cv2.medianBlur(binary, 3)
    return denoised
