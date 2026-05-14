"""Wu ICIRA 2024 skeleton extraction: contour midpoint skeleton + V/S/C
classification + dynamic crossing region traversal.

Reference: Wu et al., "Application of Stroke Extraction and Trajectory
Planning in Robotic Calligraphy", ICIRA 2024, LNAI 15202, pp. 308-320.

Three layers:
  Layer 1 — contour midpoint skeleton (geometric medial axis)
  Layer 2 — V/S/C point classification using Nc (neighbor-component count)
  Layer 3 — stroke assembly (delegates to stroke.py for robust assembly;
             V/S/C classification available for junction-aware refinement)
"""

import cv2
import numpy as np
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
from skimage.morphology import skeletonize as _skel_medial
from stroke import compute_nc


# ═══════════════════════════════════════════════════════════════
# Layer 1: Contour → Midpoint Skeleton
# ═══════════════════════════════════════════════════════════════

def wu2024_skeletonize(binary: np.ndarray) -> np.ndarray:
    """Contour-based midpoint skeleton (Wu ICIRA 2024).

    Computes midpoints as p + d(p) * n_inward for each contour point.
    Keeps pixels hit by >= 2 midpoints (consensus medial axis), then
    uses morphological closing to connect gaps into a clean skeleton.

    Unlike morphological thinning, this is based on contour geometry
    rather than iterative pixel removal.

    Args:
        binary: (H, W) uint8, 0/255, foreground=255
    Returns:
        (H, W) uint8 skeleton, 0/255
    """
    H, W = binary.shape
    fg = (binary > 0).astype(np.uint8)

    dist = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    fg_mask = fg > 0
    dt_median = np.median(dist[fg_mask]) if fg_mask.any() else 0.0
    d_min = max(0.6, min(1.5, dt_median * 0.4))

    grad_y, grad_x = np.gradient(dist)
    contours, _ = cv2.findContours(fg, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    skel_accum = np.zeros((H, W), dtype=np.uint16)

    for contour in contours:
        pts = contour.squeeze(1)
        if pts.ndim != 2 or len(pts) < 5:
            continue
        _midpoint_accumulate(pts, dist, grad_y, grad_x, skel_accum, d_min)

    # Threshold: keep only high-consensus midpoints (adaptive percentile)
    skeleton_map = np.zeros((H, W), dtype=np.uint8)
    valid = skel_accum[skel_accum > 0]
    if len(valid) == 0:
        return skeleton_map
    # 取 90 分位数以上的高共识点作为骨架核心
    pct_val = np.percentile(valid, 90)
    threshold = max(2, int(pct_val * 0.6))
    skeleton_map[skel_accum >= threshold] = 255
    if np.count_nonzero(skeleton_map) < 10:
        # 退路：极细笔画
        skeleton_map[skel_accum >= 2] = 255

    if np.count_nonzero(skeleton_map) < 10:
        from skimage.morphology import thin
        skeleton_map = (_skel_medial(fg > 0).astype(np.uint8)) * 255
        return skeleton_map

    # Morphological closing to connect nearby midpoints into continuous lines
    ksize = max(2, min(7, int(dt_median * 0.15)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
    closed = cv2.morphologyEx(skeleton_map, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Thin to 1-pixel width (increased iterations for thick strokes)
    from skimage.morphology import thin
    skeleton_map = (_skel_medial(closed > 0).astype(np.uint8)) * 255

    return skeleton_map


def _midpoint_accumulate(
    contour: np.ndarray,
    dist: np.ndarray,
    grad_y: np.ndarray,
    grad_x: np.ndarray,
    skel_accum: np.ndarray,
    d_min: float = 1.0,
    window: int = 5,
) -> None:
    """Accumulate midpoints from a single contour into skel_accum.

    Each midpoint pixel gets +1. Consensus areas where multiple contour
    points agree on the medial axis get higher accumulator values.
    """
    H, W = dist.shape
    n = len(contour)

    for i in range(n):
        y, x = int(round(contour[i, 1])), int(round(contour[i, 0]))
        if not (0 <= y < H and 0 <= x < W):
            continue

        d = dist[y, x]
        if d < d_min:
            continue

        lo, hi = max(0, i - window), min(n, i + window + 1)
        seg = contour[lo:hi].astype(np.float32)
        seg_yx = seg[:, ::-1]

        tangent = _pca_direction_vec(seg_yx)
        if np.linalg.norm(tangent) < 1e-6:
            continue

        normal = np.array([tangent[1], -tangent[0]], dtype=np.float64)
        g_vec = np.array([grad_y[y, x], grad_x[y, x]], dtype=np.float64)
        if np.dot(normal, g_vec) > 0:
            normal = -normal

        my = y + d * normal[0]
        mx = x + d * normal[1]

        miy, mix = int(round(my)), int(round(mx))
        if 0 <= miy < H and 0 <= mix < W:
            skel_accum[miy, mix] += 1


# ═══════════════════════════════════════════════════════════════
# Layer 2: V/S/C Classification (using Nc)
# ═══════════════════════════════════════════════════════════════

def classify_skeleton_points(
    skeleton: np.ndarray,
) -> Dict:
    """Classify every skeleton pixel as V(vertex)/S(intersection)/C(connection).

    Uses Nc — number of 8-connected components among neighbors — to avoid
    misclassifying chain points near intersections as S.

    Returns dict:
        'V': list of (y, x)        — endpoints (Nc=1)
        'S': list of (y, x)        — intersections (Nc>=3)
        'C': list of (y, x)        — chain points (Nc=2)
        'map': (H, W) int8 array   — 0=C, 1=V, 2=S
        'graph': {(y,x): [(ny,nx)]} — 8-connected adjacency
    """
    H, W = skeleton.shape
    binary = skeleton > 0
    ys, xs = np.where(binary)
    pts_set = set(zip(ys.tolist(), xs.tolist()))

    graph = {}
    for y, x in pts_set:
        nb = []
        for ny, nx in _eight_neighbors(y, x):
            if (ny, nx) in pts_set:
                nb.append((ny, nx))
        graph[(y, x)] = nb

    V_list, S_list, C_list = [], [], []
    label_map = np.zeros((H, W), dtype=np.int8)

    for pt, neighbors in graph.items():
        nc = compute_nc(graph, pt)
        if nc == 1:
            V_list.append(pt)
            label_map[pt[0], pt[1]] = 1
        elif nc >= 3:
            S_list.append(pt)
            label_map[pt[0], pt[1]] = 2
        else:
            C_list.append(pt)

    return {
        'V': V_list,
        'S': S_list,
        'C': C_list,
        'map': label_map,
        'graph': graph,
    }



# ═══════════════════════════════════════════════════════════════
# Layer 3: Stroke Assembly
# ═══════════════════════════════════════════════════════════════

def trace_wu2024(skeleton: np.ndarray) -> np.ndarray:
    """Skeleton → (N, 2) ordered trajectory. Uses stroke.py assembly."""
    if np.sum(skeleton > 0) == 0:
        return np.empty((0, 2))
    strokes = get_wu2024_stroke_list(skeleton)
    if not strokes:
        return np.empty((0, 2))
    all_pts = []
    for s in strokes:
        all_pts.extend(s)
    return np.array(all_pts)


def get_wu2024_stroke_list(skeleton: np.ndarray,
                          min_branch_len: int = 30,
                          min_stroke_len: int = 60) -> List[np.ndarray]:
    """Skeleton → per-stroke arrays.

    Prunes short spurs then uses stroke.py's robust assembly pipeline.
    The wu2024 V/S/C classification is available for junction analysis
    via wu2024_classify_and_show().
    """
    from stroke import _extract_strokes as stroke_extract
    from stroke import order_strokes, set_stroke_direction
    from stroke import _merge_collinear_strokes, prune_skeleton

    if np.sum(skeleton > 0) == 0:
        return []

    # 自适应剪枝（调用方应传入基于笔画宽度的阈值）
    skeleton = prune_skeleton(skeleton, min_branch_len=min_branch_len)

    strokes_raw = stroke_extract(skeleton)
    if not strokes_raw:
        return []

    strokes_raw = [s for s in strokes_raw if len(s) >= min_stroke_len]
    strokes_raw = _merge_collinear_strokes(strokes_raw)
    strokes_raw = order_strokes(strokes_raw)
    strokes_raw = [set_stroke_direction(s) for s in strokes_raw]

    return [np.array(s) for s in strokes_raw]


def wu2024_classify_and_show(skeleton: np.ndarray) -> Dict:
    """Run V/S/C classification and return stats for analysis.

    Use this to inspect junction quality of any skeleton.
    Returns: {'V': count, 'S': count, 'C': count, 'cls': full dict}
    """
    cls = classify_skeleton_points(skeleton)
    return {
        'V': len(cls['V']),
        'S': len(cls['S']),
        'C': len(cls['C']),
        'cls': cls,
    }


# ═══════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════

def _eight_neighbors(y: int, x: int):
    return [
        (y - 1, x), (y - 1, x + 1), (y, x + 1), (y + 1, x + 1),
        (y + 1, x), (y + 1, x - 1), (y, x - 1), (y - 1, x - 1),
    ]


def _pca_direction_vec(pts: np.ndarray) -> np.ndarray:
    """Unit PCA direction vector."""
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
