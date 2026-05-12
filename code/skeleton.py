"""骨架提取算法。

提供两种方法：
- zhang_suen: 手工实现的 Zhang-Suen（参考基线）
- skeletonize: 使用 skimage.morphology.thin（推荐，对复杂字形噪点少 20 倍）
"""

import numpy as np
from skimage.morphology import thin


def skeletonize(binary: np.ndarray) -> np.ndarray:
    """输入二值图 (0/255, 前景白色)，返回骨架二值图 (0/255)。

    使用 skimage 的 morphological thinning，相比 Zhang-Suen 在斜线、
    粗笔画上的交叉点噪点少一个数量级。
    """
    skel = thin(binary > 0, max_num_iter=100)
    return (skel.astype(np.uint8)) * 255


def zhang_suen(binary: np.ndarray) -> np.ndarray:
    """输入二值图 (0/255, 前景白色)，返回骨架二值图 (0/255)。"""
    img = (binary > 0).astype(np.uint8)
    skeleton = np.zeros_like(img)
    h, w = img.shape

    while True:
        # 子迭代 1
        s1 = _thin_iteration(img, 0)
        # 子迭代 2
        s2 = _thin_iteration(img, 1)
        img = s2
        if np.array_equal(s1, s2):
            skeleton = s2
            break

    return (skeleton * 255).astype(np.uint8)


def _neighbors(img: np.ndarray, y: int, x: int) -> list[int]:
    """返回 P1 的 8 邻域 P2..P9 像素值（0 或 1），顺序为 P2(上) 顺时针一圈。"""
    h, w = img.shape
    coords = [
        (y - 1, x),     # P2
        (y - 1, x + 1), # P3
        (y, x + 1),     # P4
        (y + 1, x + 1), # P5
        (y + 1, x),     # P6
        (y + 1, x - 1), # P7
        (y, x - 1),     # P8
        (y - 1, x - 1), # P9
    ]
    return [img[ny, nx] if 0 <= ny < h and 0 <= nx < w else 0 for ny, nx in coords]


def _transitions(neighbors: list[int]) -> int:
    """计算 P2→P3→...→P9→P2 中 0→1 转移次数。"""
    n = neighbors + [neighbors[0]]
    count = 0
    for i in range(8):
        if n[i] == 0 and n[i + 1] == 1:
            count += 1
    return count


def _thin_iteration(img: np.ndarray, iteration: int) -> np.ndarray:
    h, w = img.shape
    marker = np.zeros_like(img)

    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if img[y, x] != 1:
                continue

            nb = _neighbors(img, y, x)
            p2, p3, p4, p5, p6, p7, p8, p9 = nb
            n_sum = sum(nb)
            trans = _transitions(nb)

            # 共同条件
            if not (2 <= n_sum <= 6):
                continue
            if trans != 1:
                continue

            if iteration == 0:
                # 子迭代1: P2*P4*P6 == 0 且 P4*P6*P8 == 0
                if p2 * p4 * p6 == 0 and p4 * p6 * p8 == 0:
                    marker[y, x] = 1
            else:
                # 子迭代2: P2*P4*P8 == 0 且 P2*P6*P8 == 0
                if p2 * p4 * p8 == 0 and p2 * p6 * p8 == 0:
                    marker[y, x] = 1

    result = img.copy()
    result[marker == 1] = 0
    return result
