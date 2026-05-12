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


def smooth_bspline(points: np.ndarray, num_points: Optional[int] = None, s: float = 0.0) -> np.ndarray:
    """对轨迹点做B样条平滑，返回平滑后的 (M, 2) 点序列。

    Args:
        points: (N, 2) 原始轨迹点
        num_points: 输出点数，默认为原始点数
        s: 平滑因子，越大越平滑
    """
    if len(points) < 4:
        return points

    if num_points is None:
        num_points = len(points)

    t = np.linspace(0, 1, len(points))
    t_new = np.linspace(0, 1, num_points)

    try:
        tck, _ = interpolate.splprep([points[:, 0], points[:, 1]], s=s, k=min(3, len(points) - 1))
        smoothed = np.array(interpolate.splev(t_new, tck)).T
    except Exception:
        return points

    return smoothed


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
