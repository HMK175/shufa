"""Tiny skeletonization helpers for the offline MVP."""

from __future__ import annotations

import numpy as np


def _run_midpoints(indices: np.ndarray) -> list[int]:
    if indices.size == 0:
        return []
    splits = np.where(np.diff(indices) > 1)[0] + 1
    mids: list[int] = []
    for run in np.split(indices, splits):
        if run.size:
            mids.append(int(run[len(run) // 2]))
    return mids


def numpy_skeletonize(mask: np.ndarray) -> np.ndarray:
    arr = np.asarray(mask, dtype=bool)
    if arr.ndim != 2:
        raise ValueError("mask must be a 2D array")

    skel = np.zeros_like(arr, dtype=bool)
    for y in range(arr.shape[0]):
        for x in _run_midpoints(np.flatnonzero(arr[y])):
            skel[y, x] = True
    for x in range(arr.shape[1]):
        for y in _run_midpoints(np.flatnonzero(arr[:, x])):
            skel[y, x] = True
    return skel


def skeleton_backend_name() -> str:
    try:
        from skimage.morphology import skeletonize  # noqa: F401

        return "skimage_skeletonize"
    except (ImportError, ModuleNotFoundError):
        return "numpy_midpoint_fallback"


def skeleton_backend_warning(backend_name: str | None = None) -> str | None:
    name = backend_name or skeleton_backend_name()
    if name == "numpy_midpoint_fallback":
        return (
            "scikit-image is not available; using the lightweight numpy midpoint "
            "fallback can break crossing centers and over-fragment brush intersections."
        )
    return None


def ridge_skeleton(mask: np.ndarray) -> np.ndarray:
    arr = np.asarray(mask, dtype=bool)
    if arr.ndim != 2:
        raise ValueError("mask must be a 2D array")

    try:
        from skimage.morphology import skeletonize

        return skeletonize(arr).astype(bool)
    except (ImportError, ModuleNotFoundError):
        return numpy_skeletonize(arr)


def topology_metrics(skeleton: np.ndarray) -> dict[str, int]:
    skel = np.asarray(skeleton, dtype=bool)
    if skel.ndim != 2:
        raise ValueError("skeleton must be a 2D array")

    padded = np.pad(skel, 1, mode="constant", constant_values=False)
    endpoints = 0
    branches = 0
    for y, x in zip(*np.nonzero(skel)):
        neighborhood = padded[y : y + 3, x : x + 3]
        degree = int(neighborhood.sum()) - 1
        if degree == 1:
            endpoints += 1
        elif degree >= 3:
            branches += 1

    return {
        "skeleton_pixel_count": int(skel.sum()),
        "endpoint_count": endpoints,
        "branch_point_count": branches,
    }
