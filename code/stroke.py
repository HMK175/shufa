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

    流程：建图 → 简化图（压缩链点）→ 交叉点配对 → 排序 → 定方向。
    """
    if np.sum(skeleton > 0) == 0:
        return np.empty((0, 2))

    strokes = _extract_strokes(skeleton)
    if not strokes:
        return np.array(list(build_skeleton_graph(skeleton).keys()))

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

    strokes = _extract_strokes(skeleton)
    if not strokes:
        return [np.array(list(build_skeleton_graph(skeleton).keys()))]

    strokes = order_strokes(strokes)
    strokes = [set_stroke_direction(s) for s in strokes]
    return [np.array(s) for s in strokes]


def _extract_strokes(skeleton: np.ndarray) -> List[List[Tuple[int, int]]]:
    """核心笔画提取：简化图 + 交叉点配对。

    1. 建全图，找端点和交叉点，聚类交叉点为分量
    2. 压缩 deg-2 链点 → 简化图（节点=端点+交叉分量）
    3. 在每个交叉分量将其关联边按方向连续性配对
    4. 每对端点→交叉区→端点 = 一个笔画
    """
    graph = build_skeleton_graph(skeleton)
    endpoints = [pt for pt, nb in graph.items() if len(nb) == 1]
    raw_junctions = [pt for pt, nb in graph.items() if len(nb) >= 3]

    if not endpoints:
        return []

    if not raw_junctions:
        return _pair_endpoints_directly(graph, endpoints)

    # 1. 聚类交叉点（8-连通）
    junc_set = set(raw_junctions)
    junc_components = _cluster_junc_pixels(junc_set, graph)

    # 2. 建立交叉分量的查找表
    pt_to_comp = {}
    for ci, comp in enumerate(junc_components):
        for pt in comp:
            pt_to_comp[pt] = ci

    # 3. 压缩：收缩 deg-2 链 → 构建简化图
    # 简化图节点 = 端点坐标 或 交叉分量索引 (0..K-1)
    # 简化图边 = (node_a, node_b, path_pixels)
    #   其中 node_a/node_b 可以是端点坐标或分量索引
    # 忽略同一分量内的交叉点间边
    simp_edges = []
    visited_nodes_in_search = set()

    ep_set = set(endpoints)

    # 只从端点出发遍历（避免从交叉点出发产生重复边）
    for ep in endpoints:
        for nb in graph.get(ep, []):
            edge_key = _normalize_edge(ep, nb)
            if edge_key in visited_nodes_in_search:
                continue
            visited_nodes_in_search.add(edge_key)

            if nb in junc_set or nb in ep_set:
                simp_edges.append((ep, nb, [ep, nb]))
                continue

            # 沿 deg-2 链走到下一个特殊节点
            path = [ep, nb]
            prev = ep
            cur = nb
            while cur not in junc_set and cur not in ep_set:
                nxt = None
                for n in graph[cur]:
                    if n != prev:
                        nxt = n
                        break
                if nxt is None:
                    break
                path.append(nxt)
                prev, cur = cur, nxt
            if cur in junc_set or cur in ep_set:
                simp_edges.append((ep, cur, path))

    # 补充：交叉点间的桥接边（从交叉点出发，但已访问的跳过）
    for jp in junc_set:
        for nb in graph.get(jp, []):
            edge_key = _normalize_edge(jp, nb)
            if edge_key in visited_nodes_in_search:
                continue
            if nb not in junc_set:
                continue
            if pt_to_comp[jp] == pt_to_comp[nb]:
                continue
            visited_nodes_in_search.add(edge_key)
            # 走到交叉点间路径
            path = [jp, nb]
            prev = jp
            cur = nb
            while cur not in junc_set and cur not in ep_set:
                nxt = None
                for n in graph[cur]:
                    if n != prev:
                        nxt = n
                        break
                if nxt is None:
                    break
                path.append(nxt)
                prev, cur = cur, nxt
            if cur in junc_set:
                simp_edges.append((jp, cur, path))

    # 4. 合并所有通过桥接边连通的交叉分量
    n_comp = len(junc_components)
    comp_parent = list(range(n_comp))
    def find_comp(i):
        while comp_parent[i] != i:
            comp_parent[i] = comp_parent[comp_parent[i]]
            i = comp_parent[i]
        return i
    def union_comp(i, j):
        ri, rj = find_comp(i), find_comp(j)
        if ri != rj:
            comp_parent[ri] = rj

    for a, b, path in simp_edges:
        if a in junc_set and b in junc_set:
            ci, cj = pt_to_comp[a], pt_to_comp[b]
            union_comp(ci, cj)  # 桥接连通就合并（不限距离）

    # 重新映射：旧分量 → 新分量
    new_comp_id: Dict[int, int] = {}
    comp_groups: Dict[int, List[int]] = defaultdict(list)
    for ci in range(n_comp):
        root = find_comp(ci)
        comp_groups[root].append(ci)
    for new_id, (root, old_ids) in enumerate(comp_groups.items()):
        for oi in old_ids:
            new_comp_id[oi] = new_id

    # 5. 将交叉分量作为合并后的节点，构建分量→关联边 映射
    #    只考虑端点↔交叉分量 的边；交叉分量间的桥接边已内化
    comp_edges: Dict[int, List[int]] = defaultdict(list)
    ep_edges: Dict[Tuple, List[int]] = defaultdict(list)

    for ei, (a, b, path) in enumerate(simp_edges):
        # 跳过交叉点间边（已在合并后的分量内部）
        if a in junc_set and b in junc_set:
            continue

        if a in ep_set:
            ep_edges[a].append(ei)
        elif a in junc_set:
            comp_edges[new_comp_id[pt_to_comp[a]]].append(ei)

        if b in ep_set:
            ep_edges[b].append(ei)
        elif b in junc_set:
            comp_edges[new_comp_id[pt_to_comp[b]]].append(ei)

    # 6. 在每个（合并后的）交叉分量配对
    used_edges = set()
    strokes = []

    # 构建新分量→旧分量列表（用于方向计算）
    new_to_old_comps: Dict[int, Set[Tuple[int, int]]] = {}
    old_to_new = new_comp_id
    for old_ci, new_ci in old_to_new.items():
        if new_ci not in new_to_old_comps:
            new_to_old_comps[new_ci] = set()
        new_to_old_comps[new_ci] |= junc_components[old_ci]

    for ci, edge_indices in comp_edges.items():
        # 该分量关联的边（去重，排除已使用的）
        available = [ei for ei in set(edge_indices) if ei not in used_edges]

        paired = set()
        for _ in range(len(available) // 2):
            best_score = -1.0
            best_pair = None
            for p in range(len(available)):
                if p in paired:
                    continue
                for q in range(p + 1, len(available)):
                    if q in paired:
                        continue
                    score = _simp_edge_pair_score(
                        simp_edges[available[p]], simp_edges[available[q]],
                        new_to_old_comps[ci],
                    )
                    if score > best_score:
                        best_score = score
                        best_pair = (p, q)
            if best_pair and best_score > 0.2:
                p, q = best_pair
                paired.add(p)
                paired.add(q)
                used_edges.add(available[p])
                used_edges.add(available[q])
                merged = _merge_edge_pair(
                    simp_edges[available[p]], simp_edges[available[q]],
                    new_to_old_comps[ci],
                )
                strokes.append(merged)

        # 未配对的边：尝试强制配对剩余边
        remaining = [p for p in range(len(available)) if p not in paired]
        while len(remaining) >= 2:
            p, q = remaining[0], remaining[1]
            paired.add(p)
            paired.add(q)
            used_edges.add(available[p])
            used_edges.add(available[q])
            merged = _merge_edge_pair(
                simp_edges[available[p]], simp_edges[available[q]],
                new_to_old_comps[ci],
            )
            strokes.append(merged)
            remaining = remaining[2:]

        # 无法配对的单条边
        for p in remaining:
            used_edges.add(available[p])
            _, _, path = simp_edges[available[p]]
            strokes.append(_orient_path(path, endpoints, junc_set))

    # 6. 未被任何交叉分量关联的边（直连端点对、孤立分量）
    for ei, (a, b, path) in enumerate(simp_edges):
        if ei not in used_edges:
            # 跳过交叉点间边（已在合并后的分量内部）
            if a in junc_set and b in junc_set:
                continue
            strokes.append(_orient_path(path, endpoints, junc_set))

    # 7. 过滤太短的笔画（<5 像素）并去重
    seen_keys = set()
    filtered = []
    for s in strokes:
        if len(s) < 5:
            continue
        key = (s[0], s[-1]) if s[0] < s[-1] else (s[-1], s[0])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        filtered.append(s)

    return filtered


def _cluster_junc_pixels(
    junc_set: Set[Tuple[int, int]], graph: Dict
) -> List[Set[Tuple[int, int]]]:
    """将交叉点像素按 8-连通聚类成组件。"""
    if not junc_set:
        return []
    visited = set()
    components = []
    for pt in junc_set:
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
                if nb in junc_set and nb not in visited:
                    stack.append(nb)
        components.append(comp)
    return components


def _simp_edge_pair_score(
    edge_a: Tuple, edge_b: Tuple,
    junc_pts: Set[Tuple[int, int]],
) -> float:
    """两条简化边在交叉区处的方向连续性得分。"""
    a_node_a, a_node_b, path_a = edge_a
    b_node_a, b_node_b, path_b = edge_b

    # 判断哪端连接交叉区
    a_end_a_in_comp = a_node_a in junc_pts
    b_end_a_in_comp = b_node_a in junc_pts

    # 取交叉分量附近的局部方向
    k = min(5, len(path_a), len(path_b))
    if k < 2:
        return 0.0

    if a_end_a_in_comp:
        pts_a = np.array(path_a[:k]).astype(float)
    else:
        pts_a = np.array(path_a[-k:]).astype(float)

    if b_end_a_in_comp:
        pts_b = np.array(path_b[:k]).astype(float)
    else:
        pts_b = np.array(path_b[-k:]).astype(float)

    dir_a = pts_a[-1] - pts_a[0]  # 进入交叉区方向
    dir_b = pts_b[-1] - pts_b[0]

    na, nb = np.linalg.norm(dir_a), np.linalg.norm(dir_b)
    if na < 1e-6 or nb < 1e-6:
        return 0.0

    cos = np.dot(dir_a / na, -dir_b / nb)
    return max(0.0, cos)


def _merge_edge_pair(
    edge_a: Tuple, edge_b: Tuple,
    junc_pts: Set[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    """拼接两条边为一个完整笔画路径。"""
    a_node_a, a_node_b, path_a = edge_a
    b_node_a, b_node_b, path_b = edge_b

    a_starts_in_comp = a_node_a in junc_pts
    b_starts_in_comp = b_node_a in junc_pts

    # path_a 从非交叉端走到交叉端
    if a_starts_in_comp:
        part_a = list(reversed(path_a))
    else:
        part_a = list(path_a)

    # path_b 从交叉端走到非交叉端
    if b_starts_in_comp:
        part_b = list(path_b)
    else:
        part_b = list(reversed(path_b))

    # 拼接（去掉交叉端的重复点）
    merged = part_a + part_b[1:]
    return merged


def _orient_path(
    path: List[Tuple[int, int]],
    endpoints: List[Tuple[int, int]],
    junc_set: Set[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    """确保路径从端点出发（如果有的话）。"""
    if not path:
        return path
    ep_set = set(endpoints)
    if path[-1] in ep_set and path[0] not in ep_set:
        return list(reversed(path))
    return path






def _pair_endpoints_directly(
    graph: Dict, endpoints: List[Tuple[int, int]]
) -> List[List[Tuple[int, int]]]:
    """无交叉点时：端点对直接配对。"""
    # BFS 找端点间路径
    used = set()
    strokes = []
    for ep in endpoints:
        if ep in used:
            continue
        # BFS 到最近的其他端点
        queue = [(ep, [ep])]
        visited = {ep}
        while queue:
            cur, path = queue.pop(0)
            if cur != ep and cur in endpoints:
                strokes.append(path)
                for p in path:
                    used.add(p)
                break
            for nb in graph.get(cur, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, path + [nb]))
        else:
            strokes.append([ep])
            used.add(ep)
    return strokes
    return [np.array(s) for s in strokes]


# ── 辅助 ──────────────────────────────────────────────────

def _eight_neighbors(y: int, x: int):
    return [
        (y - 1, x), (y - 1, x + 1), (y, x + 1), (y + 1, x + 1),
        (y + 1, x), (y + 1, x - 1), (y, x - 1), (y - 1, x - 1),
    ]


def _normalize_edge(a: Tuple[int, int], b: Tuple[int, int]) -> Tuple:
    return (a, b) if a < b else (b, a)
