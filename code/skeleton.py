"""骨架提取算法。

提供两种方法：
- zhang_suen: 手工实现的 Zhang-Suen（参考基线）
- skeletonize: 使用 skimage.morphology.skeletonize（中轴变换，1像素宽）
"""

import numpy as np
from skimage.morphology import skeletonize as _skel_medial
from scipy.ndimage import binary_dilation
from stroke import compute_nc


def skeletonize(binary: np.ndarray) -> np.ndarray:
    """输入二值图 (0/255, 前景白色)，返回骨架二值图 (0/255)。

    Iterative thinning + 断裂小环（消除拐点三角凸起）。
    """
    from skimage.morphology import thin
    skel = thin(binary > 0, max_num_iter=300)
    skel = _break_small_loops(skel, max_len=6, min_deviation=0.5)
    return (skel.astype(np.uint8)) * 255


def _break_small_loops(skel: np.ndarray, max_len: int = 6,
                       min_deviation: float = 0.5) -> np.ndarray:
    """断裂长度≤max_len 且有尖锐拐角的小环（thin 在拐点产生的三角/菱形）。

    安全约束：环必须是简单环（除首尾外所有点 deg=2），
    且断裂后不产生新的孤立点。
    """
    from stroke import build_skeleton_graph
    graph = build_skeleton_graph(skel)
    if not graph:
        return skel

    result = skel.copy()
    juncs = {pt for pt, nb in graph.items() if len(nb) >= 3}
    broken = set()

    for start in juncs:
        if start in broken:
            continue
        for nb in graph[start]:
            queue = [(nb, [start, nb])]
            visited = {start, nb}
            while queue:
                cur, path = queue.pop(0)
                if len(path) > max_len:
                    continue
                for nxt in graph.get(cur, []):
                    if nxt == start and len(path) >= 3:
                        # 检查是否简单环（中间点全 deg=2）
                        if any(len(graph.get(p, [])) > 2 for p in path[1:]):
                            continue
                        # 找方向偏离最大的点
                        best_pt, best_dev = None, -1.0
                        for i, pt in enumerate(path):
                            prev_pt = path[(i - 1) % len(path)]
                            next_pt = path[(i + 1) % len(path)]
                            v_in = np.array(pt) - np.array(prev_pt)
                            v_out = np.array(next_pt) - np.array(pt)
                            n_in = np.linalg.norm(v_in.astype(float))
                            n_out = np.linalg.norm(v_out.astype(float))
                            if n_in < 1e-6 or n_out < 1e-6:
                                continue
                            dev = 1.0 - abs(np.dot(v_in/n_in, v_out/n_out))
                            if dev > best_dev:
                                best_dev = dev
                                best_pt = pt
                        # 只断够尖锐的
                        if best_pt and best_dev > min_deviation:
                            y, x = int(best_pt[0]), int(best_pt[1])
                            # 安全检查：去掉后邻居未断开
                            before_nb = len(graph.get(best_pt, []))
                            if before_nb >= 2:
                                result[y, x] = 0
                                broken.add(best_pt)
                        continue
                    if nxt not in visited and nxt not in broken:
                        visited.add(nxt)
                        queue.append((nxt, path + [nxt]))

    return result


def _draw_line(img: np.ndarray, y1: int, x1: int, y2: int, x2: int, value: int = 255):
    """Bresenham 直线绘制（就地修改）。"""
    H, W = img.shape
    dy = abs(y2 - y1)
    dx = abs(x2 - x1)
    sy = 1 if y1 < y2 else -1
    sx = 1 if x1 < x2 else -1
    err = dx - dy
    cy, cx = y1, x1
    while True:
        if 0 <= cy < H and 0 <= cx < W:
            img[cy, cx] = value
        if cy == y2 and cx == x2:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy


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
        cleaned = _skel_medial(dilated)
        cleaned_u8 = (cleaned.astype(np.uint8)) * 255

        result[min_y:max_y, min_x:max_x] = cleaned_u8

    return result


def straighten_junctions(skeleton: np.ndarray, angle_threshold: float = 25.0,
                         walk_steps: int = 15) -> np.ndarray:
    """在交叉区用直线连接共线分支，防止竖笔穿过交叉区时弯曲。

    采用非破坏性方法：不擦除原有骨架像素，直接在共线分支入口点之间
    叠加直线，然后局部细化清理冗余像素。这样保证连通性不丢失。
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

    # 8-连通聚类交叉区
    visited = set()
    junc_comps = []
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
        junc_comps.append(comp)

    result = skeleton.copy()

    for comp in junc_comps:
        branches = []  # [(path_list, direction_vec, entry_pt)]
        seen_starts = set()

        for jpt in comp:
            for nb in graph.get(jpt, []):
                if nb in comp:
                    continue
                path = [nb]
                prev = jpt
                cur = nb
                for _ in range(walk_steps - 1):
                    nxt = None
                    for n in graph.get(cur, []):
                        if n != prev and n not in comp:
                            nxt = n
                            break
                    if nxt is None:
                        break
                    path.append(nxt)
                    prev, cur = cur, nxt
                if len(path) < 3:
                    continue
                key = (path[0], path[-1]) if path[0] < path[-1] else (path[-1], path[0])
                if key in seen_starts:
                    continue
                seen_starts.add(key)
                approach_pts = np.array(path).astype(float)
                direction = _pca_direction_vec(approach_pts)
                branches.append((path, direction, path[0]))

        if len(branches) < 2:
            continue

        # 配对共线分支
        cos_threshold = np.cos(np.radians(angle_threshold))
        paired = set()
        straight_lines = []

        for i in range(len(branches)):
            if i in paired:
                continue
            path_i, dir_i, entry_i = branches[i]
            best_j, best_cos = None, -1.0
            for j in range(len(branches)):
                if j == i or j in paired:
                    continue
                path_j, dir_j, entry_j = branches[j]
                cos_abs = abs(np.dot(dir_i, dir_j))
                if cos_abs > best_cos and cos_abs > cos_threshold:
                    best_cos = cos_abs
                    best_j = j
            if best_j is not None:
                path_j, dir_j, entry_j = branches[best_j]
                straight_lines.append((entry_i, entry_j))
                paired.add(i)
                paired.add(best_j)

        if not straight_lines:
            continue

        # 直接在骨架上叠加直线（不擦除原有像素，保证连通性）
        for (y1, x1), (y2, x2) in straight_lines:
            _draw_line(result, y1, x1, y2, x2, value=255)

        # 局部细化清理冗余像素（直线被叠加后细化产生更直的骨架）
        ys_c = [p[0] for p in comp]
        xs_c = [p[1] for p in comp]
        margin = 6
        min_y = max(0, min(ys_c) - margin)
        max_y = min(result.shape[0], max(ys_c) + margin + 1)
        min_x = max(0, min(xs_c) - margin)
        max_x = min(result.shape[1], max(xs_c) + margin + 1)

        patch = result[min_y:max_y, min_x:max_x]
        cleaned = _skel_medial(patch > 0)
        cleaned_u8 = (cleaned.astype(np.uint8)) * 255
        result[min_y:max_y, min_x:max_x] = cleaned_u8

    return result


def _pca_direction_vec(pts: np.ndarray) -> np.ndarray:
    """返回归一化的 PCA 主方向向量。"""
    if len(pts) < 2:
        return np.array([0.0, 0.0])
    centered = pts - pts.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    principal = eigenvectors[:, -1]
    norm = np.linalg.norm(principal)
    if norm < 1e-6:
        return np.array([0.0, 0.0])
    return principal / norm

def _eight_neighbors(y: int, x: int):
    return [
        (y - 1, x), (y - 1, x + 1), (y, x + 1), (y + 1, x + 1),
        (y + 1, x), (y + 1, x - 1), (y, x - 1), (y - 1, x - 1),
    ]
