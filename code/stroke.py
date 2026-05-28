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

# 交叉区配对调试开关（默认关闭，排查配对问题时开启）
_DEBUG_JUNCTION_PAIRING = False

_TRACE_CONTEXT_CHAR: Optional[str] = None
_LAST_TRACE_DIAGNOSTICS: Dict[str, object] = {}
_LOCAL_EXPECTED_COUNTS = {
    "yi": 1,
    "san": 3,
    "kou": 3,
    "tian": 5,
}
_SIMPLE_SAFE_GLOBAL_CHARS = {"yi", "san", "chuan", "kou"}


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


def set_trace_context(char_name: Optional[str] = None):
    """Set optional per-image context for safe global selection diagnostics."""
    global _TRACE_CONTEXT_CHAR
    _TRACE_CONTEXT_CHAR = char_name


def get_last_trace_diagnostics() -> Dict[str, object]:
    """Return diagnostics from the latest stroke extraction call."""
    return dict(_LAST_TRACE_DIAGNOSTICS)


def _stroke_path_len(stroke: List[Tuple[int, int]]) -> float:
    if len(stroke) < 2:
        return 0.0
    pts = np.array(stroke).astype(float)
    return float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))


def _stroke_winding(stroke: List[Tuple[int, int]]) -> float:
    if len(stroke) < 2:
        return 0.0
    pts = np.array(stroke).astype(float)
    se = np.linalg.norm(pts[-1] - pts[0])
    if se < 1:
        return 999.0
    return _stroke_path_len(stroke) / float(se)


def _stroke_summary(strokes: List[List[Tuple[int, int]]]) -> Dict[str, object]:
    lengths = [len(s) for s in strokes]
    path_total = sum(_stroke_path_len(s) for s in strokes)
    winding = [_stroke_winding(s) for s in strokes]
    return {
        "count": len(strokes),
        "points": int(sum(lengths)),
        "lengths": lengths,
        "path_total": float(path_total),
        "max_winding": float(max(winding)) if winding else 0.0,
    }


def _expected_count_for_context(char_name: Optional[str]) -> Optional[int]:
    if not char_name:
        return None
    key = char_name.lower()
    if key in _LOCAL_EXPECTED_COUNTS:
        return _LOCAL_EXPECTED_COUNTS[key]
    try:
        from stroke_knowledge import get_stroke_count
        return get_stroke_count(key)
    except Exception:
        return None


def _safe_global_decision(
    char_name: Optional[str],
    skeleton_px: int,
    legacy: List[List[Tuple[int, int]]],
    global_strokes: List[List[Tuple[int, int]]],
    expected_count: Optional[int],
) -> Tuple[bool, str]:
    if not global_strokes:
        return False, "global_empty"

    gsum = _stroke_summary(global_strokes)
    lsum = _stroke_summary(legacy)
    key = (char_name or "").lower()

    if gsum["points"] > max(skeleton_px * 1.35, lsum["points"] * 1.25):
        return False, "global_overcovers_skeleton"
    if gsum["max_winding"] > 4.5:
        return False, "global_high_winding"

    if expected_count is not None:
        if abs(gsum["count"] - expected_count) > abs(lsum["count"] - expected_count):
            return False, "global_count_farther_from_expected"
        if key not in _SIMPLE_SAFE_GLOBAL_CHARS and gsum["count"] != expected_count:
            return False, "global_count_not_expected_for_complex"

    if key in _SIMPLE_SAFE_GLOBAL_CHARS:
        if expected_count is not None and gsum["count"] == expected_count:
            return True, "simple_expected_count_match"
        if gsum["count"] < lsum["count"] and gsum["points"] <= max(skeleton_px * 1.20, lsum["points"] * 1.10):
            return True, "simple_reduced_fragmentation"

    if expected_count is not None and gsum["count"] == expected_count and lsum["count"] != expected_count:
        return True, "expected_count_improved"

    return False, "legacy_preferred_conservative_gate"


def _merge_strokes_as_row(strokes: List[List[Tuple[int, int]]]) -> List[Tuple[int, int]]:
    ordered = sorted(strokes, key=lambda s: float(np.mean([p[1] for p in s])) if s else 0.0)
    merged: List[Tuple[int, int]] = []
    for stroke in ordered:
        if not stroke:
            continue
        pts = list(stroke)
        if pts[0][1] > pts[-1][1]:
            pts = list(reversed(pts))
        if not merged:
            merged = pts
        else:
            merged.extend(pts)
    return merged


def _glyph_bbox_from_strokes(
    strokes: List[List[Tuple[int, int]]],
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    pts = [np.array(stroke).astype(float) for stroke in strokes if len(stroke) > 0]
    if not pts:
        return None
    all_pts = np.vstack(pts)
    return all_pts.min(axis=0), all_pts.max(axis=0)


def _is_right_frame_detour(
    stroke: List[Tuple[int, int]],
    glyph_bbox: Tuple[np.ndarray, np.ndarray],
    ratio_threshold: float = 1.6,
) -> bool:
    if len(stroke) < 2:
        return False
    pts = np.array(stroke).astype(float)
    (glyph_y0, glyph_x0), (glyph_y1, glyph_x1) = glyph_bbox
    glyph_h = max(1.0, glyph_y1 - glyph_y0)
    glyph_w = max(1.0, glyph_x1 - glyph_x0)
    s_y0, s_x0 = pts.min(axis=0)
    s_y1, s_x1 = pts.max(axis=0)
    right_anchored = (s_x1 - glyph_x0) / glyph_w > 0.88
    starts_in_right_half = (s_x0 - glyph_x0) / glyph_w > 0.35
    touches_top = (s_y0 - glyph_y0) / glyph_h < 0.12
    tall = (s_y1 - s_y0) / glyph_h > 0.45
    wide = (s_x1 - s_x0) / glyph_w > 0.45
    return (
        right_anchored
        and starts_in_right_half
        and touches_top
        and tall
        and wide
        and _stroke_winding(stroke) > ratio_threshold
    )


def _split_at_max_chord_deviation(
    stroke: List[Tuple[int, int]],
) -> Optional[Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]]:
    if len(stroke) < 20:
        return None
    pts = np.array(stroke).astype(float)
    chord = pts[-1] - pts[0]
    chord_len = np.linalg.norm(chord)
    if chord_len < 1:
        return None
    lo = max(8, int(len(stroke) * 0.15))
    hi = min(len(stroke) - 8, int(len(stroke) * 0.85))
    if hi <= lo:
        return None
    offsets = pts[lo:hi] - pts[0]
    # 2-D point-to-line distance using scalar cross product.
    distances = np.abs(chord[0] * offsets[:, 1] - chord[1] * offsets[:, 0]) / chord_len
    cut_idx = lo + int(np.argmax(distances))
    left = list(stroke[:cut_idx + 1])
    right = list(stroke[cut_idx:])
    if len(left) < 5 or len(right) < 5:
        return None
    return left, right


def _split_closed_structure_detours(
    strokes: List[List[Tuple[int, int]]],
) -> Tuple[List[List[Tuple[int, int]]], bool]:
    glyph_bbox = _glyph_bbox_from_strokes(strokes)
    if glyph_bbox is None:
        return strokes, False
    repaired: List[List[Tuple[int, int]]] = []
    changed = False
    for stroke in strokes:
        needs_split = (
            _stroke_winding(stroke) > 3.0
            or _is_right_frame_detour(stroke, glyph_bbox)
        )
        split = _split_at_max_chord_deviation(stroke) if needs_split else None
        if split is None:
            repaired.append(stroke)
            continue
        left, right = split
        if max(_stroke_winding(left), _stroke_winding(right)) >= _stroke_winding(stroke):
            repaired.append(stroke)
            continue
        repaired.extend([left, right])
        changed = True
    return repaired, changed


def _split_extreme_winding_strokes(
    strokes: List[List[Tuple[int, int]]],
    winding_threshold: float = 5.0,
) -> List[List[Tuple[int, int]]]:
    repaired: List[List[Tuple[int, int]]] = []
    for stroke in strokes:
        original_winding = _stroke_winding(stroke)
        if original_winding <= winding_threshold:
            repaired.append(stroke)
            continue
        split = _split_at_max_chord_deviation(stroke)
        if split is None:
            repaired.append(stroke)
            continue
        left, right = split
        if max(_stroke_winding(left), _stroke_winding(right)) >= original_winding:
            repaired.append(stroke)
            continue
        repaired.extend([left, right])
    return repaired


def _split_mid_winding_open_strokes(
    char_name: Optional[str],
    strokes: List[List[Tuple[int, int]]],
    winding_threshold: float = 4.0,
) -> Tuple[List[List[Tuple[int, int]]], bool]:
    key = (char_name or "").lower()
    if key in {"kou", "tian", "zhong"}:
        return strokes, False
    repaired = _split_extreme_winding_strokes(
        strokes, winding_threshold=winding_threshold
    )
    return repaired, len(repaired) != len(strokes)


def _merge_by_closest_endpoints(
    first: List[Tuple[int, int]],
    second: List[Tuple[int, int]],
) -> Tuple[float, List[Tuple[int, int]]]:
    pairs = [
        (np.linalg.norm(np.array(first[0], dtype=float) - np.array(second[0], dtype=float)), 0, 0),
        (np.linalg.norm(np.array(first[0], dtype=float) - np.array(second[-1], dtype=float)), 0, -1),
        (np.linalg.norm(np.array(first[-1], dtype=float) - np.array(second[0], dtype=float)), -1, 0),
        (np.linalg.norm(np.array(first[-1], dtype=float) - np.array(second[-1], dtype=float)), -1, -1),
    ]
    distance, first_end, second_end = min(pairs, key=lambda item: item[0])
    ordered_first = list(reversed(first)) if first_end == 0 else list(first)
    ordered_second = list(second) if second_end == 0 else list(reversed(second))
    return float(distance), ordered_first + ordered_second[1:]


def _merge_closed_structure_safely(
    strokes: List[List[Tuple[int, int]]],
    target_count: int,
    max_distance: float = 140.0,
    max_winding: float = 2.4,
) -> Tuple[List[List[Tuple[int, int]]], bool]:
    if len(strokes) <= target_count:
        return strokes, False
    result = [list(stroke) for stroke in strokes]
    changed = False
    while len(result) > target_count:
        glyph_bbox = _glyph_bbox_from_strokes(result)
        best = None
        for i in range(len(result)):
            for j in range(i + 1, len(result)):
                distance, merged = _merge_by_closest_endpoints(result[i], result[j])
                if distance > max_distance:
                    continue
                winding = _stroke_winding(merged)
                if winding > max_winding:
                    continue
                if glyph_bbox is not None and _is_right_frame_detour(merged, glyph_bbox):
                    continue
                score = distance + winding * 80.0
                if best is None or score < best[0]:
                    best = (score, i, j, merged)
        if best is None:
            break
        _, i, j, merged = best
        next_result = []
        for idx, stroke in enumerate(result):
            if idx == i:
                next_result.append(merged)
            elif idx != j:
                next_result.append(stroke)
        result = next_result
        changed = True
    return result, changed


def _simple_count_prior(
    char_name: Optional[str],
    selected: List[List[Tuple[int, int]]],
    legacy: List[List[Tuple[int, int]]],
    global_strokes: List[List[Tuple[int, int]]],
    expected_count: Optional[int],
) -> Tuple[List[List[Tuple[int, int]]], Optional[str]]:
    key = (char_name or "").lower()
    if key == "yi" and expected_count == 1:
        pool = [s for s in (legacy + global_strokes) if len(s) >= 5]
        if not pool:
            return selected, None
        return [max(pool, key=len)], "simple_prior_longest_main_stroke"

    if key == "san" and expected_count == 3:
        base = legacy if legacy else selected
        if len(base) <= 3:
            return selected, None
        infos = []
        for stroke in base:
            if not stroke:
                continue
            ys = [p[0] for p in stroke]
            infos.append((float(np.mean(ys)), stroke))
        if len(infos) < 3:
            return selected, None
        infos.sort(key=lambda item: item[0])
        groups = [[] for _ in range(3)]
        for idx, (_, stroke) in enumerate(infos):
            group_idx = min(2, int(idx * 3 / len(infos)))
            groups[group_idx].append(stroke)
        merged = [_merge_strokes_as_row(group) for group in groups if group]
        if len(merged) == 3:
            return merged, "simple_prior_three_rows"

    if key == "tian":
        repaired, changed = _split_closed_structure_detours(selected)
        if changed:
            return repaired, "closed_prior_split_frame_detour"

    if key == "zhong" and expected_count == 4:
        repaired, changed = _merge_closed_structure_safely(selected, expected_count)
        if changed and len(repaired) == expected_count:
            return repaired, "closed_prior_safe_count_merge"

    return selected, None


def _build_simplified_graph(
    skeleton: np.ndarray,
) -> Tuple[List, Set, Dict, Dict, Dict, Dict, Set]:
    """构建简化图：端点+交叉区→压缩 deg-2 链→合并短桥交叉区。

    Returns:
        simp_edges: List[(node_a, node_b, path_pixels)]
        ep_set: Set[pt] — 所有端点
        ep_to_edge: Dict[pt, edge_idx] — 端点→其唯一边
        comp_to_edges: Dict[comp_id, List[edge_idx]] — 交叉区→关联边
        new_comp_id: Dict[old_comp_id, new_comp_id] — 合并后映射
        new_to_old_comps: Dict[new_comp_id, Set[pt]] — 新分量→旧交叉区像素
        junc_set: Set[pt] — 所有原始交叉区像素
    """
    graph = build_skeleton_graph(skeleton)
    endpoints = [pt for pt, nb in graph.items() if len(nb) == 1]
    raw_junctions = [pt for pt, nb in graph.items() if len(nb) >= 3]

    ep_set = set(endpoints)
    junc_set = set(raw_junctions)

    if not raw_junctions:
        return [], ep_set, {}, {}, {}, {}, junc_set

    # 1. 聚类交叉点（8-连通）
    junc_components = _cluster_junc_pixels(junc_set, graph)

    # 2. pt → old component index
    pt_to_comp = {}
    for ci, comp in enumerate(junc_components):
        for pt in comp:
            pt_to_comp[pt] = ci

    # 3. 压缩 deg-2 链 → simp_edges
    special_nodes = ep_set | junc_set
    simp_edges = []
    visited_pairs = set()

    for sn in special_nodes:
        for nb in graph.get(sn, []):
            path = [sn, nb]
            prev, cur = sn, nb
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
                pair = (sn, cur, nb) if sn == cur else ((sn, cur) if sn <= cur else (cur, sn))
                if pair not in visited_pairs:
                    visited_pairs.add(pair)
                    simp_edges.append((sn, cur, path))

    # 4. Union-Find 合并短桥连通的交叉分量
    n_comp = len(junc_components)
    comp_parent = list(range(n_comp))
    def _find(i):
        while comp_parent[i] != i:
            comp_parent[i] = comp_parent[comp_parent[i]]
            i = comp_parent[i]
        return i
    def _union(i, j):
        ri, rj = _find(i), _find(j)
        if ri != rj:
            comp_parent[ri] = rj

    for a, b, path in simp_edges:
        if a in junc_set and b in junc_set and len(path) <= 50:
            _union(pt_to_comp[a], pt_to_comp[b])

    # Remap old → new
    new_comp_id: Dict[int, int] = {}
    comp_groups: Dict[int, List[int]] = defaultdict(list)
    for ci in range(n_comp):
        root = _find(ci)
        comp_groups[root].append(ci)
    for new_id, (root, old_ids) in enumerate(comp_groups.items()):
        for oi in old_ids:
            new_comp_id[oi] = new_id

    # 5. 构建索引 (ep_to_edge, comp_to_edges)
    ep_to_edge: Dict[Tuple, int] = {}
    comp_to_edges: Dict[int, List[int]] = defaultdict(list)

    for ei, (a, b, path) in enumerate(simp_edges):
        # 跳过用于合并的短桥
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

    # 6. 新分量→旧交叉区像素映射
    new_to_old_comps: Dict[int, Set[Tuple[int, int]]] = {}
    for old_ci, new_ci in new_comp_id.items():
        if new_ci not in new_to_old_comps:
            new_to_old_comps[new_ci] = set()
        new_to_old_comps[new_ci] |= junc_components[old_ci]

    if _DEBUG_JUNCTION_PAIRING:
        _log_junction_structure(simp_edges, junc_components, comp_groups,
                                new_comp_id, pt_to_comp, ep_set, junc_set)

    return simp_edges, ep_set, ep_to_edge, comp_to_edges, new_comp_id, new_to_old_comps, junc_set, pt_to_comp


def _log_junction_structure(simp_edges, junc_components, comp_groups,
                            new_comp_id, pt_to_comp, ep_set, junc_set):
    """打印合并后的交叉区结构和关联边。"""
    total_junc_px = sum(len(c) for c in junc_components)
    n_comps = len(comp_groups)
    print(f'\n=== Junction structure after merging ===')
    print(f'  Raw junctions: {total_junc_px} px in {len(junc_components)} clusters')
    print(f'  After merge: {n_comps} components')
    for new_ci, old_ids in comp_groups.items():
        total_px = sum(len(junc_components[oi]) for oi in old_ids)
        print(f'  Comp{new_ci}: {len(old_ids)} old clusters, {total_px} junc px')
    print(f'  Simplified edges: {len(simp_edges)} total')
    for ci in range(n_comps):
        edges_here = []
        for ei, (a, b, path) in enumerate(simp_edges):
            if a in junc_set and b in junc_set and len(path) <= 50:
                continue
            a_here = a in junc_set and new_comp_id.get(pt_to_comp.get(a, -1), -1) == ci
            b_here = b in junc_set and new_comp_id.get(pt_to_comp.get(b, -1), -1) == ci
            if a_here or b_here:
                epts = np.array(path).astype(float)
                edir = _pca_direction(epts) if len(epts) >= 2 else np.array([0.0, 0.0])
                e_se = np.linalg.norm(epts[-1] - epts[0]) if len(epts) >= 2 else 0
                edges_here.append((ei, len(path), e_se, edir))
        if edges_here:
            print(f'  Comp{ci} incident edges ({len(edges_here)}):')
            for ei, plen, se, edir in edges_here:
                ea, eb, _ = simp_edges[ei]
                a_info = 'ep' if ea in ep_set else f'J{new_comp_id.get(pt_to_comp.get(ea,-1),-1)}'
                b_info = 'ep' if eb in ep_set else f'J{new_comp_id.get(pt_to_comp.get(eb,-1),-1)}'
                print(f'    edge{ei} len={plen:4d} SE={se:5.0f} dir=({edir[0]:.2f},{edir[1]:.2f}) ends=({a_info},{b_info})')
    print()


# ═══════════════════════════════════════════════════════════════
# 全局代价评分 + 候选路径生成 + 贪心覆盖选择
# ═══════════════════════════════════════════════════════════════

# 评分权重
_W_CONTINUITY = 2.0
_W_WINDING = -1.5
_W_COVERAGE = 0.3
_W_CLOSED = 1.0
_W_SPUR = -4.0
_W_COUNT = -2.0


def _generate_candidates(
    ep_set: Set, simp_edges: List, ep_to_edge: Dict,
    comp_to_edges: Dict, new_comp_id: Dict,
    new_to_old_comps: Dict, pt_to_comp: Dict,
    max_branch: int = 4, max_depth: int = 5,
) -> List[Tuple[List[int], List[Tuple]]]:
    """从每个端点 DFS 生成所有端点→端点候选路径。

    Returns: [(edge_indices, full_path_points), ...]
    """
    candidates = []
    junc_set = set()
    for comp_pts in new_to_old_comps.values():
        junc_set |= comp_pts

    for ep in ep_set:
        if ep not in ep_to_edge:
            continue
        start_ei = ep_to_edge[ep]
        # DFS stack: (cur_edge_idx, cur_node, edge_path_indices, full_points, depth)
        a, b, path = simp_edges[start_ei]
        next_node = b if a == ep else a
        oriented = path if a == ep else list(reversed(path))
        stack = [(start_ei, next_node, [start_ei], oriented[:], 1)]

        while stack:
            cur_ei, cur_node, ei_list, pts_sofar, depth = stack.pop()

            if cur_node in ep_set:
                candidates.append((ei_list, pts_sofar))
                continue

            if depth > max_depth:
                continue

            # 到达交叉区：枚举候选延续边
            ci = new_comp_id.get(pt_to_comp.get(cur_node, -1), -1)
            if ci < 0 or ci not in comp_to_edges:
                continue

            cand_edges = [(ei2, simp_edges[ei2]) for ei2 in comp_to_edges[ci]
                         if ei2 not in ei_list]
            if not cand_edges:
                continue

            # 按方向连续性排序，取 top max_branch
            scored = []
            for ei2, (a2, b2, path2) in cand_edges:
                score = _continuity_at_junction(pts_sofar, path2, new_to_old_comps.get(ci, set()))
                scored.append((score, ei2, a2, b2, path2))
            scored.sort(key=lambda x: x[0], reverse=True)

            for score, ei2, a2, b2, path2 in scored[:max_branch]:
                if score < 0.05:
                    continue
                next_n = b2 if a2 == cur_node else a2
                orient2 = path2 if a2 == cur_node else list(reversed(path2))
                new_pts = pts_sofar + orient2[1:]
                stack.append((ei2, next_n, ei_list + [ei2], new_pts, depth + 1))

    return candidates


def _score_candidate(
    ei_list: List[int], pts: List[Tuple],
    simp_edges: List, new_comp_id: Dict, new_to_old_comps: Dict, pt_to_comp: Dict,
    all_edges_se: List[float], median_se: float,
    is_closed: bool,
) -> Tuple[float, Dict[str, float]]:
    """对一条候选路径做全局评分，返回 (total, components_dict)。"""
    comps = {}

    # 1. 方向连续性（相邻边在连接处的方向余弦均值）
    if len(ei_list) >= 2:
        cont_scores = []
        for k in range(len(ei_list) - 1):
            _, _, path_k = simp_edges[ei_list[k]]
            _, _, path_k1 = simp_edges[ei_list[k + 1]]
            cs = _fallback_continuity(path_k, path_k1)
            cont_scores.append(cs)
        comps['continuity'] = np.mean(cont_scores) if cont_scores else 0.0
    else:
        comps['continuity'] = 1.0

    # 2. 绕路惩罚
    pts_arr = np.array(pts).astype(float)
    se = np.linalg.norm(pts_arr[-1] - pts_arr[0])
    path_len = np.sum(np.linalg.norm(np.diff(pts_arr, axis=0), axis=1))
    winding = path_len / se if se > 1 else 1.0
    comps['winding'] = max(0.0, winding - 2.0)

    # 3. 覆盖奖励
    comps['coverage'] = np.log(1.0 + path_len)

    # 4. 闭合结构保护
    comps['closed'] = 1.0 if is_closed else 0.0

    # 5. 毛刺惩罚
    if len(ei_list) == 1 and se < median_se * 0.25:
        comps['spur'] = 1.0
    else:
        comps['spur'] = 0.0

    # 加权汇总
    total = (
        _W_CONTINUITY * comps['continuity'] +
        _W_WINDING * comps['winding'] +
        _W_COVERAGE * comps['coverage'] +
        _W_CLOSED * comps['closed'] +
        _W_SPUR * comps['spur']
    )
    return total, comps


def _fallback_continuity(path_a, path_b):
    """Fallback: 用两端 PCA 方向余弦估计连续性。"""
    pts_a = np.array(path_a).astype(float)
    pts_b = np.array(path_b).astype(float)
    dir_a = _pca_direction(pts_a[-15:]) if len(pts_a) >= 15 else _pca_direction(pts_a)
    dir_b = _pca_direction(pts_b[:15]) if len(pts_b) >= 15 else _pca_direction(pts_b)
    cos = np.dot(dir_a, dir_b)
    if cos < -0.7:
        return 0.0
    if cos > 0.5:
        return cos
    return 0.3


def _select_strokes_global(
    candidates: List[Tuple[List[int], List[Tuple], float]],
    simp_edges: List, total_edges: int,
    expected_count: Optional[int],
    junc_set: Set,
) -> List[Tuple[List[int], List[Tuple]]]:
    """贪心选择最优笔画集合覆盖所有边，动态 count_prior。"""
    if not candidates:
        return []

    # 按初始分数排序
    ranked = list(candidates)
    ranked.sort(key=lambda c: c[2], reverse=True)
    covered = set()
    selected = []

    # 预估平均每笔边数
    avg_edges_per_stroke = max(1.0, total_edges / max(1, expected_count or 5))

    while len(covered) < total_edges and ranked:
        best_idx, best_score = None, -float('inf')

        for idx, (ei_list, pts, base_score) in enumerate(ranked):
            new_edges = set(ei_list) - covered
            if not new_edges:
                continue
            overlap_edges = set(ei_list) & covered

            # 动态 count_prior
            count_penalty = 0.0
            if expected_count is not None:
                remaining = total_edges - len(covered)
                est_remaining = remaining / avg_edges_per_stroke
                current_total = len(selected) + est_remaining
                count_penalty = _W_COUNT * abs(current_total - expected_count)

            novelty = len(new_edges) / max(1, len(set(ei_list)))
            overlap_penalty = 2.0 * len(overlap_edges)
            score = base_score + count_penalty + (2.5 * novelty) - overlap_penalty
            if score > best_score:
                best_score = score
                best_idx = idx

        if best_idx is None:
            break

        ei_list, pts, _ = ranked[best_idx]
        covered.update(ei_list)
        selected.append((ei_list, pts))
        # 移除已选候选（避免重复选择相同边集）
        ranked[best_idx] = ([], [], -float('inf'))

    return selected


def _extract_strokes_global(
    skeleton: np.ndarray,
    expected_count: Optional[int] = None,
) -> List[List[Tuple[int, int]]]:
    """全局优化笔画提取：候选生成 + 代价评分 + 贪心覆盖。

    当 expected_count 提供时启用 count_prior 分量。
    """
    graph = build_skeleton_graph(skeleton)
    endpoints = [pt for pt, nb in graph.items() if len(nb) == 1]
    raw_junctions = [pt for pt, nb in graph.items() if len(nb) >= 3]

    if not endpoints:
        return []
    if not raw_junctions:
        return _pair_endpoints_directly(graph, endpoints)

    ep_set = set(endpoints)
    junc_set = set(raw_junctions)
    simp_edges, ep_set2, ep_to_edge, comp_to_edges, new_comp_id, new_to_old_comps, junc_set2, pt_to_comp = \
        _build_simplified_graph(skeleton)

    if not simp_edges:
        return []

    # 计算 SE 中位数（用于毛刺判断）
    all_se = []
    for _, _, path in simp_edges:
        pts = np.array(path).astype(float)
        se = np.linalg.norm(pts[-1] - pts[0])
        all_se.append(se)
    median_se = np.median(all_se) if all_se else 100

    # 识别闭环边（junction→junction 且两端在同一交叉区）
    # 用于闭合结构保护
    closed_edge_indices = set()
    for ei, (a, b, path) in enumerate(simp_edges):
        if a in junc_set and b in junc_set and len(path) > 50:
            closed_edge_indices.add(ei)

    # 生成候选
    raw_candidates = _generate_candidates(
        ep_set2, simp_edges, ep_to_edge, comp_to_edges,
        new_comp_id, new_to_old_comps, pt_to_comp,
        max_branch=6, max_depth=8,
    )

    if _DEBUG_JUNCTION_PAIRING:
        print(f'  [GLOBAL] Generated {len(raw_candidates)} candidates from {len(ep_set2)} endpoints')

    # 评分
    total_edges = sum(1 for ei, (a, b, _) in enumerate(simp_edges)
                      if not (a in junc_set and b in junc_set and len(_) <= 50))
    scored = []
    for ei_list, pts in raw_candidates:
        is_closed = any(ei in closed_edge_indices for ei in ei_list)
        score, comps = _score_candidate(
            ei_list, pts, simp_edges, new_comp_id, new_to_old_comps, pt_to_comp,
            all_se, median_se, is_closed,
        )
        scored.append((ei_list, pts, score))
        if _DEBUG_JUNCTION_PAIRING and score > 0:
            cont_str = ', '.join(f'{k}={v:.2f}' for k, v in comps.items())
            print(f'    candidate [{len(ei_list)} edges, {len(pts)} pts] score={score:.2f} ({cont_str})')

    # 选择最优覆盖
    selected_candidates = _select_strokes_global(
        scored, simp_edges, total_edges, expected_count, junc_set,
    )
    strokes = [pts for _, pts in selected_candidates]

    # 收集已覆盖的边（通过匹配选中笔画的起止点与候选路径）
    used_edges = set()
    for ei_list, _ in selected_candidates:
        used_edges.update(ei_list)

    # 处理未覆盖边：复用现有 step 7 贪心配对逻辑
    remaining = set(range(len(simp_edges))) - used_edges
    short_bridges = {ei for ei in remaining
                     if simp_edges[ei][0] in junc_set and simp_edges[ei][1] in junc_set
                     and len(simp_edges[ei][2]) <= 50}
    remaining -= short_bridges

    if remaining:
        for ei in remaining:
            _, _, path = simp_edges[ei]
            strokes.append(_orient_path(path, endpoints, junc_set))

    # 处理循环
    all_visited = set()
    for s in strokes:
        all_visited.update(s)
    for _, _, path in simp_edges:
        all_visited.update(path)

    unvisited = set(graph.keys()) - all_visited
    while unvisited:
        start = unvisited.pop()
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
            strokes.append(_traverse_component(graph, comp))

    # 后处理（复用现有）
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

    filtered = _filter_endpoint_spurs(filtered)
    filtered = _despike_zigzag(filtered)
    filtered = _split_extreme_winding_strokes(filtered)
    filtered = _break_internal_jumps(filtered)
    filtered = _split_backtracks(filtered)
    filtered = _merge_collinear_strokes(filtered)

    return filtered


def _extract_strokes(skeleton: np.ndarray) -> List[List[Tuple[int, int]]]:
    """Core stroke extraction with a conservative global trial and legacy fallback."""
    global _LAST_TRACE_DIAGNOSTICS

    graph = build_skeleton_graph(skeleton)
    skeleton_px = len(graph)
    ep_count = sum(1 for _, nb in graph.items() if len(nb) == 1)
    jn_count = sum(1 for _, nb in graph.items() if len(nb) >= 3)
    char_name = _TRACE_CONTEXT_CHAR
    expected_count = _expected_count_for_context(char_name)

    legacy = _extract_strokes_legacy(skeleton)
    try:
        global_strokes = _extract_strokes_global(skeleton, expected_count=expected_count)
        use_global, reason = _safe_global_decision(
            char_name, skeleton_px, legacy, global_strokes, expected_count
        )
    except Exception as exc:
        global_strokes = []
        use_global = False
        reason = f"global_exception:{type(exc).__name__}"

    selected = global_strokes if use_global else legacy
    prior_selected, prior_reason = _simple_count_prior(
        char_name, selected, legacy, global_strokes, expected_count
    )
    if prior_reason:
        selected = prior_selected
        if not use_global:
            reason = f"{reason};{prior_reason}"
    repaired_selected, repair_changed = _split_mid_winding_open_strokes(
        char_name, selected
    )
    if repair_changed:
        selected = repaired_selected
    selected_summary = _stroke_summary(selected)
    if use_global and prior_reason:
        method = "global+prior"
    elif prior_reason:
        method = "legacy+prior"
    else:
        method = "global" if use_global else "legacy"
    _LAST_TRACE_DIAGNOSTICS = {
        "char": char_name or "unknown",
        "method": method,
        "fallback_reason": None if use_global else reason,
        "expected_count": expected_count,
        "skeleton_px": skeleton_px,
        "endpoints": ep_count,
        "junction_px": jn_count,
        "legacy": _stroke_summary(legacy),
        "global": _stroke_summary(global_strokes),
        "selected": selected_summary,
    }
    return selected


def _extract_strokes_legacy(skeleton: np.ndarray) -> List[List[Tuple[int, int]]]:
    """（保留）旧贪心局部配对逻辑，用于对比测试。"""
    from stroke import build_skeleton_graph as _bsg
    graph = _bsg(skeleton)
    endpoints = [pt for pt, nb in graph.items() if len(nb) == 1]
    raw_junctions = [pt for pt, nb in graph.items() if len(nb) >= 3]

    if not endpoints:
        return []

    if not raw_junctions:
        return _pair_endpoints_directly(graph, endpoints)

    simp_edges, ep_set, ep_to_edge, comp_to_edges, new_comp_id, new_to_old_comps, junc_set, pt_to_comp = \
        _build_simplified_graph(skeleton)

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

            # 计算本交叉区的转角容许边长（超过此长度的边不参与转角配对）
            all_lens_at_junc = [len(simp_edges[ei2][2]) for ei2 in comp_to_edges[ci]]
            median_junc_len = np.median(all_lens_at_junc) if all_lens_at_junc else 300
            corner_max_len = median_junc_len * 1.2

            # 选方向连续性最高的边
            best_ei, best_score = None, -1.0
            candidate_scores = []
            for ei2, (a2, b2, path2) in candidates:
                score = _continuity_at_junction(
                    oriented, path2,
                    new_to_old_comps[ci],
                )
                # 转角配对长度门控：仅短边（< corner_max_len）允许转角 0.3
                if score == 0.3 and len(path2) > corner_max_len:
                    score = 0.0
                candidate_scores.append((ei2, score, len(path2)))
                if score > best_score:
                    best_score = score
                    best_ei = ei2

            if _DEBUG_JUNCTION_PAIRING and len(candidates) >= 2:
                inc_pts = np.array(oriented[-15:]).astype(float) if len(oriented) >= 15 else np.array(oriented).astype(float)
                in_dir = _pca_direction(inc_pts) if len(inc_pts) >= 2 else np.array([0.0, 0.0])
                print(f'  [J{ci}] step6 choose from {len(candidates)} candidates:')
                for ei2, sc, plen in candidate_scores:
                    _, _, p2 = simp_edges[ei2]
                    out_dir = _pca_direction(np.array(p2[:15]).astype(float)) if len(p2) >= 15 else np.array([0.0, 0.0])
                    mark = ' <-- BEST' if ei2 == best_ei else ''
                    print(f'    edge{ei2} len={plen:4d} score={sc:.3f} in_dir=({in_dir[0]:.2f},{in_dir[1]:.2f}) out_dir=({out_dir[0]:.2f},{out_dir[1]:.2f}){mark}')
                print(f'    threshold=0.2 best_score={best_score:.3f}')

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
        if _DEBUG_JUNCTION_PAIRING and len(edge_list) >= 2:
            print(f'  [J{ci}] step7 component: {len(edge_list)} remaining edges, {len(comp_pts)} junc px')
            for ei in edge_list:
                ea, eb, epath = simp_edges[ei]
                epts = np.array(epath).astype(float)
                edir = _pca_direction(epts) if len(epts) >= 2 else np.array([0.0, 0.0])
                e_se = np.linalg.norm(epts[-1] - epts[0]) if len(epts) >= 2 else 0
                a_in = ea in comp_pts
                b_in = eb in comp_pts
                print(f'    edge{ei} len={len(epath):4d} SE={e_se:5.0f} dir=({edir[0]:.2f},{edir[1]:.2f}) a_in_comp={a_in} b_in_comp={b_in}')
        # 计算本交叉区的转角容许边长
        all_lens_at_junc = [len(simp_edges[ei][2]) for ei in edge_list]
        median_junc_len = np.median(all_lens_at_junc) if all_lens_at_junc else 300
        corner_max_len = median_junc_len * 1.2

        while len(edge_list) >= 2:
            ei_a = edge_list.pop(0)
            best_ei, best_score = None, -1.0
            pair_scores = []
            for ei_b in edge_list:
                score = _simp_edge_pair_score(simp_edges[ei_a], simp_edges[ei_b], comp_pts)
                # 转角配对长度门控：两条边都必须足够短
                if score == 0.3:
                    _, _, pa = simp_edges[ei_a]
                    _, _, pb = simp_edges[ei_b]
                    if min(len(pa), len(pb)) > corner_max_len:
                        score = 0.0
                pair_scores.append((ei_b, score))
                if score > best_score:
                    best_score = score
                    best_ei = ei_b
            if _DEBUG_JUNCTION_PAIRING and pair_scores:
                cand_str = ', '.join(f'e{e}={s:.3f}' for e, s in pair_scores)
                print(f'    pair edge{ei_a}: candidates=[{cand_str}], best=e{best_ei} score={best_score:.3f}')
            if best_ei is not None and best_score > 0.2:
                edge_list.remove(best_ei)
                merged = _merge_edge_pair(simp_edges[ei_a], simp_edges[ei_b], comp_pts)
                # 合并后回绕率检查：拒绝过度绕路的转角合并
                mpts = np.array(merged).astype(float)
                mse = np.linalg.norm(mpts[-1] - mpts[0])
                mpath = np.sum(np.linalg.norm(np.diff(mpts, axis=0), axis=1))
                mwinding = mpath / mse if mse > 1 else 999.0
                if mwinding > 4.0:
                    # 合并后回绕太严重，撤销合并
                    if _DEBUG_JUNCTION_PAIRING:
                        print(f'    REJECT merge e{ei_a}+e{best_ei}: winding={mwinding:.1f} > 4.0')
                    _, _, path_a = simp_edges[ei_a]
                    strokes.append(_orient_path(path_a, endpoints, junc_set))
                    paired_in_second.add(ei_a)
                    edge_list.insert(0, best_ei)  # 放回候选池
                else:
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

    # 过滤端部短毛刺笔画（必须在分割/回溯处理前，用原始笔数计算相对长度）
    filtered = _filter_endpoint_spurs(filtered)

    # 清理极高绕路的微碎片（仅删、不裁切）
    filtered = _despike_zigzag(filtered)

    # 切分长距离回绕笔画（例如同一枝干下去又沿近邻回到起点附近）
    filtered = _split_extreme_winding_strokes(filtered)

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
    # cos≈1: 直通, cos≈0: 转角(口/田等闭合结构), cos≈-1: 折返(应拒绝)
    if cos < -0.7:
        return 0.0
    if cos > 0.5:
        return cos
    return 0.3  # 转角固定得分，高于 0.2 阈值但低于直通


def _simp_edge_pair_score(
    edge_a: Tuple, edge_b: Tuple,
    junc_pts: Set[Tuple[int, int]],
) -> float:
    """两条简化边在交叉区处的方向连续性得分。

    支持直通（共线笔直穿过）和转角（闭合结构如口/田的 90° 拐角）。
    拒绝折返（同方向回头）。
    """
    a_node_a, a_node_b, path_a = edge_a
    b_node_a, b_node_b, path_b = edge_b

    # 确定每条边在交叉区的一端：若两端都在交叉区内，取离另一交叉区更远的一端
    a_both_in = a_node_a in junc_pts and a_node_b in junc_pts
    b_both_in = b_node_a in junc_pts and b_node_b in junc_pts

    skip_margin = 6
    k = 15
    min_len = min(len(path_a), len(path_b))
    if k + skip_margin >= min_len:
        k = max(3, min_len // 2)
        skip_margin = min(2, k // 3)
    if k < 2:
        return 0.0

    # 边 a：确定取哪端方向（取不在交叉区那端，或两端都在时取主导方向）
    if a_both_in:
        # 两端都在交叉区——用整条边的 PCA 方向
        pts_a = np.array(path_a).astype(float)
    elif a_node_a in junc_pts:
        start_a, end_a = skip_margin, min(len(path_a), skip_margin + k)
        if end_a - start_a < 2:
            start_a, end_a = 0, min(len(path_a), k)
        pts_a = np.array(path_a[start_a:end_a]).astype(float)
    else:
        end_a = len(path_a) - skip_margin
        start_a = max(0, end_a - k)
        if end_a - start_a < 2:
            start_a, end_a = max(0, len(path_a) - k), len(path_a)
        pts_a = np.array(path_a[start_a:end_a]).astype(float)

    # 边 b：同上
    if b_both_in:
        pts_b = np.array(path_b).astype(float)
    elif b_node_a in junc_pts:
        start_b, end_b = skip_margin, min(len(path_b), skip_margin + k)
        if end_b - start_b < 2:
            start_b, end_b = 0, min(len(path_b), k)
        pts_b = np.array(path_b[start_b:end_b]).astype(float)
    else:
        end_b = len(path_b) - skip_margin
        start_b = max(0, end_b - k)
        if end_b - start_b < 2:
            start_b, end_b = max(0, len(path_b) - k), len(path_b)
        pts_b = np.array(path_b[start_b:end_b]).astype(float)

    dir_a = _pca_direction(pts_a)
    dir_b = _pca_direction(pts_b)

    na, nb = np.linalg.norm(dir_a), np.linalg.norm(dir_b)
    if na < 1e-6 or nb < 1e-6:
        return 0.0

    # cos: 1=直通(相反方向汇合), 0=转角(垂直), -1=折返(同方向)
    cos = np.dot(dir_a / na, -dir_b / nb)
    if cos < -0.7:
        return 0.0
    if cos > 0.5:
        return cos
    return 0.3  # 转角固定得分


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


def _filter_endpoint_spurs(
    strokes: List[List[Tuple[int, int]]],
    junction_radius: float = 15.0,
    max_se_ratio: float = 0.20,
) -> List[List[Tuple[int, int]]]:
    """过滤端部短毛刺笔画：非常保守，仅删除极短的孤立端部分支。

    同时满足以下全部条件才过滤：
    - SE < 中位数的 max_se_ratio（相对短，默认 20%）
    - 一端接其他笔（交叉区），另一端孤立（距所有其他笔点 > junction_radius）
    不做段切分、不依赖笔画方向——避免误伤复杂字的合法短笔和闭合结构。
    """
    if len(strokes) <= 1:
        return strokes

    n = len(strokes)
    ends_info = []
    lengths = []
    for s in strokes:
        pts = np.array(s).astype(float)
        se = np.linalg.norm(pts[-1] - pts[0])
        lengths.append(se)
        ends_info.append((np.array(s[0]).astype(float), np.array(s[-1]).astype(float)))

    median_len = np.median(lengths) if lengths else 0
    if median_len < 1:
        return strokes

    # 连通性判断：距任何其他笔的任一点 < junction_radius 即为「接」
    def endpoint_connectivity(ep_idx: int, ep_which: int) -> bool:
        ep = ends_info[ep_idx][ep_which]
        for j, s in enumerate(strokes):
            if j == ep_idx:
                continue
            sj_pts = np.array(s).astype(float)
            # 始终检查首尾端点（交叉区/接合处）
            for ej in [0, -1]:
                if np.linalg.norm(ep - sj_pts[ej]) < junction_radius:
                    return True
            # 对内部点均匀采样（步长保证不遗漏 junction_radius 宽的交叉区）
            step = max(1, int(junction_radius * 1.2))
            for k in range(0, len(sj_pts), step):
                if np.linalg.norm(ep - sj_pts[k]) < junction_radius:
                    return True
        return False

    keep = []
    for i, s in enumerate(strokes):
        length_i = lengths[i]

        # 相对长度门槛：SE >= 中位数 20% → 保留
        if length_i >= median_len * max_se_ratio:
            keep.append(s)
            continue

        # 非常短的笔画：检查端点连通性
        ep0_conn = endpoint_connectivity(i, 0)
        ep1_conn = endpoint_connectivity(i, 1)

        if ep0_conn and ep1_conn:
            # 两端都接 → 合法短桥（如口的一边）
            keep.append(s)
        elif not ep0_conn and not ep1_conn:
            # 两端都孤立 → 保留
            keep.append(s)
        else:
            # 一端接、一端孤立 → 端部毛刺，过滤
            pass

    return keep


def _despike_zigzag(
    strokes: List[List[Tuple[int, int]]],
    remove_winding: float = 8.0,
    remove_se_ratio: float = 0.04,
) -> List[List[Tuple[int, int]]]:
    """清理极高绕路的微碎片（仅删、不裁切、不修改笔画路径）。

    只移除满足全部条件的极短锯齿碎片：
    - winding > remove_winding (极高绕路)
    - SE < 中位数的 remove_se_ratio (净位移极小)
    不做段切分、不做方向修正、不做降采样——避免误伤复杂字的弯笔画。
    """
    if not strokes:
        return strokes

    se_list = []
    for stk in strokes:
        if len(stk) >= 2:
            pts = np.array(stk).astype(float)
            se_list.append(np.linalg.norm(pts[-1] - pts[0]))
    median_se = np.median(se_list) if se_list else 100
    remove_se_threshold = max(15, median_se * remove_se_ratio)

    result = []
    for stk in strokes:
        if len(stk) < 8:
            result.append(stk)
            continue

        pts = np.array(stk).astype(float)
        se = np.linalg.norm(pts[-1] - pts[0])
        path = np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1))
        winding = path / se if se > 1 else 0

        # 唯一删除条件：极高绕路 + 极短净位移 → 微小锯齿环碎片
        if winding > remove_winding and se < remove_se_threshold:
            continue

        result.append(stk)

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
