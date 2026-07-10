"""Batch evaluation for tune/holdout glyph sets.

Runs the existing pipeline without RL, then writes one structured CSV row per
glyph for experiment records.
"""

import argparse
import csv
import math
import os
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from pipeline import SAMPLE, SMOOTH, TRACE_MODE, process_one
from stroke import get_last_trace_diagnostics
from stroke_knowledge import get_stroke_count


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "output"
SUBSET_DIRS = {
    "tune": SCRIPT_DIR / "tune_set",
    "holdout": SCRIPT_DIR / "holdout_set",
}


def _read_set_names(subset: str) -> List[str]:
    list_path = SCRIPT_DIR / f"{subset}_set.txt"
    if list_path.exists():
        names = []
        for line in list_path.read_text(encoding="utf-8").splitlines():
            name = line.strip()
            if name and not name.startswith("#"):
                names.append(name)
        return names

    return sorted(path.stem for path in SUBSET_DIRS[subset].glob("*.png"))


def _read_stroke_csv(path: Path) -> List[np.ndarray]:
    strokes: List[List[Tuple[float, float]]] = []
    current: List[Tuple[float, float]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            y = float(row["y"])
            x = float(row["x"])
            if math.isnan(y) or math.isnan(x):
                if current:
                    strokes.append(current)
                    current = []
            else:
                current.append((y, x))
    if current:
        strokes.append(current)
    return [np.array(stroke, dtype=float) for stroke in strokes]


def _max_winding(strokes: List[np.ndarray]) -> float:
    max_ratio = 0.0
    for stroke in strokes:
        if len(stroke) < 2:
            continue
        path_len = float(np.sum(np.linalg.norm(np.diff(stroke, axis=0), axis=1)))
        endpoint_distance = float(np.linalg.norm(stroke[-1] - stroke[0]))
        ratio = path_len / endpoint_distance if endpoint_distance > 1 else 999.0
        max_ratio = max(max_ratio, ratio)
    return max_ratio


def _evaluate_one(subset: str, name: str) -> Dict[str, object]:
    image_path = SUBSET_DIRS[subset] / f"{name}.png"
    out_csv = OUTPUT_DIR / f"eval_{subset}_{name}.csv"
    out_img = OUTPUT_DIR / f"eval_{subset}_{name}.png"

    ok = process_one(
        str(image_path),
        str(out_csv),
        str(out_img),
        SMOOTH,
        SAMPLE,
        TRACE_MODE,
        use_rl=False,
    )
    if not ok:
        raise RuntimeError(f"Pipeline failed for {image_path}")

    diag = get_last_trace_diagnostics()
    selected = diag.get("selected", {})
    final_strokes = _read_stroke_csv(out_csv)
    expected = get_stroke_count(name)
    final_count = len(final_strokes)
    count_correct = expected is not None and final_count == expected

    return {
        "char": name,
        "subset": subset,
        "expected": expected if expected is not None else "",
        "method": diag.get("method", ""),
        "pred": selected.get("count", ""),
        "fallback": diag.get("fallback_reason") or "none",
        "final_csv_strokes": final_count,
        "max_winding": f"{_max_winding(final_strokes):.2f}",
        "skeleton_px": diag.get("skeleton_px", ""),
        "endpoints": diag.get("endpoints", ""),
        "junction_px": diag.get("junction_px", ""),
        "count_correct": "yes" if count_correct else "no",
    }


def evaluate_subset(subset: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = [_evaluate_one(subset, name) for name in _read_set_names(subset)]
    output_csv = OUTPUT_DIR / f"{subset}_eval.csv"
    fields = [
        "char",
        "subset",
        "expected",
        "method",
        "pred",
        "fallback",
        "final_csv_strokes",
        "max_winding",
        "skeleton_px",
        "endpoints",
        "junction_px",
        "count_correct",
    ]
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    correct = sum(1 for row in rows if row["count_correct"] == "yes")
    worst = max(rows, key=lambda row: float(row["max_winding"])) if rows else None
    print(f"Wrote {output_csv}")
    print(f"{subset}: total={len(rows)}, count_correct={correct}")
    if worst:
        print(
            f"{subset}: max_winding={worst['max_winding']} "
            f"char={worst['char']}"
        )
    return output_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate tune/holdout glyph set")
    parser.add_argument("--subset", choices=["tune", "holdout"], required=True)
    args = parser.parse_args()
    evaluate_subset(args.subset)


if __name__ == "__main__":
    main()
