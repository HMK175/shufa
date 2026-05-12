"""骨架点排序、B样条平滑、轨迹CSV输出。

提供两种轨迹追踪方法：
- trace_skeleton_dfs: 简单 DFS（对比基线）
- trace_skeleton:     骨架拓扑分析 + 笔画组装（推荐）
"""

import numpy as np
from scipy import interpolate
from typing import Optional

from stroke import trace_strokes


def trace_skeleton(skeleton: np.ndarray) -> np.ndarray:
    """骨架二值图 → (N,2) 轨迹点 [y, x]（笔画感知版）。

    内部调用 stroke.trace_strokes，自动完成笔画分割、排序、定向。
    """
    return trace_strokes(skeleton)


def trace_skeleton_dfs(skeleton: np.ndarray) -> np.ndarray:
    """骨架二值图 → 轨迹点（简单 DFS，不区分笔画，作为对比基线）。"""
    binary = (skeleton > 0).astype(np.uint8)
    points = np.argwhere(binary)
    if len(points) == 0:
        return np.empty((0, 2))

    endpoints = []
    for y, x in points:
        nb = _count_neighbors(binary, y, x)
        if nb == 1:
            endpoints.append((y, x))

    start = endpoints[0] if endpoints else tuple(points[0])

    visited = np.zeros(binary.shape, dtype=bool)
    order = []
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


def save_trajectory_csv(points: np.ndarray, path: str):
    """保存轨迹点到CSV文件，列: y, x。"""
    np.savetxt(path, points, delimiter=",", fmt="%.3f", header="y,x", comments="")


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
