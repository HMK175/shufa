"""骨架提取算法。

提供两种方法：
- zhang_suen: 手工实现的 Zhang-Suen（参考基线）
- skeletonize: 使用 skimage.morphology.thin（推荐，对复杂字形噪点少 20 倍）
"""

import numpy as np
from skimage.morphology import thin
from scipy.ndimage import binary_dilation


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


def smooth_junctions(skeleton: np.ndarray) -> np.ndarray:
    """对骨架交叉区做局部膨胀→细化，平滑交叉点拓扑。

    抹掉交叉核心像素后膨胀周围骨架，重新细化。
    边界外的原始骨架充当锚点，确保细化后自然连通。
    """
    from collections import defaultdict

    binary = skeleton > 0
    ys, xs = np.where(binary)
    pts_set = set(zip(ys, xs))

    graph = defaultdict(list)
    for y, x in pts_set:
        for ny, nx in _eight_neighbors(y, x):
            if (ny, nx) in pts_set:
                graph[(y, x)].append((ny, nx))

    junctions = {pt for pt, nb in graph.items() if len(nb) >= 3}
    if len(junctions) <= 1:
        return skeleton

    # 8-连通聚类
    visited = set()
    components = []
    for pt in junctions:
        if pt in visited:
            continue
        comp = set()
        stack = [pt]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            for nb in graph.get(cur, []):
                if nb in junctions and nb not in visited:
                    stack.append(nb)
        components.append(comp)

    result = skeleton.copy()
    H, W = skeleton.shape

    for comp in components:
        if len(comp) <= 1:
            continue

        ys_c = [p[0] for p in comp]
        xs_c = [p[1] for p in comp]
        margin = 5
        min_y, max_y = max(0, min(ys_c) - margin), min(H, max(ys_c) + margin + 1)
        min_x, max_x = max(0, min(xs_c) - margin), min(H, max(xs_c) + margin + 1)

        patch = result[min_y:max_y, min_x:max_x].copy()

        # 抹掉交叉核心像素（只去掉交叉像素，保留周围骨架当锚点）
        for cy, cx in comp:
            py, px = cy - min_y, cx - min_x
            if 0 <= py < patch.shape[0] and 0 <= px < patch.shape[1]:
                patch[py, px] = 0

        # 膨胀 → 细化（锚点骨架确保连通性）
        dilated = binary_dilation(patch > 0, iterations=3)
        cleaned = thin(dilated, max_num_iter=20)
        cleaned_u8 = (cleaned.astype(np.uint8)) * 255

        result[min_y:max_y, min_x:max_x] = cleaned_u8

    return result


def _eight_neighbors(y: int, x: int):
    return [
        (y - 1, x), (y - 1, x + 1), (y, x + 1), (y + 1, x + 1),
        (y + 1, x), (y + 1, x - 1), (y, x - 1), (y - 1, x - 1),
    ]
