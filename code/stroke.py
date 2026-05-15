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

def compute_nc(graph: Dict, pt: Tuple[int, int]) -> int:
    """计算 pt 的 8 邻域分量数 Nc（Wu2024 分类）。

    Nc=1 → V 端点, Nc=2 → C 连接点, Nc≥3 → S 交叉点。
    与简单 degree 不同：交叉区边界点即使有 3+ 邻居，
    若邻居同属 2 个连通分量，仍判为 C（抗边界误判）。
    """
    nbs = graph.get(pt, [])
    if len(nbs) <= 1:
        return len(nbs)
    nb_set = set(nbs)
    visited = set()
    components = 0
    for nb in nbs:
        if nb in visited:
            continue
        components += 1
        stack = [nb]
        visited.add(nb)
        while stack:
            cur = stack.pop()
            for nxt in graph.get(cur, []):
                if nxt in nb_set and nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
    return components


def prune_skeleton(skeleton: np.ndarray, min_branch_len: int = 10) -> np.ndarray:
    """移除骨架的短小毛刺分支，返回清理后的骨架二值图 (0/255)。

    这是 Zhang-Suen 在斜线/粗线上产生阶梯状分支的标准后处理。
    """
    binary = (skeleton > 0).astype(np.uint8)
    graph = build_skeleton_graph(skeleton)

    while True:
        # 找所有端点和分支点（deg 判断——剪枝只需找到主分支的连接点）
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
    """按书法规则排序：笔型优先 + 交叉区感知 + 拓扑排序，自上而下/自左而右兜底。

    规则：先横后竖(交叉处)、先撇后捺、从上到下、从左到右。
    """
    n = len(strokes)
    if n <= 1:
        return strokes

    types = [classify_stroke(s) for s in strokes]

    # 构建交叉区邻接：端点距离 < 8px 认为共享交叉区
    adj = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if _strokes_adjacent(strokes[i], strokes[j]):
                adj[i].add(j)
                adj[j].add(i)

    # 优先级权重（越小越先写）
    type_priority = {"dian": 0, "heng": 1, "zhe": 2, "shu": 3, "gou": 4, "pie": 5, "na": 6, "unknown": 7}

    # 给每个笔画打分：结合笔型优先级和位置
    def centroid(i):
        ys = [p[0] for p in strokes[i]]
        xs = [p[1] for p in strokes[i]]
        return np.mean(ys), np.mean(xs)

    infos = []
    for i in range(n):
        cy, cx = centroid(i)
        # 位置得分：上方和左侧优先
        pos_score = cy * 1.0 + cx * 0.3
        # 笔型优先级
        tp = type_priority.get(types[i], 7)
        infos.append({"idx": i, "cy": cy, "cx": cx, "type": types[i],
                       "type_rank": tp, "pos_score": pos_score})

    # 对邻接笔画应用规则约束
    # 先横后竖：在交叉处横笔优先级提升
    # 先撇后捺：在交叉处撇笔优先级提升
    final_rank = {}
    for info in infos:
        i = info["idx"]
        rank = info["type_rank"] * 1000 + info["pos_score"]
        # 降低 1 级优先级数字 → 更容易被选中
        for j in adj[i]:
            ti, tj = types[i], types[j]
            # 横 vs 竖：横优先
            if ti == "heng" and tj == "shu":
                rank -= 500
            # 撇 vs 捺：撇优先
            if ti == "pie" and tj == "na":
                rank -= 500
        final_rank[i] = rank

    order = sorted(range(n), key=lambda i: final_rank[i])
    return [strokes[i] for i in order]


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
        if a in junc_set and b in junc_set and len(path) <= 50:
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
        if a in junc_set and b in junc_set and len(path) <= 50:
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

    # 7. 二次配对：在每个交叉区对未使用的边按方向连续性配对
    remaining = set(ei for ei in range(len(simp_edges)) if ei not in used_edges)
    short_bridges = set()
    for ei in remaining:
        a, b, path = simp_edges[ei]
        if a in junc_set and b in junc_set and len(path) <= 50:
            short_bridges.add(ei)
    remaining -= short_bridges

    # 按交叉区分组去重
    comp_remaining: Dict[int, List[int]] = defaultdict(list)
    for ei in remaining:
        a, b, _ = simp_edges[ei]
        if a in junc_set:
            comp_remaining[new_comp_id[pt_to_comp[a]]].append(ei)
        if b in junc_set:
            comp_remaining[new_comp_id[pt_to_comp[b]]].append(ei)
    for ci in comp_remaining:
        comp_remaining[ci] = list(set(comp_remaining[ci]))

    paired_in_second = set()
    for ci, edge_list in comp_remaining.items():
        comp_pts = new_to_old_comps.get(ci, set())
        while len(edge_list) >= 2:
            ei_a = edge_list.pop(0)
            best_ei, best_score = None, -1.0
            for ei_b in edge_list:
                score = _simp_edge_pair_score(simp_edges[ei_a], simp_edges[ei_b], comp_pts)
                if score > best_score:
                    best_score = score
                    best_ei = ei_b
            if best_ei is not None and best_score > 0.2:
                edge_list.remove(best_ei)
                merged = _merge_edge_pair(simp_edges[ei_a], simp_edges[ei_b], comp_pts)
                strokes.append(merged)
                paired_in_second.add(ei_a)
                paired_in_second.add(best_ei)
            else:
                _, _, path = simp_edges[ei_a]
                strokes.append(_orient_path(path, endpoints, junc_set))
                paired_in_second.add(ei_a)
        for ei in edge_list:
            _, _, path = simp_edges[ei]
            strokes.append(_orient_path(path, endpoints, junc_set))
            paired_in_second.add(ei)

    # 剩余未在任何交叉区的边（纯端点-端点，step 6 可能漏掉）
    for ei in remaining:
        if ei not in paired_in_second:
            _, _, path = simp_edges[ei]
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
            # 非纯循环但无端点：沿图遍历产生有序点序
            strokes.append(_traverse_component(graph, comp))

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

    # 切断笔画内部的大跳跃（straighten_junctions 或 tracer 引入的伪连接）
    filtered = _break_internal_jumps(filtered)

    # 拆分骨架回溯路径（粗笔画导致的平行骨架线错误连结）
    filtered = _split_backtracks(filtered)

    # 合并被交叉区拆分的共线笔画
    filtered = _merge_collinear_strokes(filtered)

    return filtered


def _break_internal_jumps(
    strokes: List[List[Tuple[int, int]]],
    max_step: float = 200.0,
    min_segment: int = 15,
) -> List[List[Tuple[int, int]]]:
    """在笔画内部的大跳跃处切断（>max_step px），修复骨架伪连接。"""
    result = []
    for stk in strokes:
        if len(stk) < 4:
            result.append(stk)
            continue
        pts = np.array(stk).astype(float)
        steps = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        cut_indices = np.where(steps > max_step)[0]
        if len(cut_indices) == 0:
            result.append(stk)
            continue
        # 在所有跳跃处切断
        prev = 0
        for ci in cut_indices:
            segment = stk[prev:ci + 1]
            if len(segment) >= min_segment:
                result.append(segment)
            prev = ci + 1
        segment = stk[prev:]
        if len(segment) >= min_segment:
            result.append(segment)
    return result


def _merge_junction_fragments(
    strokes: List[List[Tuple[int, int]]],
    junc_radius: float = 5.0,
    max_winding: float = 3.0,
    short_ratio: float = 0.2,
) -> List[List[Tuple[int, int]]]:
    """合并共享同一 junction 的笔画碎片。

    当骨架在笔直笔画中部产生多余 junction 时，tracer 可能把
    一笔拆成两段。此函数查找端点邻接同一 junction 的笔画对，
    若合并后路径不绕路则合并。一方显著短于另一方时放宽要求。
    """
    if len(strokes) <= 1:
        return strokes

    n = len(strokes)
    ends = [(np.array(s[0]).astype(float), np.array(s[-1]).astype(float)) for s in strokes]

    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            for ei in [0, -1]:
                ep_i = ends[i][ei]
                # 检查 j 的端点 vs i 的端点
                for ej in [0, -1]:
                    d = np.linalg.norm(ep_i - ends[j][ej])
                    if d < junc_radius:
                        pairs.append((i, j, ei, ej, d, 'end'))
                # 也检查 j 的碎片端点是否在 i 内部（junction 在笔画中部时）
                pts_j = np.array(strokes[j]).astype(float)
                # 从 j 的端点出发，检查其是否接近 i 内部的某个点
                for pj_idx in [0, -1]:
                    pj = pts_j[pj_idx]
                    # 在 i 中搜索最近点
                    pts_i = np.array(strokes[i]).astype(float)
                    dists = np.linalg.norm(pts_i - pj, axis=1)
                    min_idx = np.argmin(dists)
                    if dists[min_idx] < junc_radius:
                        # j 的 pj_idx 端靠近 i 内部的点 — 在最近处拼接
                        pairs.append((i, j, min_idx, pj_idx, dists[min_idx], 'internal'))

    if not pairs:
        return strokes

    merged = set()
    result = []
    for i in range(n):
        if i in merged:
            continue
        best_j, best_merged = None, None
        best_score = -1.0
        i_pairs = [p for p in pairs if p[0] == i and p[1] not in merged]
        for p_entry in i_pairs:
            pinfo = list(p_entry)
            pi, j, ei, ej, d = pinfo[:5]
            is_internal = len(pinfo) > 5 and pinfo[5] == 'internal'
            si, sj = strokes[i], strokes[j]

            if is_internal:
                # 碎片 j 的 ej 端靠近 i 内部的 ei 位置 —— 在 ei 处插入 j
                cut_at = int(ei)  # ei is the index in si
                # 确定 j 的插入方向：如果 j 的靠近端是 j_start，则 j 正向插入
                if ej == 0:
                    j_segment = list(sj)  # j 从 start 开始
                else:
                    j_segment = list(reversed(sj))  # j 从 end 开始（反转后从 end 走向 start）
                # 在 cut_at 处拼接：si[:cut_at] + j_segment + si[cut_at+1:]
                merged_stk = si[:cut_at] + j_segment + si[cut_at + 1:]
            else:
                # 端点拼接（原有逻辑）
                si_ord = list(si) if ei == -1 else list(reversed(si))
                sj_ord = list(reversed(sj)) if ej == -1 else list(sj)
                merged_stk = si_ord + sj_ord[1:]

            if len(merged_stk) < 4:
                continue
            mpts = np.array(merged_stk).astype(float)
            se = np.linalg.norm(mpts[-1] - mpts[0])
            if se < 1:
                continue
            path = np.sum(np.linalg.norm(np.diff(mpts, axis=0), axis=1))
            len_ratio = min(len(si), len(sj)) / max(len(si), len(sj))
            effective_limit = max(max_winding, 8.0) if len_ratio < short_ratio else max_winding
            if path / se > effective_limit:
                continue
            score = (1.0 - len_ratio) * 0.5 + min(se / (path + 1e-6), 1.0) * 0.5
            if score > best_score:
                best_score = score
                best_j = j
                best_merged = merged_stk

        if best_j is not None:
            result.append(best_merged)
            merged.add(i)
            merged.add(best_j)
        else:
            result.append(strokes[i])
            merged.add(i)

    return result


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

    跳过交叉区边缘最可能扭曲的像素（skip_margin），用远离交叉区的点
    估计真实笔画方向，避免交叉区局部弯折干扰方向判断。
    """
    skip_margin = 6  # 跳过交叉区边缘最可能扭曲的像素
    k = 15
    k = min(k, len(incoming), len(candidate))
    total_needed = k + skip_margin
    if total_needed >= min(len(incoming), len(candidate)):
        k = min(len(incoming), len(candidate)) // 2
        skip_margin = min(3, k // 2)
    if k < 2:
        return 0.0

    # incoming：取远离交叉区的 k 个点（跳过最靠近交叉区的 skip_margin 点）
    start_in = max(0, len(incoming) - skip_margin - k)
    end_in = len(incoming) - skip_margin
    if end_in - start_in < 2:
        start_in = max(0, len(incoming) - k)
        end_in = len(incoming)
    pts_in = np.array(incoming[start_in:end_in]).astype(float)
    dir_in = _pca_direction(pts_in)

    # candidate：跳过靠近交叉区的前 skip_margin 个点，取后续 k 个点
    if candidate[0] in junc_pts:
        start_out = skip_margin
        end_out = min(len(candidate), skip_margin + k)
    else:
        end_out = len(candidate) - skip_margin
        start_out = max(0, end_out - k)
    if end_out - start_out < 2:
        if candidate[0] in junc_pts:
            start_out, end_out = 0, min(len(candidate), k)
        else:
            end_out = len(candidate)
            start_out = max(0, end_out - k)
    pts_out = np.array(candidate[start_out:end_out]).astype(float)
    dir_out = _pca_direction(pts_out)

    na, nb = np.linalg.norm(dir_in), np.linalg.norm(dir_out)
    if na < 1e-6 or nb < 1e-6:
        return 0.0

    cos = np.dot(dir_in / na, dir_out / nb)
    return max(0.0, cos)


def _simp_edge_pair_score(
    edge_a: Tuple, edge_b: Tuple,
    junc_pts: Set[Tuple[int, int]],
) -> float:
    """两条简化边在交叉区处的方向连续性得分。"""
    a_node_a, a_node_b, path_a = edge_a
    b_node_a, b_node_b, path_b = edge_b

    a_end_a_in_comp = a_node_a in junc_pts
    b_end_a_in_comp = b_node_a in junc_pts

    skip_margin = 6
    k = 15
    if k + skip_margin >= min(len(path_a), len(path_b)):
        k = min(len(path_a), len(path_b)) // 2
        skip_margin = min(3, k // 2)
    if k < 2:
        return 0.0

    if a_end_a_in_comp:
        start_a, end_a = skip_margin, min(len(path_a), skip_margin + k)
    else:
        end_a = len(path_a) - skip_margin
        start_a = max(0, end_a - k)
    if end_a - start_a < 2:
        start_a, end_a = 0, min(len(path_a), k)

    if b_end_a_in_comp:
        start_b, end_b = skip_margin, min(len(path_b), skip_margin + k)
    else:
        end_b = len(path_b) - skip_margin
        start_b = max(0, end_b - k)
    if end_b - start_b < 2:
        start_b, end_b = 0, min(len(path_b), k)

    pts_a = np.array(path_a[start_a:end_a]).astype(float)
    pts_b = np.array(path_b[start_b:end_b]).astype(float)

    dir_a = _pca_direction(pts_a)
    dir_b = _pca_direction(pts_b)

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


def _merge_collinear_strokes(
    strokes,
    angle_threshold: float = 30.0,
    dist_threshold: float = 350.0,
):
    """合并被交叉区错误拆分的共线笔画。

    使用端点局部方向（最后/最前 30% 的点）而非全局 PCA，
    以避免复杂笔画（穿过交叉区）的全局方向误导合并判断。
    """
    import numpy as np
    if len(strokes) <= 1:
        return strokes

    n = len(strokes)
    cos_threshold = np.cos(np.radians(angle_threshold))

    # 计算每个笔画的起笔和收笔局部方向
    end_dirs = []   # [(dir_at_start, dir_at_end)]
    for s in strokes:
        pts = np.array(s).astype(float)
        k = max(3, len(pts) // 3)
        # 跳过最靠近 junction 的 8 个点计算局部方向（抗 junction 弯折干扰）
        start_k = min(k, max(3, len(pts) - 8))
        end_k = min(k, max(3, len(pts) - 8))
        start_pts = pts[8:8+start_k] if len(pts) > 8 + start_k else pts[:start_k]
        end_pts = pts[-end_k-8:-8] if len(pts) > end_k + 8 else pts[-end_k:]
        end_dirs.append((_pca_safe(start_pts), _pca_safe(end_pts)))

    merged = set()
    result = []
    for i in range(n):
        if i in merged:
            continue
        best_j, best_score = None, -1.0
        si = strokes[i]
        for j in range(n):
            if i == j or j in merged:
                continue
            sj = strokes[j]
            d00 = np.linalg.norm(np.array(si[0]) - np.array(sj[0]))
            d01 = np.linalg.norm(np.array(si[0]) - np.array(sj[-1]))
            d10 = np.linalg.norm(np.array(si[-1]) - np.array(sj[0]))
            d11 = np.linalg.norm(np.array(si[-1]) - np.array(sj[-1]))
            d = min(d00, d01, d10, d11)
            if d > dist_threshold:
                continue

            # 用连接端的局部方向做共线性判断
            if d == d00:  # si.start ↔ sj.start
                dir_i, dir_j = end_dirs[i][0], end_dirs[j][0]
                gap_vec = np.array(sj[0]) - np.array(si[0])
            elif d == d01:  # si.start ↔ sj.end
                dir_i, dir_j = end_dirs[i][0], end_dirs[j][1]
                gap_vec = np.array(sj[-1]) - np.array(si[0])
            elif d == d10:  # si.end ↔ sj.start
                dir_i, dir_j = end_dirs[i][1], end_dirs[j][0]
                gap_vec = np.array(sj[0]) - np.array(si[-1])
            else:  # si.end ↔ sj.end
                dir_i, dir_j = end_dirs[i][1], end_dirs[j][1]
                gap_vec = np.array(sj[-1]) - np.array(si[-1])

            # 局部方向必须共线
            cos_local = abs(np.dot(dir_i, dir_j))
            if cos_local < cos_threshold:
                continue

            # 间隙方向必须与笔画方向一致（防止把交叉区对面的不同笔画合并）
            gap_norm = np.linalg.norm(gap_vec)
            if gap_norm < 1e-6:
                # 端点重合（共享交叉区/junction）
                gap_align = 1.0  # 共享端点视为完美对齐
            else:
                gap_dir = gap_vec / gap_norm
                gap_align = abs(np.dot(gap_dir, dir_i))
                if gap_align < cos_threshold:
                    continue

            score = cos_local * 2.0 - d / max(dist_threshold, 1) + gap_align
            if score > best_score:
                best_score = score
                best_j = j

        if best_j is not None:
            si, sj = strokes[i], strokes[best_j]
            d00 = np.linalg.norm(np.array(si[0]) - np.array(sj[0]))
            d01 = np.linalg.norm(np.array(si[0]) - np.array(sj[-1]))
            d10 = np.linalg.norm(np.array(si[-1]) - np.array(sj[0]))
            d11 = np.linalg.norm(np.array(si[-1]) - np.array(sj[-1]))
            best_pair = min([(d00, 0, 0), (d01, 0, -1), (d10, -1, 0), (d11, -1, -1)], key=lambda x: x[0])
            _, si_end, sj_end = best_pair
            if si_end == 0:
                si_ordered = list(reversed(si))
            else:
                si_ordered = list(si)
            if sj_end == 0:
                sj_ordered = list(sj)
            else:
                sj_ordered = list(reversed(sj))
            result.append(si_ordered + sj_ordered[1:])
            merged.add(i)
            merged.add(best_j)
        else:
            result.append(strokes[i])
            merged.add(i)
    return result


def _pca_safe(pts: np.ndarray) -> np.ndarray:
    """返回点集的归一化 PCA 主方向，点太少时退化为首尾方向。"""
    import numpy as np
    if len(pts) < 2:
        return np.array([0.0, 0.0])
    if len(pts) == 2:
        v = pts[-1] - pts[0]
        n = np.linalg.norm(v)
        return v / n if n > 1e-6 else np.array([0.0, 0.0])
    centered = pts - pts.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    v = eigenvectors[:, -1]
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else np.array([0.0, 0.0])


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


def _traverse_component(graph: Dict, comp: Set[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """从comp中任一点沿graph边遍历，产生有序点序列，避免set迭代的随机序。"""
    if not comp:
        return []
    start = next(iter(comp))
    ordered = [start]
    visited = {start}
    cur = start
    while len(visited) < len(comp):
        nxt = None
        for nb in graph.get(cur, []):
            if nb in comp and nb not in visited:
                nxt = nb
                break
        if nxt is None:
            for p in comp:
                if p not in visited:
                    nxt = p
                    break
        if nxt is None:
            break
        ordered.append(nxt)
        visited.add(nxt)
        cur = nxt
    return ordered


def _split_backtracks(
    strokes: List[List[Tuple[int, int]]],
    spatial_threshold: float = 25.0,
    path_threshold: float = 200.0,
    min_stroke_len: int = 20,
    keep_ratio: float = 0.15,
) -> List[List[Tuple[int, int]]]:
    """拆分含有回溯路径的笔画，丢弃过短的回溯碎片。

    Zhang-Suen 在粗笔画上会产生平行双线，tracer 可能把两条线错误连成
    一个「走到底→回头→再走」的回溯笔画。此函数检测路径上空间邻近但
    路径距离远的点对，在回溯点切开，只保留长段（短段是回溯产物）。

    keep_ratio: 短段/长段长度比低于此值则丢弃短段。
    """
    if not strokes:
        return strokes

    result = []
    for stk in strokes:
        if len(stk) < 20:
            result.append(stk)
            continue

        pts = np.array(stk).astype(float)
        n = len(pts)

        seg_lens = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        cum_dist = np.zeros(n)
        cum_dist[1:] = np.cumsum(seg_lens)

        cut_at = None
        for i in range(0, n - 10, 5):
            j_start = i + 50
            j_end = min(i + 300, n)
            for j in range(j_start, j_end, 5):
                spatial_d = np.linalg.norm(pts[i] - pts[j])
                path_d = cum_dist[j] - cum_dist[i]
                if spatial_d < spatial_threshold and path_d > path_threshold:
                    cut_at = (i + j) // 2
                    break
            if cut_at is not None:
                break

        if cut_at is None:
            result.append(stk)
            continue

        part1 = stk[:cut_at]
        part2 = stk[cut_at + 1:]

        # 保留长段，丢弃显著更短的碎片
        longer, shorter = (part1, part2) if len(part1) >= len(part2) else (part2, part1)

        if len(shorter) < len(longer) * keep_ratio:
            # 短段是回溯产物，丢弃
            if len(longer) >= min_stroke_len:
                result.extend(_split_backtracks(
                    [longer], spatial_threshold, path_threshold, min_stroke_len, keep_ratio
                ))
            else:
                result.append(stk)
        else:
            # 两段都有效（可能是交叉区的两个独立笔画）
            if len(part1) >= min_stroke_len:
                result.append(part1)
            if len(part2) >= min_stroke_len:
                result.extend(_split_backtracks(
                    [part2], spatial_threshold, path_threshold, min_stroke_len, keep_ratio
                ))

    return result


def _pca_direction(pts: np.ndarray) -> np.ndarray:
    """返回点集的主成分方向向量（比首尾向量更抗弯折干扰）。"""
    if len(pts) < 2:
        return np.array([0.0, 0.0])
    centered = pts - pts.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    principal = eigenvectors[:, -1]
    if np.dot(principal, pts[-1] - pts[0]) < 0:
        principal = -principal
    return principal


# ── 笔画分类 ──────────────────────────────────────────────

def classify_stroke(stroke: List[Tuple[int, int]]) -> str:
    """按几何特征将笔画分为 heng/shu/pie/na/dian/gou/zhe。

    使用 PCA 主导方向 + 曲率分析，不依赖训练数据。
    """
    if len(stroke) < 2:
        return "dian"

    pts = np.array(stroke).astype(float)
    start_end_vec = pts[-1] - pts[0]
    total_len = np.linalg.norm(start_end_vec)

    # 极短笔画 → 点
    if len(pts) < 8 or total_len < 10:
        return "dian"

    # PCA 主导方向
    dy, dx = _pca_direction(pts)
    deg_from_vertical = abs(np.degrees(np.arctan2(dx, dy)))

    # 曲率分析：最后 20% 是否急弯（钩）
    has_hook = False
    if len(pts) > 10:
        split = int(len(pts) * 0.8)
        main_dir = pts[split] - pts[0]
        hook_dir = pts[-1] - pts[split]
        n_main = np.linalg.norm(main_dir)
        n_hook = np.linalg.norm(hook_dir)
        if n_main > 2 and n_hook > 2:
            cos_hook = np.dot(main_dir, hook_dir) / (n_main * n_hook)
            if cos_hook < 0.5:  # > 60°
                has_hook = True

    # 曲率分析：中间是否有方向突变（折）
    has_zhe = False
    if len(pts) > 15:
        third = len(pts) // 3
        d1 = pts[third] - pts[0]
        d2 = pts[-1] - pts[2 * third]
        n1, n2 = np.linalg.norm(d1), np.linalg.norm(d2)
        if n1 > 3 and n2 > 3:
            cos_zhe = np.dot(d1, d2) / (n1 * n2)
            if cos_zhe < 0.3:  # > 72°
                has_zhe = True

    if has_zhe:
        return "zhe"
    if has_hook:
        return "gou"

    # 按主导方向分类
    if deg_from_vertical > 70:
        return "heng"
    if deg_from_vertical < 20:
        return "shu"

    # 斜向笔画：左下 = 撇，右下 = 捺
    if dy > 0 and dx < 0:
        return "pie"
    if dy > 0 and dx > 0:
        return "na"

    return "unknown"


def _strokes_adjacent(
    s1: List[Tuple[int, int]], s2: List[Tuple[int, int]], threshold: int = 8
) -> bool:
    """判断两个笔画是否通过端点邻近（共享交叉区）。"""
    eps1 = [(s1[0], s1[-1])]
    eps2 = [(s2[0], s2[-1])]
    for ep1 in eps1[0]:
        for ep2 in eps2[0]:
            if np.linalg.norm(np.array(ep1) - np.array(ep2)) < threshold:
                return True
    return False
