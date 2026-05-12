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

    # 3. 压缩：从所有特殊节点出发，沿 deg-2 链走到下一个特殊节点
    # 简化图边 = (node_a, node_b, path_pixels)
    # 统一遍历（端点+交叉点），用 (special_a, special_b) 对去重
    ep_set = set(endpoints)
    special_nodes = ep_set | junc_set
    simp_edges = []
    visited_pairs = set()

    for sn in special_nodes:
        for nb in graph.get(sn, []):
            path = [sn, nb]
            prev = sn
            cur = nb
            while cur not in special_nodes:
                nxt = None
                for n in graph[cur]:
                    if n != prev:
                        nxt = n
                        break
                if nxt is None:
                    break
                path.append(nxt)
                prev, cur = cur, nxt

            if cur in special_nodes:
                if sn == cur:
                    pair = (sn, cur, nb)  # 自环用首步区分
                else:
                    pair = (sn, cur) if sn <= cur else (cur, sn)
                if pair not in visited_pairs:
                    visited_pairs.add(pair)
                    simp_edges.append((sn, cur, path))

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
        if a in junc_set and b in junc_set and len(path) <= 5:
            ci, cj = pt_to_comp[a], pt_to_comp[b]
            union_comp(ci, cj)  # 短桥合并，长链保留为笔画段

    # 重新映射：旧分量 → 新分量
    new_comp_id: Dict[int, int] = {}
    comp_groups: Dict[int, List[int]] = defaultdict(list)
    for ci in range(n_comp):
        root = find_comp(ci)
        comp_groups[root].append(ci)
    for new_id, (root, old_ids) in enumerate(comp_groups.items()):
        for oi in old_ids:
            new_comp_id[oi] = new_id

    # 5. 构建端点→边、交叉分量→边 的索引
    ep_to_edge: Dict[Tuple, int] = {}
    comp_to_edges: Dict[int, List[int]] = defaultdict(list)

    for ei, (a, b, path) in enumerate(simp_edges):
        # 跳过用于合并的短桥（已在合并后的分量内部）
        if a in junc_set and b in junc_set and len(path) <= 5:
            continue
        if a in ep_set:
            ep_to_edge[a] = ei
        elif a in junc_set:
            comp_to_edges[new_comp_id[pt_to_comp[a]]].append(ei)
        if b in ep_set:
            ep_to_edge[b] = ei
        elif b in junc_set:
            comp_to_edges[new_comp_id[pt_to_comp[b]]].append(ei)

    # 构建新分量→旧分量映射（用于方向计算时判断点是否在交叉区内）
    new_to_old_comps: Dict[int, Set[Tuple[int, int]]] = {}
    for old_ci, new_ci in new_comp_id.items():
        if new_ci not in new_to_old_comps:
            new_to_old_comps[new_ci] = set()
        new_to_old_comps[new_ci] |= junc_components[old_ci]

    # 6. 全局笔画组装：从端点出发，经交叉区沿方向连续性遍历
    used_edges: Set[int] = set()
    strokes = []

    for ep in endpoints:
        if ep not in ep_to_edge:
            continue
        ei = ep_to_edge[ep]
        if ei in used_edges:
            continue

        stroke_path = []
        cur_node = ep
        cur_ei = ei

        while True:
            a, b, path = simp_edges[cur_ei]
            # 确认走向：从 cur_node 到另一端
            if a == cur_node:
                oriented = path
                next_node = b
            else:
                oriented = list(reversed(path))
                next_node = a

            if not stroke_path:
                stroke_path = oriented
            else:
                stroke_path.extend(oriented[1:])

            used_edges.add(cur_ei)

            if next_node in ep_set:
                break  # 到达另一个端点

            # 在交叉区选择最佳延续边
            ci = new_comp_id[pt_to_comp[next_node]]
            candidates = [(ei2, simp_edges[ei2]) for ei2 in comp_to_edges[ci]
                         if ei2 not in used_edges]

            if not candidates:
                break

            # 选方向连续性最高的边
            best_ei, best_score = None, -1.0
            for ei2, (a2, b2, path2) in candidates:
                score = _continuity_at_junction(
                    oriented, path2,
                    new_to_old_comps[ci],
                )
                if score > best_score:
                    best_score = score
                    best_ei = ei2

            if best_ei is None or best_score < 0.2:
                break

            cur_node = next_node
            cur_ei = best_ei

        strokes.append(stroke_path)

    # 7. 处理剩余未使用的边（循环或孤立交叉点间链）
    for ei, (a, b, path) in enumerate(simp_edges):
        if ei in used_edges:
            continue
        if a in junc_set and b in junc_set and len(path) <= 5:
            continue
        strokes.append(_orient_path(path, endpoints, junc_set))

    # 7. 处理循环（无端点的闭合笔画，如「口」「日」等包围结构）
    all_visited = set()
    for _, _, path in simp_edges:
        all_visited.update(path)

    unvisited = set(graph.keys()) - all_visited
    while unvisited:
        start = unvisited.pop()
        # BFS 取该连通分量
        comp = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in comp:
                continue
            comp.add(cur)
            for nb in graph.get(cur, []):
                if nb not in comp and nb in unvisited:
                    stack.append(nb)
        unvisited -= comp

        if len(comp) < 5:
            continue
        # 纯循环（全部 deg-2）：沿一个方向追踪顺序
        if all(len(graph.get(p, [])) == 2 for p in comp):
            cycle = [start]
            cur = start
            prev = None
            while len(cycle) < len(comp):
                nxt = [n for n in graph[cur] if n != prev]
                if not nxt:
                    break
                if nxt[0] == start:
                    break
                cycle.append(nxt[0])
                prev, cur = cur, nxt[0]
            strokes.append(cycle)
        else:
            # 非纯循环但无端点：整体作为一笔
            strokes.append(list(comp))

    # 8. 过滤太短的笔画（<5 像素）并去重
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


def _continuity_at_junction(
    incoming: List[Tuple[int, int]],
    candidate: List[Tuple[int, int]],
    junc_pts: Set[Tuple[int, int]],
) -> float:
    """计算到达交叉区后延续到候选边的方向连续性得分。

    incoming 末端在交叉区；candidate 一端在交叉区。
    返回 [0, 1] 得分，越高表示方向越一致。
    """
    k = min(5, len(incoming), len(candidate))
    if k < 2:
        return 0.0

    # incoming 末尾 k 个点：进入交叉区方向
    pts_in = np.array(incoming[-k:]).astype(float)
    dir_in = pts_in[-1] - pts_in[0]

    # candidate 靠近交叉区的 k 个点：离开交叉区方向
    if candidate[0] in junc_pts:
        pts_out = np.array(candidate[:k]).astype(float)
    else:
        pts_out = np.array(candidate[-k:][::-1]).astype(float)
    dir_out = pts_out[-1] - pts_out[0]

    na, nb = np.linalg.norm(dir_in), np.linalg.norm(dir_out)
    if na < 1e-6 or nb < 1e-6:
        return 0.0

    # 进入和离开方向应一致（同向，不反向）
    cos = np.dot(dir_in / na, dir_out / nb)
    return max(0.0, cos)


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
