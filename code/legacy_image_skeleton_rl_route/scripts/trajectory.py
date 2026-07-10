"""骨架点排序、B样条平滑、轨迹CSV输出。

提供两种轨迹追踪方法：
- trace_skeleton_dfs: 简单 DFS（对比基线）
- trace_skeleton:     骨架拓扑分析 + 笔画组装（推荐）
"""

import numpy as np
from scipy import interpolate
from typing import List, Optional

from stroke import trace_strokes


def trace_skeleton(skeleton: np.ndarray) -> np.ndarray:
    """骨架二值图 → (N,2) 轨迹点 [y, x]（笔画感知版）。

    内部调用 stroke.trace_strokes，自动完成笔画分割、排序、定向。
    """
    return trace_strokes(skeleton)


def trace_skeleton_dfs(skeleton: np.ndarray) -> np.ndarray:
    """骨架二值图 → 轨迹点（简单 DFS，不区分笔画，作为对比基线）。

    遍历所有连通分量，每个分量从端点开始追踪。
    """
    binary = (skeleton > 0).astype(np.uint8)
    visited = np.zeros(binary.shape, dtype=bool)
    order = []

    for start_y, start_x in np.argwhere(binary):
        if visited[start_y, start_x]:
            continue
        # 从这个分量中找一个端点作为起点
        start = _find_endpoint_in_component(binary, start_y, start_x) or (start_y, start_x)
        stack = [start]
        while stack:
            y, x = stack.pop()
            if visited[y, x]:
                continue
            visited[y, x] = True
            order.append((y, x))
            for ny, nx in _eight_neighbors(y, x):
                if 0 <= ny < binary.shape[0] and 0 <= nx < binary.shape[1]:
                    if binary[ny, nx] and not visited[ny, nx]:
                        stack.append((ny, nx))

    if not order:
        return np.empty((0, 2))
    return np.array(order)


def trace_skeleton_curvature(skeleton: np.ndarray, angle_threshold: float = 50.0,
                              window: int = 8) -> List[np.ndarray]:
    """DFS 追踪骨架全路径，按曲率分割为笔画段。

    在方向急变处（> angle_threshold 度）切分笔画。
    不依赖交叉区图分析，天然抗交叉区弯曲。
    """
    full_path = trace_skeleton_dfs(skeleton)
    if len(full_path) < 10:
        return [full_path] if len(full_path) > 0 else []

    pts = full_path.astype(float)
    n = len(pts)
    cos_threshold = np.cos(np.radians(angle_threshold))

    # 计算每个点的局部方向（前后 window 点）
    directions = np.zeros((n, 2))
    for i in range(n):
        lo = max(0, i - window)
        hi = min(n, i + window + 1)
        seg = pts[lo:hi]
        if len(seg) < 2:
            continue
        centered = seg - seg.mean(axis=0)
        cov = np.cov(centered.T)
        eigenvalues, eigenvectors = np.linalg.eigh(cov)
        directions[i] = eigenvectors[:, -1]

    # 找方向突变点作为切分边界
    cuts = [0]
    for i in range(window, n - window):
        d1 = directions[i - window]
        d2 = directions[i + window]
        n1, n2 = np.linalg.norm(d1), np.linalg.norm(d2)
        if n1 < 1e-6 or n2 < 1e-6:
            continue
        cos_angle = abs(np.dot(d1 / n1, d2 / n2))
        if cos_angle < cos_threshold:
            cuts.append(i)
    cuts.append(n)

    # 切分笔画
    strokes = []
    for c in range(len(cuts) - 1):
        seg = full_path[cuts[c]:cuts[c + 1]]
        if len(seg) >= 5:
            strokes.append(seg)

    return strokes


def _find_endpoint_in_component(binary: np.ndarray, sy: int, sx: int):
    """在给定种子点所在的连通分量中找第一个端点（8邻域仅1个前景邻居），用于确定笔画起点。"""
    # BFS 搜索连通分量，回到第一个端点
    component_visited = np.zeros(binary.shape, dtype=bool)
    queue = [(sy, sx)]
    component_visited[sy, sx] = True
    while queue:
        y, x = queue.pop(0)
        nb_count = 0
        for ny, nx in _eight_neighbors(y, x):
            if 0 <= ny < binary.shape[0] and 0 <= nx < binary.shape[1]:
                if binary[ny, nx]:
                    nb_count += 1
                    if not component_visited[ny, nx]:
                        component_visited[ny, nx] = True
                        queue.append((ny, nx))
        if nb_count == 1:
            return (y, x)
    return None


def _rdp_simplify(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Ramer-Douglas-Peucker 折线简化，返回简化后的点集。"""
    if len(points) < 3:
        return points
    # 找离首尾连线最远的点
    dmax, idx = 0.0, 0
    end = len(points) - 1
    seg = points[end] - points[0]
    seg_len_sq = np.dot(seg, seg)
    if seg_len_sq < 1e-12:
        return np.array([points[0], points[-1]])
    for i in range(1, end):
        d = abs(np.cross(seg, points[i] - points[0])) / np.sqrt(seg_len_sq)
        if d > dmax:
            dmax, idx = d, i
    if dmax > epsilon:
        left = _rdp_simplify(points[: idx + 1], epsilon)
        right = _rdp_simplify(points[idx:], epsilon)
        return np.vstack([left[:-1], right])
    return np.array([points[0], points[-1]])


def smooth_bspline(points: np.ndarray, num_points: Optional[int] = None, s: float = 0.0) -> np.ndarray:
    """对轨迹点做B样条平滑，返回平滑后的 (M, 2) 点序列。

    Args:
        points: (N, 2) 原始轨迹点
        num_points: 输出点数，默认为原始点数
        s: 平滑因子，越大越平滑（自动按压缩比缩放）

    先用 RDP 简化去除 Zhang-Suen 锯齿，再用 k=2 二次样条拟合。
    若二次样条自交，回退到线性插值。
    """
    if len(points) < 4:
        return points

    if num_points is None:
        num_points = len(points)

    # RDP 预简化：去除骨架锯齿（epsilon=2.0 保留亚像素级细节）
    simplified = _rdp_simplify(points.astype(float), epsilon=2.0)
    if len(simplified) < 4:
        simplified = points.astype(float)

    # 自动按压缩比缩放 s
    compression = num_points / len(simplified)
    s_effective = s * max(compression, 0.02)

    t = np.linspace(0, 1, len(simplified))
    t_new = np.linspace(0, 1, num_points)

    for k in [2, 1]:
        try:
            k_use = min(k, len(simplified) - 1)
            tck, _ = interpolate.splprep(
                [simplified[:, 0], simplified[:, 1]], s=s_effective, k=k_use
            )
            smoothed = np.array(interpolate.splev(t_new, tck)).T

            if k == 2 and _has_self_cross(smoothed):
                continue

            return smoothed
        except Exception:
            continue

    return points


def _has_self_cross(pts: np.ndarray) -> bool:
    """检查点序列是否自交（采样检测，非精确）。"""
    n = len(pts)
    if n < 10:
        return False
    for a in range(0, n - 5, 5):
        for b in range(a + 5, n - 1, 5):
            p1, p2 = pts[a], pts[min(a + 5, n - 1)]
            p3, p4 = pts[b], pts[min(b + 5, n - 1)]
            d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0])
            if abs(d) < 1e-6:
                continue
            t = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d
            u = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d
            if 0.05 < t < 0.95 and 0.05 < u < 0.95:
                return True
    return False


def smooth_strokes(
    strokes: List[np.ndarray],
    total_points: int = 300,
    s: float = 2.0,
) -> List[np.ndarray]:
    """对每个笔画分别B样条平滑，按笔画长度比例分配采样点数。"""
    if not strokes:
        return []

    lengths = [len(s) for s in strokes]
    total_len = sum(lengths)
    if total_len == 0:
        return strokes

    smoothed = []
    for i, stk in enumerate(strokes):
        if len(stk) < 4:
            smoothed.append(stk)
            continue
        n_pts = max(4, int(total_points * lengths[i] / total_len))
        smoothed.append(smooth_bspline(stk, num_points=n_pts, s=s))

    return smoothed


def save_trajectory_csv(points: np.ndarray, path: str):
    """保存轨迹点到CSV文件，列: y, x。"""
    np.savetxt(path, points, delimiter=",", fmt="%.3f", header="y,x", comments="")


def save_stroke_csv(strokes: List[np.ndarray], path: str):
    """保存笔画轨迹到CSV文件，每个笔画之间插入空行表示抬笔。"""
    lines = ["y,x"]
    for stk in strokes:
        for y, x in stk:
            lines.append(f"{y:.3f},{x:.3f}")
        lines.append("nan,nan")  # 抬笔分隔
    with open(path, "w") as f:
        f.write("\n".join(lines))


def _count_neighbors(binary: np.ndarray, y: int, x: int) -> int:
    count = 0
    for ny, nx in _eight_neighbors(y, x):
        if 0 <= ny < binary.shape[0] and 0 <= nx < binary.shape[1]:
            count += binary[ny, nx]
    return count


def _eight_neighbors(y: int, x: int):
    return [
        (y - 1, x), (y - 1, x + 1), (y, x + 1), (y + 1, x + 1),
        (y + 1, x), (y + 1, x - 1), (y, x - 1), (y - 1, x - 1),
    ]
