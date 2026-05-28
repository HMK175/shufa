"""Extract branch-free primitive skeleton segments for offline diagnostics."""

import argparse
import csv
import math
import sys
from collections import deque
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline import BLUR_KSIZE
from skeleton import clean_junction_spurs, skeletonize, straighten_junctions
from stroke import build_skeleton_graph, prune_skeleton
from utils import estimate_stroke_width, load_image, preprocess


Point = Tuple[int, int]


def _cluster_points(points: Set[Point], graph: Dict[Point, List[Point]]) -> List[Set[Point]]:
    remaining = set(points)
    clusters = []
    while remaining:
        start = remaining.pop()
        comp = {start}
        queue = deque([start])
        while queue:
            cur = queue.popleft()
            for nb in graph.get(cur, []):
                if nb in remaining:
                    remaining.remove(nb)
                    comp.add(nb)
                    queue.append(nb)
        clusters.append(comp)
    return clusters


def _path_stats(points: List[Point]) -> dict:
    pts = np.array(points, dtype=float)
    y0, x0 = pts.min(axis=0)
    y1, x1 = pts.max(axis=0)
    if len(pts) < 2:
        path_len = endpoint = winding = 0.0
    else:
        path_len = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
        endpoint = float(np.linalg.norm(pts[-1] - pts[0]))
        winding = path_len / endpoint if endpoint > 1 else 999.0
    return {
        "bbox": f"{y0:.1f};{x0:.1f};{y1:.1f};{x1:.1f}",
        "path_length": path_len,
        "endpoint_distance": endpoint,
        "winding": winding,
    }


def _angle(points: List[Point], from_start: bool = True, window: int = 8) -> float:
    if len(points) < 2:
        return 0.0
    if from_start:
        a = np.array(points[0], dtype=float)
        b = np.array(points[min(window, len(points) - 1)], dtype=float)
    else:
        a = np.array(points[-1], dtype=float)
        b = np.array(points[max(0, len(points) - 1 - window)], dtype=float)
    dy, dx = b - a
    return math.degrees(math.atan2(dy, dx))


def _render_segment(points: List[Point], out_path: Path, image_size: int = 128) -> None:
    pts = np.array(points, dtype=float)
    canvas = np.full((image_size, image_size), 255, dtype=np.uint8)
    if len(pts) == 0:
        cv2.imwrite(str(out_path), canvas)
        return
    y0, x0 = pts.min(axis=0)
    y1, x1 = pts.max(axis=0)
    span = max(float(y1 - y0), float(x1 - x0), 1.0)
    pad = image_size * 0.16
    scale = (image_size - 2 * pad) / span
    cy = (y0 + y1) / 2.0
    cx = (x0 + x1) / 2.0
    mapped = []
    for y, x in pts:
        xx = int(round((x - cx) * scale + image_size / 2.0))
        yy = int(round((y - cy) * scale + image_size / 2.0))
        mapped.append((xx, yy))
    ink = np.zeros_like(canvas)
    for p0, p1 in zip(mapped[:-1], mapped[1:]):
        cv2.line(ink, p0, p1, 255, thickness=4, lineType=cv2.LINE_AA)
    if len(mapped) == 1:
        cv2.circle(ink, mapped[0], 3, 255, -1)
    canvas[ink > 0] = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), canvas)


def _prepare_skeleton(image_path: Path):
    image = load_image(str(image_path))
    binary = preprocess(image, blur_ksize=BLUR_KSIZE)
    half_width = estimate_stroke_width(binary)
    skel = skeletonize(binary)
    skel = prune_skeleton(skel, min_branch_len=max(30, int(half_width * 1.8)))
    skel = straighten_junctions(skel)
    skel = clean_junction_spurs(skel)
    return image, binary, skel


def extract_primitives(image_path: Path, output_dir: Path) -> Path:
    char_id = image_path.stem
    out_dir = output_dir / char_id
    out_dir.mkdir(parents=True, exist_ok=True)
    image, binary, skel = _prepare_skeleton(image_path)
    graph = build_skeleton_graph(skel)
    endpoints = {pt for pt, nb in graph.items() if len(nb) == 1}
    junction_pixels = {pt for pt, nb in graph.items() if len(nb) >= 3}
    clusters = _cluster_points(junction_pixels, graph)
    cluster_by_point = {}
    for idx, cluster in enumerate(clusters):
        for pt in cluster:
            cluster_by_point[pt] = idx

    node_points = set(endpoints) | set(junction_pixels)

    def node_id(pt: Point) -> str:
        if pt in endpoints:
            return f"e:{pt[0]}:{pt[1]}"
        if pt in cluster_by_point:
            return f"j:{cluster_by_point[pt]}"
        return f"p:{pt[0]}:{pt[1]}"

    def node_type(pt: Point) -> str:
        return "endpoint" if pt in endpoints else "junction"

    segments = []
    seen_edges = set()
    for start in sorted(node_points):
        for nb in graph.get(start, []):
            edge_key = tuple(sorted([start, nb]))
            if edge_key in seen_edges:
                continue
            path = [start]
            prev = start
            cur = nb
            seen_edges.add(edge_key)
            local_seen = {start}
            while True:
                path.append(cur)
                if cur in node_points and cur != start:
                    break
                if cur in local_seen:
                    break
                local_seen.add(cur)
                nexts = [p for p in graph.get(cur, []) if p != prev]
                if not nexts:
                    break
                nxt = nexts[0]
                seen_edges.add(tuple(sorted([cur, nxt])))
                prev, cur = cur, nxt
            if len(path) >= 2:
                segments.append(path)

    # Remaining unvisited degree-2 loops, rare but useful to record explicitly.
    visited_edges = set()
    for path in segments:
        for a, b in zip(path[:-1], path[1:]):
            visited_edges.add(tuple(sorted([a, b])))
    for pt in sorted(graph):
        for nb in graph[pt]:
            edge_key = tuple(sorted([pt, nb]))
            if edge_key in visited_edges:
                continue
            path = [pt]
            prev = pt
            cur = nb
            while True:
                path.append(cur)
                visited_edges.add(tuple(sorted([prev, cur])))
                nexts = [p for p in graph.get(cur, []) if p != prev]
                if not nexts:
                    break
                nxt = nexts[0]
                if nxt == path[0]:
                    path.append(nxt)
                    visited_edges.add(tuple(sorted([cur, nxt])))
                    break
                if tuple(sorted([cur, nxt])) in visited_edges:
                    break
                prev, cur = cur, nxt
            if len(path) >= 3:
                segments.append(path)

    rows = []
    for idx, points in enumerate(segments, start=1):
        segment_id = f"segment_{idx:03d}"
        img_name = f"{segment_id}.png"
        _render_segment(points, out_dir / img_name)
        stats = _path_stats(points)
        start = points[0]
        end = points[-1]
        is_loop = start == end
        rows.append(
            {
                "segment_id": segment_id,
                "point_count": len(points),
                "start_type": "loop" if is_loop else node_type(start),
                "end_type": "loop" if is_loop else node_type(end),
                "bbox": stats["bbox"],
                "path_length": f"{stats['path_length']:.3f}",
                "endpoint_distance": f"{stats['endpoint_distance']:.3f}",
                "winding": f"{stats['winding']:.3f}",
                "angle_start": f"{_angle(points, True):.2f}",
                "angle_end": f"{_angle(points, False):.2f}",
            }
        )

    csv_path = out_dir / "segments.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "segment_id",
            "point_count",
            "start_type",
            "end_type",
            "bbox",
            "path_length",
            "endpoint_distance",
            "winding",
            "angle_start",
            "angle_end",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    overlay_path = out_dir / "primitives_overlay.png"
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(skel, cmap="gray", alpha=0.35)
    colors = plt.cm.tab20(np.linspace(0, 1, max(len(segments), 1)))
    for idx, points in enumerate(segments):
        pts = np.array(points, dtype=float)
        ax.plot(pts[:, 1], pts[:, 0], color=colors[idx % len(colors)], linewidth=1.4)
        mid = pts[len(pts) // 2]
        ax.text(mid[1], mid[0], str(idx + 1), color="yellow", fontsize=7, ha="center")
    if endpoints:
        ey, ex = zip(*endpoints)
        ax.scatter(ex, ey, c="lime", s=24, label="endpoint")
    for ci, cluster in enumerate(clusters):
        if not cluster:
            continue
        cy, cx = zip(*cluster)
        ax.scatter(cx, cy, s=20, label=f"J{ci}")
    ax.set_title(f"{char_id}: primitives={len(segments)}, endpoints={len(endpoints)}, junction_clusters={len(clusters)}")
    ax.invert_yaxis()
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(overlay_path, dpi=160)
    plt.close(fig)

    print(
        f"{char_id}: segments={len(segments)}, endpoints={len(endpoints)}, "
        f"junction_pixels={len(junction_pixels)}, junction_clusters={len(clusters)}"
    )
    print(f"wrote {csv_path}")
    print(f"wrote {overlay_path}")
    return csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract primitive skeleton segments")
    parser.add_argument("image")
    parser.add_argument("--output-dir", default=str(SCRIPT_DIR / "output" / "primitives"))
    args = parser.parse_args()
    extract_primitives(Path(args.image).resolve(), Path(args.output_dir).resolve())


if __name__ == "__main__":
    main()
