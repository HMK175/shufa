"""Extract stroke candidates from a full glyph image for offline classification."""

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Iterable, List

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline import BLUR_KSIZE
from skeleton import clean_junction_spurs, skeletonize, straighten_junctions
from stroke import get_stroke_list, prune_skeleton, set_trace_context
from utils import estimate_stroke_width, load_image, preprocess


DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "output" / "candidates"


def _stroke_metrics(points: np.ndarray) -> dict:
    pts = np.array(points, dtype=float)
    y0, x0 = pts.min(axis=0)
    y1, x1 = pts.max(axis=0)
    if len(pts) < 2:
        path_len = 0.0
        endpoint = 0.0
        winding = 0.0
    else:
        path_len = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
        endpoint = float(np.linalg.norm(pts[-1] - pts[0]))
        winding = path_len / endpoint if endpoint > 1 else 999.0
    return {
        "point_count": int(len(pts)),
        "bbox": f"{y0:.1f};{x0:.1f};{y1:.1f};{x1:.1f}",
        "path_length": path_len,
        "endpoint_distance": endpoint,
        "winding": winding,
    }


def _render_candidate(points: np.ndarray, out_path: Path, image_size: int = 128) -> None:
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
    draw = np.zeros_like(canvas)
    mapped = []
    for y, x in pts:
        yy = (y - cy) * scale + image_size / 2.0
        xx = (x - cx) * scale + image_size / 2.0
        mapped.append((int(round(xx)), int(round(yy))))
    for p0, p1 in zip(mapped[:-1], mapped[1:]):
        cv2.line(draw, p0, p1, color=255, thickness=5, lineType=cv2.LINE_AA)
    if len(mapped) == 1:
        cv2.circle(draw, mapped[0], 3, 255, -1)
    canvas[draw > 0] = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), canvas)


def _prepare_strokes(image_path: Path) -> List[np.ndarray]:
    char_id = image_path.stem
    set_trace_context(char_id)
    image = load_image(str(image_path))
    binary = preprocess(image, blur_ksize=BLUR_KSIZE)
    half_width = estimate_stroke_width(binary)
    skel = skeletonize(binary)
    skel = prune_skeleton(skel, min_branch_len=max(30, int(half_width * 1.8)))
    skel = straighten_junctions(skel)
    skel = clean_junction_spurs(skel)
    return [np.array(stroke, dtype=float) for stroke in get_stroke_list(skel)]


def extract_candidates(image_path: Path, output_root: Path = DEFAULT_OUTPUT_ROOT, image_size: int = 128) -> Path:
    char_id = image_path.stem
    out_dir = output_root / char_id
    out_dir.mkdir(parents=True, exist_ok=True)
    strokes = _prepare_strokes(image_path)
    csv_path = out_dir / "candidates.csv"
    rows = []
    for idx, stroke in enumerate(strokes, start=1):
        candidate_id = f"{char_id}_{idx:02d}"
        rel_image = f"{candidate_id}.png"
        candidate_path = out_dir / rel_image
        _render_candidate(stroke, candidate_path, image_size=image_size)
        metrics = _stroke_metrics(stroke)
        rows.append(
            {
                "candidate_id": candidate_id,
                "char_id": char_id,
                "source_image": str(image_path),
                "candidate_image": rel_image,
                "point_count": metrics["point_count"],
                "bbox": metrics["bbox"],
                "path_length": f"{metrics['path_length']:.3f}",
                "endpoint_distance": f"{metrics['endpoint_distance']:.3f}",
                "winding": f"{metrics['winding']:.3f}",
            }
        )

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        fields = [
            "candidate_id",
            "char_id",
            "source_image",
            "candidate_image",
            "point_count",
            "bbox",
            "path_length",
            "endpoint_distance",
            "winding",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {csv_path} candidates={len(rows)}")
    return csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract stroke candidates from a glyph image")
    parser.add_argument("image")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--image-size", type=int, default=128)
    args = parser.parse_args()
    extract_candidates(Path(args.image).resolve(), Path(args.output_root).resolve(), image_size=args.image_size)


if __name__ == "__main__":
    main()
