"""Small cleanup helpers for offline stroke recovery."""

from __future__ import annotations

from collections import deque
from typing import Iterable

import numpy as np


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


def _components(skeleton: np.ndarray) -> list[list[tuple[int, int]]]:
    skel = np.asarray(skeleton, dtype=bool)
    if skel.ndim != 2:
        raise ValueError("skeleton must be a 2D array")

    seen = np.zeros(skel.shape, dtype=bool)
    components: list[list[tuple[int, int]]] = []
    for y, x in zip(*np.nonzero(skel)):
        y = int(y)
        x = int(x)
        if seen[y, x]:
            continue
        queue: deque[tuple[int, int]] = deque([(y, x)])
        seen[y, x] = True
        component: list[tuple[int, int]] = []
        while queue:
            cy, cx = queue.popleft()
            component.append((cy, cx))
            for ny, nx in _connected_neighbors(skel, (cy, cx)):
                if not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        components.append(component)
    return components


def _component_anchor(component: list[tuple[int, int]]) -> tuple[int, int]:
    return min(component, key=lambda point: (point[0], point[1]))


def _degree(skeleton: np.ndarray, y: int, x: int) -> int:
    return len(_connected_neighbors(skeleton, (y, x)))


def _endpoints(skeleton: np.ndarray) -> list[tuple[int, int]]:
    skel = np.asarray(skeleton, dtype=bool)
    return [
        (int(y), int(x))
        for y, x in zip(*np.nonzero(skel))
        if _degree(skel, int(y), int(x)) == 1
    ]


def _trace_from_endpoint(
    skeleton: np.ndarray,
    start: tuple[int, int],
    max_length: int,
) -> tuple[list[tuple[int, int]], str]:
    skel = np.asarray(skeleton, dtype=bool)
    path = [start]
    prev: tuple[int, int] | None = None
    current = start

    for _ in range(max_length):
        candidates = [point for point in _connected_neighbors(skel, current) if point != prev]
        if not candidates:
            return path, "dead_end"
        if len(candidates) > 1:
            return path, "branch"

        nxt = candidates[0]
        prev, current = current, nxt
        path.append(current)

        degree = _degree(skel, *current)
        if degree >= 3:
            return path, "branch"
        if degree == 1 and current != start:
            return path, "endpoint"

    return path, "long"


def remove_small_components(skeleton: np.ndarray, min_component_pixels: int):
    skel = np.asarray(skeleton, dtype=bool).copy()
    components = _components(skel)
    if not components:
        return skel, 0

    main_component = max(
        components,
        key=lambda component: (
            len(component),
            -_component_anchor(component)[0],
            -_component_anchor(component)[1],
        ),
    )
    cleaned = np.zeros_like(skel)
    removed = 0
    for component in components:
        keep = component is main_component or len(component) >= min_component_pixels
        if keep:
            for y, x in component:
                cleaned[y, x] = True
        else:
            removed += 1
    return cleaned, removed


def prune_short_spurs(skeleton: np.ndarray, max_length: int):
    skel = np.asarray(skeleton, dtype=bool).copy()
    if max_length <= 0:
        return skel, 0

    remove: set[tuple[int, int]] = set()
    pruned = 0
    for endpoint in _endpoints(skel):
        if endpoint in remove:
            continue
        path, terminal = _trace_from_endpoint(skel, endpoint, max_length)
        if terminal == "branch" and 1 < len(path) <= max_length + 1:
            remove.update(path[:-1])
            pruned += 1
        elif terminal in {"dead_end", "endpoint"} and len(path) <= max_length:
            remove.update(path)
            pruned += 1

    for y, x in remove:
        skel[y, x] = False
    return skel, pruned
