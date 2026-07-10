"""Graph segment extraction for cleaned skeletons."""

from __future__ import annotations

import math
from collections import deque
from typing import Iterable

import numpy as np


PSEUDO_BRANCH_SHORT_ARM_MAX = 6
PSEUDO_BRANCH_MIN_MAIN_ARM = 4
PSEUDO_BRANCH_MAIN_ARM_OPPOSITE_COS = -0.75
PSEUDO_BRANCH_HOOK_ENDPOINT_EXTRA = 2


def _neighbors(shape: tuple[int, int], y: int, x: int) -> Iterable[tuple[int, int]]:
    height, width = shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width:
                yield ny, nx


def _connected_neighbors(skeleton: np.ndarray, point: tuple[int, int]) -> list[tuple[int, int]]:
    y, x = point
    connected: list[tuple[int, int]] = []
    for ny, nx in _neighbors(skeleton.shape, y, x):
        if not skeleton[ny, nx]:
            continue
        if abs(ny - y) == 1 and abs(nx - x) == 1:
            if skeleton[y, nx] or skeleton[ny, x]:
                continue
        connected.append((ny, nx))
    return connected


def _degree(skeleton: np.ndarray, point: tuple[int, int]) -> int:
    return len(_connected_neighbors(skeleton, point))


def _components(skeleton: np.ndarray) -> list[set[tuple[int, int]]]:
    seen = np.zeros(skeleton.shape, dtype=bool)
    components: list[set[tuple[int, int]]] = []
    for y, x in zip(*np.nonzero(skeleton)):
        start = (int(y), int(x))
        if seen[start]:
            continue
        queue: deque[tuple[int, int]] = deque([start])
        seen[start] = True
        component: set[tuple[int, int]] = set()
        while queue:
            point = queue.popleft()
            component.add(point)
            for neighbor in _connected_neighbors(skeleton, point):
                if not seen[neighbor]:
                    seen[neighbor] = True
                    queue.append(neighbor)
        components.append(component)
    components.sort(key=lambda comp: (min(y for y, _ in comp), min(x for _, x in comp)))
    return components


def _cluster_points(
    points: set[tuple[int, int]],
    skeleton: np.ndarray,
) -> list[set[tuple[int, int]]]:
    remaining = set(points)
    clusters: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        cluster = {start}
        queue: deque[tuple[int, int]] = deque([start])
        while queue:
            point = queue.popleft()
            for neighbor in _neighbors(skeleton.shape, *point):
                if not skeleton[neighbor]:
                    continue
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    cluster.add(neighbor)
                    queue.append(neighbor)
        clusters.append(cluster)
    clusters.sort(key=lambda cluster: (min(y for y, _ in cluster), min(x for _, x in cluster)))
    return clusters


def _expand_branch_clusters(
    skeleton: np.ndarray,
    clusters: list[set[tuple[int, int]]],
    endpoints: set[tuple[int, int]],
) -> list[set[tuple[int, int]]]:
    expanded_clusters: list[set[tuple[int, int]]] = []
    for cluster in clusters:
        expanded = set(cluster)
        changed = True
        while changed:
            changed = False
            candidates: set[tuple[int, int]] = set()
            for point in expanded:
                for neighbor in _neighbors(skeleton.shape, *point):
                    if skeleton[neighbor] and neighbor not in expanded and neighbor not in endpoints:
                        candidates.add(neighbor)
            for candidate in sorted(candidates):
                touching = sum(1 for neighbor in _neighbors(skeleton.shape, *candidate) if neighbor in expanded)
                if touching >= 2:
                    expanded.add(candidate)
                    changed = True
        expanded_clusters.append(expanded)
    return expanded_clusters


def _edge_key(
    start: tuple[int, int],
    end: tuple[int, int],
) -> tuple[tuple[int, int], tuple[int, int]]:
    return tuple(sorted((start, end)))  # type: ignore[return-value]


def _polyline_length(points: list[tuple[int, int]]) -> float:
    total = 0.0
    for (y0, x0), (y1, x1) in zip(points[:-1], points[1:]):
        total += math.hypot(float(y1 - y0), float(x1 - x0))
    return total


def _direction_cosine(
    origin: tuple[int, int],
    first_step_a: tuple[int, int],
    first_step_b: tuple[int, int],
) -> float:
    ay, ax = first_step_a[0] - origin[0], first_step_a[1] - origin[1]
    by, bx = first_step_b[0] - origin[0], first_step_b[1] - origin[1]
    denom = math.hypot(float(ay), float(ax)) * math.hypot(float(by), float(bx))
    if denom == 0.0:
        return 1.0
    return float((ay * by + ax * bx) / denom)


def _trace_arm(
    skeleton: np.ndarray,
    origin: tuple[int, int],
    first_step: tuple[int, int],
) -> dict[str, object]:
    path = [origin, first_step]
    prev = origin
    current = first_step
    guard = int(skeleton.sum()) + 1

    while guard > 0:
        guard -= 1
        degree = _degree(skeleton, current)
        if current != origin and degree == 1:
            return {
                "path": path,
                "length": len(path) - 1,
                "terminal_kind": "endpoint",
                "terminal_point": current,
                "first_step": first_step,
            }
        if current != origin and degree >= 3:
            return {
                "path": path,
                "length": len(path) - 1,
                "terminal_kind": "branch",
                "terminal_point": current,
                "first_step": first_step,
            }
        next_points = [point for point in _connected_neighbors(skeleton, current) if point != prev]
        if not next_points:
            return {
                "path": path,
                "length": len(path) - 1,
                "terminal_kind": "dead_end",
                "terminal_point": current,
                "first_step": first_step,
            }
        if len(next_points) != 1:
            return {
                "path": path,
                "length": len(path) - 1,
                "terminal_kind": "junction",
                "terminal_point": current,
                "first_step": first_step,
            }
        prev, current = current, next_points[0]
        path.append(current)

    return {
        "path": path,
        "length": len(path) - 1,
        "terminal_kind": "guard",
        "terminal_point": current,
        "first_step": first_step,
    }


def _split_pseudo_branch_clusters(
    skeleton: np.ndarray,
    clusters: list[set[tuple[int, int]]],
) -> tuple[list[set[tuple[int, int]]], dict[tuple[int, int], tuple[int, int]]]:
    real_clusters: list[set[tuple[int, int]]] = []
    passthrough_short_neighbor_by_point: dict[tuple[int, int], tuple[int, int]] = {}

    for cluster in clusters:
        if len(cluster) != 1:
            real_clusters.append(cluster)
            continue
        point = next(iter(cluster))
        exits = _connected_neighbors(skeleton, point)
        if len(exits) != 3:
            real_clusters.append(cluster)
            continue
        arms = [_trace_arm(skeleton, point, neighbor) for neighbor in exits]
        arms_by_length = sorted(arms, key=lambda arm: int(arm["length"]))
        short_arm = arms_by_length[0]
        remaining_arms = arms_by_length[1:]
        short_length = int(short_arm["length"])
        main_arm_cosine = _direction_cosine(
            point,
            remaining_arms[0]["first_step"],  # type: ignore[arg-type]
            remaining_arms[1]["first_step"],  # type: ignore[arg-type]
        )
        branch_arms = [
            arm
            for arm in remaining_arms
            if arm["terminal_kind"] == "branch" and int(arm["length"]) >= PSEUDO_BRANCH_MIN_MAIN_ARM
        ]
        endpoint_arms = [
            arm
            for arm in remaining_arms
            if arm["terminal_kind"] == "endpoint"
            and int(arm["length"]) >= max(PSEUDO_BRANCH_MIN_MAIN_ARM, short_length + PSEUDO_BRANCH_HOOK_ENDPOINT_EXTRA)
        ]
        # Some box-like corners acquire a one-pixel side stub during thinning.
        # We treat those as pass-through bends only when the stub is uniquely
        # short and the other two arms form a real corner, not a T-junction.
        if (
            short_arm["terminal_kind"] == "endpoint"
            and short_length <= PSEUDO_BRANCH_SHORT_ARM_MAX
            and len(remaining_arms) == 2
            and int(remaining_arms[0]["length"]) > short_length
            and int(remaining_arms[0]["length"]) >= short_length * 2
            and all(int(arm["length"]) >= PSEUDO_BRANCH_MIN_MAIN_ARM for arm in remaining_arms)
            and all(arm["terminal_kind"] in {"endpoint", "branch"} for arm in remaining_arms)
            and main_arm_cosine > PSEUDO_BRANCH_MAIN_ARM_OPPOSITE_COS
        ):
            passthrough_short_neighbor_by_point[point] = short_arm["first_step"]  # type: ignore[assignment]
            continue
        # Some hook-like joints get skeletonized as a long continuation plus a
        # tiny local spur. In that case we still treat the short endpoint arm
        # as a pseudo-branch even if the two main arms start in near-opposite
        # directions.
        if (
            short_arm["terminal_kind"] == "endpoint"
            and short_length <= PSEUDO_BRANCH_SHORT_ARM_MAX
            and len(branch_arms) == 1
            and len(endpoint_arms) == 1
        ):
            passthrough_short_neighbor_by_point[point] = short_arm["first_step"]  # type: ignore[assignment]
            continue
        real_clusters.append(cluster)

    return real_clusters, passthrough_short_neighbor_by_point


def _trace_segment(
    skeleton: np.ndarray,
    terminal_lookup: dict[tuple[int, int], str],
    start: tuple[int, int],
    first_step: tuple[int, int],
    passthrough_short_neighbor_by_point: dict[tuple[int, int], tuple[int, int]] | None = None,
) -> list[tuple[int, int]]:
    path = [start, first_step]
    prev = start
    current = first_step
    guard = int(skeleton.sum()) + 1

    while current not in terminal_lookup and guard > 0:
        guard -= 1
        next_points = [
            point
            for point in _connected_neighbors(skeleton, current)
            if point != prev
        ]
        if len(next_points) != 1:
            passthrough_next = None
            if passthrough_short_neighbor_by_point is not None and len(next_points) == 2:
                short_neighbor = passthrough_short_neighbor_by_point.get(current)
                if short_neighbor is not None and short_neighbor in next_points:
                    passthrough_candidates = [point for point in next_points if point != short_neighbor]
                    if len(passthrough_candidates) == 1:
                        passthrough_next = passthrough_candidates[0]
            if passthrough_next is None:
                break
            prev, current = current, passthrough_next
            path.append(current)
            continue
        prev, current = current, next_points[0]
        path.append(current)
    return path


def _trace_component_loop(
    skeleton: np.ndarray,
    component: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    start = min(component)
    neighbors = sorted(_connected_neighbors(skeleton, start))
    if not neighbors:
        return [start]

    path = [start, neighbors[0]]
    prev = start
    current = neighbors[0]
    guard = len(component) + 2

    while guard > 0:
        guard -= 1
        next_points = [point for point in _connected_neighbors(skeleton, current) if point != prev]
        if not next_points:
            break
        next_point = next_points[0]
        path.append(next_point)
        if next_point == start:
            break
        prev, current = current, next_point
    return path


def extract_segments(skeleton: np.ndarray, min_segment_pixels: int = 4) -> dict:
    skel = np.asarray(skeleton, dtype=bool)
    if skel.ndim != 2:
        raise ValueError("skeleton must be a 2D array")

    pixels = {(int(y), int(x)) for y, x in zip(*np.nonzero(skel))}
    if not pixels:
        return {
            "segments": [],
            "segment_count": 0,
            "endpoint_count": 0,
            "branch_point_count": 0,
            "component_count": 0,
            "components": [],
        }

    degrees = {point: _degree(skel, point) for point in pixels}
    endpoints = {point for point, degree in degrees.items() if degree == 1}
    branch_pixels = {point for point, degree in degrees.items() if degree >= 3}
    branch_clusters = _expand_branch_clusters(skel, _cluster_points(branch_pixels, skel), endpoints)
    branch_clusters, passthrough_short_neighbor_by_point = _split_pseudo_branch_clusters(skel, branch_clusters)

    components = _components(skel)
    component_index_by_point: dict[tuple[int, int], int] = {}
    component_rows: list[dict] = []
    for component_index, component in enumerate(components, start=1):
        for point in component:
            component_index_by_point[point] = component_index
        component_rows.append(
            {
                "component_id": component_index,
                "pixel_count": len(component),
                "point_count": len(component),
                "segment_count": 0,
                "is_loop": False,
            }
        )

    branch_cluster_by_point: dict[tuple[int, int], int] = {}
    branch_cluster_representatives: dict[int, tuple[int, int]] = {}
    for cluster_index, cluster in enumerate(branch_clusters):
        branch_cluster_representatives[cluster_index] = min(cluster)
        for point in cluster:
            branch_cluster_by_point[point] = cluster_index

    terminal_lookup: dict[tuple[int, int], str] = {point: "endpoint" for point in endpoints}
    for point in branch_cluster_by_point:
        terminal_lookup[point] = "branch"

    visited_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    segments: list[dict] = []
    segment_component_counts: dict[int, int] = {}

    for cluster_index, cluster in enumerate(branch_clusters):
        representative = branch_cluster_representatives[cluster_index]
        outgoing_edges: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for point in sorted(cluster):
            for neighbor in _connected_neighbors(skel, point):
                if neighbor in cluster:
                    visited_edges.add(_edge_key(point, neighbor))
                    continue
                outgoing_edges.append((point, neighbor))
        outgoing_edges.sort()
        for start_point, neighbor in outgoing_edges:
            first_edge = _edge_key(start_point, neighbor)
            if first_edge in visited_edges:
                continue
            path = _trace_segment(
                skel,
                terminal_lookup,
                start_point,
                neighbor,
                passthrough_short_neighbor_by_point=passthrough_short_neighbor_by_point,
            )
            for start, end in zip(path[:-1], path[1:]):
                visited_edges.add(_edge_key(start, end))
            if path[-1] in branch_cluster_by_point:
                path[-1] = branch_cluster_representatives[branch_cluster_by_point[path[-1]]]
            if path[0] != representative:
                path[0] = representative
            if len(path) < min_segment_pixels:
                continue
            component_id = component_index_by_point[start_point]
            is_loop = path[0] == path[-1]
            segments.append(
                {
                    "segment_id": len(segments) + 1,
                    "points": path,
                    "pixel_count": len(path),
                    "length_px": _polyline_length(path),
                    "start": path[0],
                    "end": path[-1],
                    "component_id": component_id,
                    "is_loop": is_loop,
                }
            )
            segment_component_counts[component_id] = segment_component_counts.get(component_id, 0) + 1

    for endpoint in sorted(endpoints):
        for neighbor in _connected_neighbors(skel, endpoint):
            first_edge = _edge_key(endpoint, neighbor)
            if first_edge in visited_edges:
                continue
            path = _trace_segment(
                skel,
                terminal_lookup,
                endpoint,
                neighbor,
                passthrough_short_neighbor_by_point=passthrough_short_neighbor_by_point,
            )
            for start, end in zip(path[:-1], path[1:]):
                visited_edges.add(_edge_key(start, end))
            if path[-1] in branch_cluster_by_point:
                path[-1] = branch_cluster_representatives[branch_cluster_by_point[path[-1]]]
            if len(path) < min_segment_pixels:
                continue
            component_id = component_index_by_point[endpoint]
            is_loop = path[0] == path[-1]
            segments.append(
                {
                    "segment_id": len(segments) + 1,
                    "points": path,
                    "pixel_count": len(path),
                    "length_px": _polyline_length(path),
                    "start": path[0],
                    "end": path[-1],
                    "component_id": component_id,
                    "is_loop": is_loop,
                }
            )
            segment_component_counts[component_id] = segment_component_counts.get(component_id, 0) + 1

    for component_row, component in zip(component_rows, components):
        if any(point in terminal_lookup for point in component):
            continue
        path = _trace_component_loop(skel, component)
        if len(path) < min_segment_pixels or path[0] != path[-1]:
            continue
        component_id = component_row["component_id"]
        segments.append(
            {
                "segment_id": len(segments) + 1,
                "points": path,
                "pixel_count": len(path),
                "length_px": _polyline_length(path),
                "start": path[0],
                "end": path[-1],
                "component_id": component_id,
                "is_loop": True,
            }
        )
        segment_component_counts[component_id] = segment_component_counts.get(component_id, 0) + 1

    for row in component_rows:
        component_id = row["component_id"]
        row["segment_count"] = segment_component_counts.get(component_id, 0)
        row["is_loop"] = any(
            segment["component_id"] == component_id and segment["is_loop"]
            for segment in segments
        )

    return {
        "segments": segments,
        "segment_count": len(segments),
        "endpoint_count": len(endpoints),
        "branch_point_count": len(branch_clusters),
        "component_count": len(components),
        "components": component_rows,
    }
