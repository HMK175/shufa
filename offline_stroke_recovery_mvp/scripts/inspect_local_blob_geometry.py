from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "offline_stroke_recovery_mvp" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from callirewrite_hybrid import load_callirewrite_segments
from makemeahanzi_prior import regroup_ordered_segments_by_makemeahanzi
from ordering import order_segments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect how much of a local foreground blob is covered by one regrouped segment."
    )
    parser.add_argument("--sample", required=True, help="Sample alias, e.g. xin / yong / zhong.")
    parser.add_argument(
        "--source-ids",
        required=True,
        help="Comma-separated source segment ids that identify the regrouped segment, e.g. 17 or 8,6.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=200,
        help="Foreground threshold for the input image.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sample = args.sample.strip().lower()
    source_ids = tuple(int(part.strip()) for part in args.source_ids.split(",") if part.strip())
    if not source_ids:
        raise SystemExit("No source ids were provided.")

    converted_dir = (
        REPO_ROOT / "offline_stroke_recovery_mvp" / "outputs" / "callirewrite_runtime_probe" / "converted" / sample
    )
    input_path = REPO_ROOT / "offline_stroke_recovery_mvp" / "outputs" / "visual_smoke_probe_after_review" / "inputs" / f"{sample}.png"
    graphics_path = REPO_ROOT / "code" / "data" / "makemeahanzi" / "graphics.txt"

    raw_segments, _ = load_callirewrite_segments(converted_dir)
    ordered_segments = order_segments(
        raw_segments,
        endpoint_merge_distance=0.0,
        direction_cos_threshold=0.65,
    )
    foreground_mask = np.asarray(Image.open(input_path).convert("L"), dtype=np.uint8) < int(args.threshold)
    regrouped, meta = regroup_ordered_segments_by_makemeahanzi(
        ordered_segments,
        sample_name=sample,
        canvas_shape=tuple(int(value) for value in foreground_mask.shape),
        foreground_mask=foreground_mask,
        graphics_path=graphics_path,
    )
    target = next(segment for segment in regrouped if tuple(segment.get("source_segment_ids", ())) == source_ids)
    points = np.asarray(target.get("points", ()), dtype=float)
    component_pixels = _extract_connected_component(points[len(points) // 2], foreground_mask)
    blob_metrics = _principal_axis_metrics(component_pixels)
    segment_metrics = _principal_axis_metrics(points)
    payload = {
        "sample": sample,
        "source_ids": list(source_ids),
        "component_id": int(target.get("component_id", 0) or 0),
        "point_count": int(len(points)),
        "path_length": float(_polyline_length(points)),
        "blob_component_pixels": int(len(component_pixels)),
        "blob_major_span": float(blob_metrics["major_span"]),
        "blob_minor_span": float(blob_metrics["minor_span"]),
        "segment_major_span": float(segment_metrics["major_span"]),
        "segment_minor_span": float(segment_metrics["minor_span"]),
        "major_span_coverage": float(
            segment_metrics["major_span"] / max(blob_metrics["major_span"], 1e-6)
        ),
        "meta": meta,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _extract_connected_component(seed_point: np.ndarray, foreground_mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(foreground_mask, dtype=bool)
    height, width = mask.shape
    y = int(round(float(seed_point[0])))
    x = int(round(float(seed_point[1])))
    if not (0 <= y < height and 0 <= x < width) or not bool(mask[y, x]):
        return np.asarray([[float(y), float(x)]], dtype=float)

    seen = {(y, x)}
    queue = deque([(y, x)])
    component: list[tuple[float, float]] = []
    for_yx = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    while queue:
        row, col = queue.popleft()
        if not bool(mask[row, col]):
            continue
        component.append((float(row), float(col)))
        for dy, dx in for_yx:
            next_row = row + dy
            next_col = col + dx
            if 0 <= next_row < height and 0 <= next_col < width and (next_row, next_col) not in seen:
                if bool(mask[next_row, next_col]):
                    seen.add((next_row, next_col))
                    queue.append((next_row, next_col))
    return np.asarray(component, dtype=float)


def _principal_axis_metrics(points: np.ndarray) -> dict[str, float]:
    pts = np.asarray(points, dtype=float)
    if len(pts) == 0:
        return {"major_span": 0.0, "minor_span": 0.0}
    if len(pts) == 1:
        return {"major_span": 0.0, "minor_span": 0.0}
    centered = pts - pts.mean(axis=0, keepdims=True)
    _, _, vh = np.linalg.svd(centered, full_matrices=False)
    major_axis = vh[0]
    minor_axis = vh[-1]
    major_projection = centered @ major_axis
    minor_projection = centered @ minor_axis
    return {
        "major_span": float(major_projection.max() - major_projection.min()),
        "minor_span": float(minor_projection.max() - minor_projection.min()),
    }


def _polyline_length(points: np.ndarray) -> float:
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))


if __name__ == "__main__":
    raise SystemExit(main())
