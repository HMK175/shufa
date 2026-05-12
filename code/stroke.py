"""骨架拓扑分析 + 笔画级轨迹组装。

将骨架从像素级 DFS 升级为：
1. 构建邻接图，分类关键点（端点/交叉区像素）
2. 交叉区检测（所有 degree>=3 像素 + 膨胀）
3. 交叉区连通分量聚类（处理 Zhang-Suen 在交叉处的像素簇）
4. 提取端点→交叉区边界的无分支段
5. 在每个交叉区用方向连续性合并笔画
6. 按书法规则排序和确定方向
"""

import numpy as np
from collections import defaultdict
from typing import List, Tuple, Dict, Set, Optional


# ── 骨架图构建 ────────────────────────────────────────────

def build_skeleton_graph(skeleton: np.ndarray) -> Dict[Tuple[int, int], List[Tuple[int, int]]]:
    """将骨架二值图(0/255)转为邻接表 {(y,x): [邻居坐标]}。"""
    binary = (skeleton > 0)
    ys, xs = np.where(binary)
    points_set = set(zip(ys, xs))
    graph = {}
    for y, x in points_set:
        neighbors = []
        for ny, nx in _eight_neighbors(y, x):
            if (ny, nx) in points_set:
                neighbors.append((ny, nx))
        graph[(y, x)] = neighbors
    return graph


# ── 骨架剪枝 ──────────────────────────────────────────────

def prune_skeleton(skeleton: np.ndarray, min_branch_len: int = 10) -> np.ndarray:
    """移除骨架的短小毛刺分支，返回清理后的骨架二值图 (0/255)。

    这是 Zhang-Suen 在斜线/粗线上产生阶梯状分支的标准后处理。
    """
    binary = (skeleton > 0).astype(np.uint8)
    graph = build_skeleton_graph(skeleton)

    while True:
        # 找所有端点和分支点
        endpoints, branchpoints = [], []
        for pt, neighbors in graph.items():
            deg = len(neighbors)
            if deg == 1:
                endpoints.append(pt)
            elif deg >= 3:
                branchpoints.append(pt)

        bp_set = set(branchpoints)
        removed = set()
        for ep in endpoints:
            # 从端点沿 skeleton 走到分支点
            path = [ep]
            cur = ep
            prev = None
            while cur not in bp_set:
                nxt = None
                for n in graph.get(cur, []):
                    if n != prev:
                        nxt = n
                        break
                if nxt is None:
                    break
                path.append(nxt)
                prev, cur = cur, nxt

            if cur in bp_set and len(path) - 1 < min_branch_len:
                # 移除这条短分支（不包括分支点本身）
                for p in path[:-1]:
                    removed.add(p)

        if not removed:
            break

        # 从 graph 中移除
        for p in removed:
            if p in graph:
                for nb in graph[p]:
                    graph[nb] = [n for n in graph[nb] if n != p]
                del graph[p]

    # 重建骨架二值图
    cleaned = np.zeros_like(binary)
    for (y, x) in graph:
        cleaned[y, x] = 255
    return cleaned


# ── 交叉区检测 ────────────────────────────────────────────

def classify_points(
    graph: Dict[Tuple[int, int], List[Tuple[int, int]]]
) -> Tuple[List, Set[Tuple[int, int]]]:
    """返回 (端点列表, 交叉区像素集合)。

    交叉区：degree>=3 的像素 + 3x3 膨胀区域。
    """
    raw_junctions: List[Tuple[int, int]] = []
    for pt, neighbors in graph.items():
        if len(neighbors) >= 3:
            raw_junctions.append(pt)

    # 交叉区 = 原始交叉点（不膨胀，避免吃掉太多正常骨架点）
    junc_region: Set[Tuple[int, int]] = set(raw_junctions)

    # 端点：degree=1 且不在交叉区内
    endpoints = []
    for pt, neighbors in graph.items():
        if pt in junc_region:
            continue
        if len(neighbors) == 1:
            endpoints.append(pt)

    # 若无端点（骨架太乱或为闭合环），退回简单模式
    if not endpoints:
        pass  # 调用方应处理此情况

    return endpoints, junc_region


# ── 交叉区连通分量聚类 ────────────────────────────────────

def _cluster_junc_region(
    junc_region: Set[Tuple[int, int]],
    graph: Dict
) -> List[Set[Tuple[int, int]]]:
    """将交叉区按 8-连通性分成独立分量（处理多个分离的交叉点）。"""
    if not junc_region:
        return []

    visited: Set[Tuple[int, int]] = set()
    components: List[Set[Tuple[int, int]]] = []

    for pt in junc_region:
        if pt in visited:
            continue
        # BFS
        comp: Set[Tuple[int, int]] = set()
        stack = [pt]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            for nb in graph.get(cur, []):
                if nb in junc_region and nb not in visited:
                    stack.append(nb)
        components.append(comp)

    return components


def _component_centroid(comp: Set[Tuple[int, int]]) -> Tuple[int, int]:
    """分量质心（取整）。"""
    ys = [p[0] for p in comp]
    xs = [p[1] for p in comp]
    return (int(round(np.mean(ys))), int(round(np.mean(xs))))


# ── 段提取 ────────────────────────────────────────────────

def extract_segments(
    graph: Dict,
    endpoints: List[Tuple[int, int]],
    junc_region: Set[Tuple[int, int]]
) -> List[List[Tuple[int, int]]]:
    """从端点出发沿链点走到交叉区边界，切出无分支段。"""
    visited_edges: Set[Tuple] = set()
    segments: List[List[Tuple[int, int]]] = []
    stop_set = set(endpoints) | junc_region

    for ep in endpoints:
        for nb in graph.get(ep, []):
            edge = _normalize_edge(ep, nb)
            if edge in visited_edges:
                continue
            visited_edges.add(edge)

            path = [ep, nb]
            prev = ep
            cur = nb
            while cur not in stop_set:
                nxt = None
                for n in graph[cur]:
                    if n != prev:
                        nxt = n
                        break
                if nxt is None:
                    break
                visited_edges.add(_normalize_edge(cur, nxt))
                path.append(nxt)
                prev, cur = cur, nxt

            segments.append(path)

    return segments


# ── 笔画组装 ──────────────────────────────────────────────

def assemble_strokes(
    segments: List[List[Tuple[int, int]]],
    junc_components: List[Set[Tuple[int, int]]],
    junc_region: Set[Tuple[int, int]],
    graph: Dict
) -> List[List[Tuple[int, int]]]:
    """在每个交叉区用方向连续性合并段，返回笔画列表。"""
    n = len(segments)
    if n <= 1:
        return [list(seg) for seg in segments]

    # 段 → 交叉分量 映射
    seg_to_comp: List[Optional[int]] = [None] * n
    for i, seg in enumerate(segments):
        for ep in (seg[0], seg[-1]):
            if ep in junc_region:
                # 找这个点属于哪个分量
                for ci, comp in enumerate(junc_components):
                    if ep in comp:
                        seg_to_comp[i] = ci
                        break

    # 每个分量单独配对
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    for ci in range(len(junc_components)):
        seg_indices = [i for i, c in enumerate(seg_to_comp) if c == ci]
        if len(seg_indices) < 2:
            continue

        centroid = _component_centroid(junc_components[ci])
        unpaired = set(seg_indices)

        while len(unpaired) >= 2:
            best_score = -1.0
            best_pair = None
            ul = list(unpaired)
            for a in range(len(ul)):
                for b in range(a + 1, len(ul)):
                    ia, ib = ul[a], ul[b]
                    score = _continuity_score(segments[ia], segments[ib])
                    if score > best_score:
                        best_score = score
                        best_pair = (ia, ib)
            if best_pair and best_score > 0.5:
                union(best_pair[0], best_pair[1])
                unpaired.discard(best_pair[0])
                unpaired.discard(best_pair[1])
            else:
                break

    # 按合并结果分组
    groups: Dict[int, List[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    strokes = []
    for seg_list in groups.values():
        merged = _merge_segments([segments[i] for i in seg_list])
        if len(merged) >= 2:
            strokes.append(merged)

    return strokes


def _continuity_score(seg_a: List, seg_b: List) -> float:
    """计算两段的方向连续性 (0~1，越大越贯穿)。

    两段都从端点走向交叉区末端 (seg[-1] 在交叉区内)。
    判断 seg_a 进入方向与 seg_b 离开方向是否一致。
    """
    dir_a = _junction_end_direction(seg_a)
    dir_b = _junction_end_direction(seg_b)
    if dir_a is None or dir_b is None:
        return 0.0
    na, nb = np.linalg.norm(dir_a), np.linalg.norm(dir_b)
    if na < 1e-6 or nb < 1e-6:
        return 0.0
    # seg_a 进入交叉区方向 应与 seg_b 离开方向一致
    # seg_b 离开方向 = -seg_b 进入方向
    cos = np.dot(dir_a / na, -dir_b / nb)
    return max(0.0, cos)


def _junction_end_direction(seg: List) -> Optional[np.ndarray]:
    """取段末端（交叉区侧）若干点的方向向量，指向交叉区内。"""
    n_pts = min(5, len(seg))
    if n_pts < 2:
        return None
    pts = np.array(seg[-n_pts:])
    return (pts[-1] - pts[0]).astype(float)


def _merge_segments(segments: List[List]) -> List:
    """将属于同一笔画的多个段贪心拼接成连续路径。"""
    if len(segments) == 1:
        return list(segments[0])

    remaining = [list(s) for s in segments]
    result = remaining.pop(0)

    changed = True
    while changed and remaining:
        changed = False
        for i, seg in enumerate(remaining):
            if seg[0] == result[-1]:
                result.extend(seg[1:])
                remaining.pop(i)
                changed = True
                break
            elif seg[-1] == result[-1]:
                result.extend(reversed(seg[:-1]))
                remaining.pop(i)
                changed = True
                break
            elif seg[0] == result[0]:
                result = list(reversed(seg[1:])) + result
                remaining.pop(i)
                changed = True
                break
            elif seg[-1] == result[0]:
                result = list(seg[:-1]) + result
                remaining.pop(i)
                changed = True
                break

    for seg in remaining:
        result.extend(seg)
    return result


# ── 笔画排序 ──────────────────────────────────────────────

def order_strokes(strokes: List[List[Tuple[int, int]]]) -> List[List[Tuple[int, int]]]:
    """按书法习惯排序：自上而下、自左而右。"""
    if len(strokes) <= 1:
        return strokes

    infos = []
    for i, s in enumerate(strokes):
        ys = [p[0] for p in s]
        xs = [p[1] for p in s]
        infos.append({'idx': i, 'cy': np.mean(ys), 'cx': np.mean(xs)})
    infos.sort(key=lambda d: (d['cy'], d['cx']))
    return [strokes[info['idx']] for info in infos]


# ── 书写方向确定 ──────────────────────────────────────────

def set_stroke_direction(stroke: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """确保笔画从起笔到收笔方向正确（自上而下、自左而右）。"""
    if len(stroke) < 2:
        return stroke

    ys = np.array([p[0] for p in stroke])
    xs = np.array([p[1] for p in stroke])
    dy = ys[-1] - ys[0]
    dx = xs[-1] - xs[0]

    # 总体上往下走（图像坐标 y 轴向下）
    if dy < 0:
        return list(reversed(stroke))

    # 横笔画：确保左→右
    if abs(dx) > 2 * abs(dy) and dx < 0:
        return list(reversed(stroke))

    return stroke


# ── 顶层入口 ──────────────────────────────────────────────

def trace_strokes(skeleton: np.ndarray) -> np.ndarray:
    """骨架二值图 (0/255) → (N,2) 轨迹点数组 [y, x]。

    流程：建图 → 交叉区检测 → 分量聚类 → 切段 → 合并笔画 → 排序 → 定方向。
    """
    if np.sum(skeleton > 0) == 0:
        return np.empty((0, 2))

    graph = build_skeleton_graph(skeleton)
    endpoints, junc_region = classify_points(graph)
    junc_components = _cluster_junc_region(junc_region, graph)

    if len(endpoints) == 0 or len(junc_components) == 0:
        # 骨架太乱（大块交叉区），退回简单拓扑排序
        all_pts = list(graph.keys())
        return np.array(all_pts)

    segments = extract_segments(graph, endpoints, junc_region)
    if not segments:
        all_pts = list(graph.keys())
        return np.array(all_pts)

    strokes = assemble_strokes(segments, junc_components, junc_region, graph)
    if not strokes:
        all_pts = list(graph.keys())
        return np.array(all_pts)

    strokes = order_strokes(strokes)
    strokes = [set_stroke_direction(s) for s in strokes]

    all_points = []
    for s in strokes:
        all_points.extend(s)
    return np.array(all_points)


def get_stroke_list(skeleton: np.ndarray) -> List[np.ndarray]:
    """返回笔画列表（用于可视化时按笔画着色）。"""
    if np.sum(skeleton > 0) == 0:
        return []

    graph = build_skeleton_graph(skeleton)
    endpoints, junc_region = classify_points(graph)
    junc_components = _cluster_junc_region(junc_region, graph)

    if len(endpoints) == 0 or len(junc_components) == 0:
        return [np.array(list(graph.keys()))]

    segments = extract_segments(graph, endpoints, junc_region)
    if not segments:
        return [np.array(list(graph.keys()))]

    strokes = assemble_strokes(segments, junc_components, junc_region, graph)
    if not strokes:
        return [np.array(list(graph.keys()))]

    strokes = order_strokes(strokes)
    strokes = [set_stroke_direction(s) for s in strokes]
    return [np.array(s) for s in strokes]


# ── 辅助 ──────────────────────────────────────────────────

def _eight_neighbors(y: int, x: int):
    return [
        (y - 1, x), (y - 1, x + 1), (y, x + 1), (y + 1, x + 1),
        (y + 1, x), (y + 1, x - 1), (y, x - 1), (y - 1, x - 1),
    ]


def _normalize_edge(a: Tuple[int, int], b: Tuple[int, int]) -> Tuple:
    return (a, b) if a < b else (b, a)
