"""图像预处理：灰度化、二值化、去噪。"""

import cv2
import numpy as np


def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"无法读取图像: {path}")
    return img


def estimate_stroke_width(binary: np.ndarray) -> float:
    """用距离变换估计中位笔画宽度（像素）。

    对二值图 (0/255) 前景做距离变换，取距离最大值的一半作为
    笔画半宽估计，用于自适应设置骨架剪枝阈值。
    """
    fg = (binary > 0).astype(np.uint8)
    dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    # 距离变换给出到最近背景的像素距离 → 半宽
    half_widths = dist[dist > 0]
    if len(half_widths) == 0:
        return 5.0
    # 用 80 分位数估计主要笔画半宽（抗小噪点干扰）
    return float(np.percentile(half_widths, 80))


def preprocess(img: np.ndarray, blur_ksize: int = 5) -> np.ndarray:
    """灰度化 → 中值滤波（去墨点）→ 高斯模糊 → Otsu二值化 → 中值滤波，
    返回二值图 (0/255)。
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 中值滤波先去除孤立暗/亮像素（墨点/纸纹）
    gray = cv2.medianBlur(gray, 7)
    if blur_ksize > 0:
        gray = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    denoised = cv2.medianBlur(binary, 3)
    # 形态学开运算：去除边界微小突起
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    denoised = cv2.morphologyEx(denoised, cv2.MORPH_OPEN, kernel)
    return denoised
