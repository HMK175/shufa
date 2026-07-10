"""H1-lite constraint-bounded median adaptation prototype.

This diagnostic prototype keeps the MakeMeAHanzi median stroke order and uses
only H2 font-reference constraints marked as ``usable_for_adaptation``. It does
not use raw skeleton paths, unordered skeleton segments, nearest-point pulling,
execution/workspace/robot outputs, or the default pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from font_outline_basis_feasibility import DEFAULT_GRAPHICS
from knowledge import MakeMeAHanziKnowledge
from trajectory_tools import normalize_medians, stroke_path_length


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
DEFAULT_H2_CONSTRAINTS_JSON = (
    EXP_DIR
    / "outputs"
    / "font_reference_constraints_20260619_230426"
    / "font_reference_constraints.json"
)
DEFAULT_SAMPLE_SPECS: list[tuple[str, str]] = [
    ("\u4eba", "kaishu"),
    ("\u5c71", "lishu"),
]
ALLOWED_CONSTRAINTS = {
    "bbox_aspect",
    "lower_half_width_ratio",
    "left_right_spread",
    "bbox_center_shift_x",
    "bbox_center_shift_y",
}
VARIANT_PARAMS = {
    "conservative": {
        "aspect_alpha": 0.16,
        "lower_alpha": 0.16,
        "spread_alpha": 0.12,
        "center_shift_alpha": 0.20,
        "max_point_shift_px": 12.0,
    },
    "balanced": {
        "aspect_alpha": 0.30,
        "lower_alpha": 0.28,
        "spread_alpha": 0.20,
        "center_shift_alpha": 0.32,
        "max_point_shift_px": 18.0,
    },
}

TRIAL_FIELDS = ["y", "x", "stroke_id", "point_index", "is_break", "variant", "source"]
SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "sample_dir",
    "summary_json",
    "compare_png",
    "stroke_count",
    "point_count",
    "used_constraints",
    "bbox_aspect_median",
    "bbox_aspect_target",
    "bbox_aspect_conservative",
    "bbox_aspect_balanced",
    "lower_half_width_median",
    "lower_half_width_target",
    "lower_half_width_conservative",
    "lower_half_width_balanced",
    "left_right_spread_median",
    "left_right_spread_target",
    "left_right_spread_conservative",
    "left_right_spread_balanced",
    "max_point_shift_px_conservative",
    "max_point_shift_px_balanced",
    "mean_point_shift_px_conservative",
    "mean_point_shift_px_balanced",
    "path_length_ratio_conservative",
    "path_length_ratio_balanced",
    "stroke_count_preserved",
    "warning",
    "recommended_for_visual_followup",
]
MANIFEST_FIELDS = ["char", "char_id", "style", "variant", "trial_csv", "compare_png", "summary_json", "warning"]


def _char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else ""


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _flatten(strokes: Sequence[np.ndarray]) -> np.ndarray:
    parts = [np.asarray(stroke, dtype=float) for stroke in strokes if len(stroke)]
    if not parts:
        return np.empty((0, 2), dtype=float)
    return np.vstack(parts)


def _bbox(points: np.ndarray) -> dict[str, float]:
    pts = np.asarray(points, dtype=float)
    if len(pts) == 0:
        return {"y_min": 0.0, "y_max": 0.0, "x_min": 0.0, "x_max": 0.0, "height": 0.0, "width": 0.0}
    y_min, x_min = np.min(pts, axis=0)
    y_max, x_max = np.max(pts, axis=0)
    return {
        "y_min": float(y_min),
        "y_max": float(y_max),
        "x_min": float(x_min),
        "x_max": float(x_max),
        "height": float(y_max - y_min),
        "width": float(x_max - x_min),
    }


def bbox_aspect(strokes: Sequence[np.ndarray]) -> float:
    box = _bbox(_flatten(strokes))
    return round(box["width"] / box["height"] if box["height"] > 1e-9 else 0.0, 6)


def lower_half_width_ratio(strokes: Sequence[np.ndarray]) -> float:
    pts = _flatten(strokes)
    if len(pts) == 0:
        return 0.0
    box = _bbox(pts)
    if box["width"] <= 1e-9:
        return 0.0
    threshold = box["y_min"] + 0.5 * box["height"]
    lower = pts[pts[:, 0] >= threshold]
    if len(lower) == 0:
        return 0.0
    width = float(np.max(lower[:, 1]) - np.min(lower[:, 1]))
    return round(width / box["width"], 6)


def left_right_spread(strokes: Sequence[np.ndarray]) -> float:
    pts = _flatten(strokes)
    if len(pts) == 0:
        return 0.0
    box = _bbox(pts)
    if box["width"] <= 1e-9:
        return 0.0
    center_x = 0.5 * (box["x_min"] + box["x_max"])
    spread = (center_x - box["x_min"] + box["x_max"] - center_x) / box["width"]
    return round(float(spread), 6)


def lower_half_width(strokes: Sequence[np.ndarray]) -> float:
    pts = _flatten(strokes)
    if len(pts) == 0:
        return 0.0
    box = _bbox(pts)
    threshold = box["y_min"] + 0.5 * box["height"]
    lower = pts[pts[:, 0] >= threshold]
    if len(lower) == 0:
        return 0.0
    return round(float(np.max(lower[:, 1]) - np.min(lower[:, 1])), 6)


def _path_length(strokes: Sequence[np.ndarray]) -> float:
    return float(sum(stroke_path_length(np.asarray(stroke, dtype=float)) for stroke in strokes))


def _shift_stats(original: Sequence[np.ndarray], candidate: Sequence[np.ndarray]) -> dict[str, float]:
    shifts: list[float] = []
    for src, cand in zip(original, candidate):
        delta = np.asarray(cand, dtype=float) - np.asarray(src, dtype=float)
        shifts.extend(float(value) for value in np.linalg.norm(delta, axis=1))
    return {
        "max_point_shift_px": round(max(shifts) if shifts else 0.0, 6),
        "mean_point_shift_px": round(float(np.mean(shifts)) if shifts else 0.0, 6),
    }


def _cap_to_original(original: Sequence[np.ndarray], candidate: Sequence[np.ndarray], max_shift_px: float) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    for src, cand in zip(original, candidate):
        src_arr = np.asarray(src, dtype=float)
        cand_arr = np.asarray(cand, dtype=float)
        delta = cand_arr - src_arr
        lengths = np.linalg.norm(delta, axis=1)
        limited = cand_arr.copy()
        for idx, length in enumerate(lengths):
            if length > max_shift_px:
                limited[idx] = src_arr[idx] + delta[idx] * (max_shift_px / max(float(length), 1e-9))
        out.append(limited)
    return out


def load_usable_constraints(constraints_json_path: Path | str, char_id: str, style: str) -> dict[str, float]:
    payload = json.loads(Path(constraints_json_path).read_text(encoding="utf-8"))
    for sample in payload.get("samples", []):
        if sample.get("char_id") != char_id or sample.get("style") != style:
            continue
        constraints: dict[str, float] = {}
        for name, item in sample.get("constraints", {}).items():
            if name not in ALLOWED_CONSTRAINTS:
                continue
            if item.get("recommended_use") != "usable_for_adaptation":
                continue
            constraints[name] = float(item.get("value", 0.0))
        return constraints
    raise KeyError(f"H2 usable constraints not found for {char_id}/{style}")


def _scaled_for_aspect(
    strokes: Sequence[np.ndarray],
    target_aspect: float,
    aspect_alpha: float,
    max_scale_delta: float = 0.18,
) -> list[np.ndarray]:
    pts = _flatten(strokes)
    box = _bbox(pts)
    current_aspect = bbox_aspect(strokes)
    if current_aspect <= 1e-9 or target_aspect <= 1e-9 or box["width"] <= 1e-9 or box["height"] <= 1e-9:
        return [np.asarray(stroke, dtype=float).copy() for stroke in strokes]
    ratio = math.sqrt(max(target_aspect / current_aspect, 1e-9))
    sx_raw = ratio
    sy_raw = 1.0 / ratio
    sx_limited = max(1.0 - max_scale_delta, min(1.0 + max_scale_delta, sx_raw))
    sy_limited = max(1.0 - max_scale_delta, min(1.0 + max_scale_delta, sy_raw))
    sx = 1.0 + aspect_alpha * (sx_limited - 1.0)
    sy = 1.0 + aspect_alpha * (sy_limited - 1.0)
    cy = 0.5 * (box["y_min"] + box["y_max"])
    cx = 0.5 * (box["x_min"] + box["x_max"])
    out: list[np.ndarray] = []
    for stroke in strokes:
        arr = np.asarray(stroke, dtype=float).copy()
        arr[:, 0] = cy + (arr[:, 0] - cy) * sy
        arr[:, 1] = cx + (arr[:, 1] - cx) * sx
        out.append(arr)
    return out


def _apply_spread_and_shift(
    strokes: Sequence[np.ndarray],
    constraints: dict[str, float],
    lower_alpha: float,
    spread_alpha: float,
    center_shift_alpha: float,
    image_size: int,
) -> list[np.ndarray]:
    pts = _flatten(strokes)
    box = _bbox(pts)
    if len(pts) == 0 or box["width"] <= 1e-9 or box["height"] <= 1e-9:
        return [np.asarray(stroke, dtype=float).copy() for stroke in strokes]
    cx = 0.5 * (box["x_min"] + box["x_max"])
    cy = 0.5 * (box["y_min"] + box["y_max"])
    current_lower_ratio = lower_half_width_ratio(strokes)
    current_spread = left_right_spread(strokes)
    target_lower_ratio = float(constraints.get("lower_half_width_ratio", current_lower_ratio))
    target_spread = float(constraints.get("left_right_spread", current_spread))
    lower_delta = max(-0.18, min(0.18, target_lower_ratio - current_lower_ratio))
    spread_delta = max(-0.12, min(0.12, target_spread - current_spread))
    center_dx = float(constraints.get("bbox_center_shift_x", 0.0)) * image_size * center_shift_alpha
    center_dy = float(constraints.get("bbox_center_shift_y", 0.0)) * image_size * center_shift_alpha
    lower_threshold = box["y_min"] + 0.5 * box["height"]
    out: list[np.ndarray] = []
    for stroke in strokes:
        arr = np.asarray(stroke, dtype=float).copy()
        for idx, (y, x) in enumerate(arr):
            side = -1.0 if x < cx else 1.0
            lower_weight = max(0.0, min(1.0, (y - lower_threshold) / max(box["height"] * 0.5, 1e-9)))
            spread_px = side * box["width"] * (spread_alpha * spread_delta + lower_alpha * lower_delta * lower_weight) * 0.5
            arr[idx, 1] = x + spread_px + center_dx
            arr[idx, 0] = y + center_dy
        out.append(arr)
    return out


def adapt_with_h2_constraints(
    median_strokes: Sequence[np.ndarray],
    constraints: dict[str, float],
    variant: str,
    image_size: int = 256,
) -> list[np.ndarray]:
    params = VARIANT_PARAMS[variant]
    adapted = _scaled_for_aspect(
        median_strokes,
        target_aspect=float(constraints.get("bbox_aspect", bbox_aspect(median_strokes))),
        aspect_alpha=float(params["aspect_alpha"]),
    )
    adapted = _apply_spread_and_shift(
        adapted,
        constraints=constraints,
        lower_alpha=float(params["lower_alpha"]),
        spread_alpha=float(params["spread_alpha"]),
        center_shift_alpha=float(params["center_shift_alpha"]),
        image_size=image_size,
    )
    return _cap_to_original(median_strokes, adapted, max_shift_px=float(params["max_point_shift_px"]))


def _write_trial_csv(path: Path, strokes: Sequence[np.ndarray], variant: str) -> int:
    rows: list[dict[str, Any]] = []
    point_count = 0
    for stroke_id, stroke in enumerate(strokes, start=1):
        pts = np.asarray(stroke, dtype=float)
        for point_index, (y, x) in enumerate(pts):
            rows.append(
                {
                    "y": round(float(y), 6),
                    "x": round(float(x), 6),
                    "stroke_id": stroke_id,
                    "point_index": point_index,
                    "is_break": 0,
                    "variant": variant,
                    "source": "constraint_bounded_adaptation_h1_lite_trial",
                }
            )
            point_count += 1
        rows.append(
            {
                "y": "nan",
                "x": "nan",
                "stroke_id": stroke_id,
                "point_index": "",
                "is_break": 1,
                "variant": variant,
                "source": "constraint_bounded_adaptation_h1_lite_trial",
            }
        )
    _write_csv(path, rows, TRIAL_FIELDS)
    return point_count


def _variant_metrics(original: Sequence[np.ndarray], variant: Sequence[np.ndarray]) -> dict[str, float]:
    shifts = _shift_stats(original, variant)
    original_length = _path_length(original)
    variant_length = _path_length(variant)
    return {
        "bbox_aspect": bbox_aspect(variant),
        "lower_half_width": lower_half_width(variant),
        "lower_half_width_ratio": lower_half_width_ratio(variant),
        "left_right_spread": left_right_spread(variant),
        "max_point_shift_px": shifts["max_point_shift_px"],
        "mean_point_shift_px": shifts["mean_point_shift_px"],
        "path_length_ratio": round(variant_length / original_length if original_length > 1e-9 else 0.0, 6),
    }


def _draw_strokes(ax: Any, strokes: Sequence[np.ndarray], title: str, color: str) -> None:
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlim(0, 256)
    ax.set_ylim(256, 0)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(True, color="#eeeeee", linewidth=0.4)
    for idx, stroke in enumerate(strokes, start=1):
        pts = np.asarray(stroke, dtype=float)
        if len(pts) < 2:
            continue
        ax.plot(pts[:, 1], pts[:, 0], color=color, linewidth=1.8)
        ax.scatter(pts[0, 1], pts[0, 0], s=10, color=color)
        mid = pts[len(pts) // 2]
        ax.text(mid[1], mid[0], str(idx), fontsize=7, color="#111111")


def _write_compare(path: Path, char: str, style: str, median: Sequence[np.ndarray], conservative: Sequence[np.ndarray], balanced: Sequence[np.ndarray], h2_figure: Path | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 4, figsize=(12.8, 3.4), dpi=150)
    _draw_strokes(axes[0], median, "original median", "#333333")
    axes[1].set_title("H2 reference constraints", fontsize=8)
    axes[1].set_aspect("equal")
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    axes[1].set_xlim(0, 256)
    axes[1].set_ylim(256, 0)
    if h2_figure and h2_figure.exists():
        axes[1].text(8, 28, "H2 reference figure:", fontsize=7)
        axes[1].text(8, 48, h2_figure.name, fontsize=6, wrap=True)
    else:
        axes[1].text(8, 28, "H2 constraints loaded\n(no image reference)", fontsize=7)
    _draw_strokes(axes[2], conservative, "H1-lite conservative", "#d62728")
    _draw_strokes(axes[3], balanced, "H1-lite balanced", "#2ca02c")
    fig.suptitle(f"H1-lite constraint-bounded adaptation {_char_id(char)} / {style}", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(path)
    plt.close(fig)


def _load_median(char: str, image_size: int) -> list[np.ndarray]:
    glyph = MakeMeAHanziKnowledge(DEFAULT_GRAPHICS).get_glyph(char)
    return list(normalize_medians(glyph.medians, image_size=image_size))


def _h2_reference_figure(char_id: str, style: str) -> Path:
    return DEFAULT_H2_CONSTRAINTS_JSON.parent / "figures" / f"constraint_reference_{char_id}_{style}.png"


def _write_report(path: Path, output_dir: Path, rows: Sequence[dict[str, Any]]) -> None:
    lines = [
        "# H1-lite constraint-bounded median adaptation prototype",
        "",
        "H1-lite uses Route A median strokes plus H2 usable font-reference constraints. It is a trial-only diagnostic layer and is not used by default.",
        "",
        "## Boundary",
        "",
        "- 只使用 H2 中 `usable_for_adaptation` 的 bounded constraints。",
        "- 不使用 raw skeleton path，不使用 unordered skeleton segments，不做最近点吸附。",
        "- 保留 MakeMeAHanzi stroke_count、stroke order、stroke breaks 和点顺序。",
        "- 不生成正式 trajectory.csv，不生成 execution/workspace/robot 文件，不接 run_demo 默认流程。",
        "",
        f"- output_dir: `{output_dir}`",
        "",
        "## Results",
        "",
        "| char | style | median aspect | target aspect | cons aspect | balanced aspect | median lower | target lower | cons lower | balanced lower | max shift cons | max shift balanced | path ratio cons | path ratio balanced | compare |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['bbox_aspect_median']} | {row['bbox_aspect_target']} | "
            f"{row['bbox_aspect_conservative']} | {row['bbox_aspect_balanced']} | "
            f"{row['lower_half_width_median']} | {row['lower_half_width_target']} | "
            f"{row['lower_half_width_conservative']} | {row['lower_half_width_balanced']} | "
            f"{row['max_point_shift_px_conservative']} | {row['max_point_shift_px_balanced']} | "
            f"{row['path_length_ratio_conservative']} | {row['path_length_ratio_balanced']} | `{row['compare_png']}` |"
        )
    lines.extend(
        [
            "",
            "## Questions for manual visual audit",
            "",
            "- H1-lite balanced 是否自然？",
            "- conservative 是否太弱？",
            "- 山/lishu 是否有更稳定的隶书宽底感，同时没有触达过高 shift cap？",
            "- 人/kaishu 是否仍可写、没有过度变形？",
            "",
            "## Interpretation",
            "",
            "If H1-lite improves bbox/lower-half/spread metrics without large point shifts, it supports using H2 constraints as safer inputs for future B adaptation than raw skeleton pulling. Visual audit still decides whether the result is worth expanding.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(index_path: Path, output_dir: Path, rows: Sequence[dict[str, Any]]) -> None:
    lines = [
        "# H1-lite constraint-bounded adaptation index",
        "",
        f"- source_output_dir: `{output_dir}`",
        "- Status: trial-only, not used by default.",
        "- Boundary: no raw skeleton path, no nearest-point pulling, no formal trajectory.csv, no execution/workspace/robot outputs.",
        "",
        "| char | style | compare | summary |",
        "|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['char']} | {row['style']} | `{row['compare_png']}` | `{row['summary_json']}` |")
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _process_sample(char: str, style: str, output_dir: Path, constraints_json: Path, image_size: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    char_id = _char_id(char)
    sample_dir = output_dir / f"{char_id}_{style}"
    sample_dir.mkdir(parents=True, exist_ok=True)
    median = _load_median(char, image_size=image_size)
    constraints = load_usable_constraints(constraints_json, char_id, style)
    conservative = adapt_with_h2_constraints(median, constraints, "conservative", image_size=image_size)
    balanced = adapt_with_h2_constraints(median, constraints, "balanced", image_size=image_size)
    conservative_points = _write_trial_csv(sample_dir / "h1_lite_conservative.csv", conservative, "conservative")
    balanced_points = _write_trial_csv(sample_dir / "h1_lite_balanced.csv", balanced, "balanced")
    if conservative_points != balanced_points:
        raise RuntimeError("H1-lite point counts diverged between variants")

    median_metrics = _variant_metrics(median, median)
    cons_metrics = _variant_metrics(median, conservative)
    balanced_metrics = _variant_metrics(median, balanced)
    target_lower_abs = float(constraints.get("lower_half_width_ratio", median_metrics["lower_half_width_ratio"])) * max(_bbox(_flatten(median))["width"], 0.0)
    compare_png = sample_dir / "h1_lite_compare.png"
    _write_compare(compare_png, char, style, median, conservative, balanced, _h2_reference_figure(char_id, style))

    summary = {
        "status": "trial_not_used_by_default",
        "source": "constraint_bounded_adaptation_h1_lite_trial",
        "char": char,
        "char_id": char_id,
        "style": style,
        "stroke_count": len(median),
        "point_count": conservative_points,
        "used_constraints": sorted(constraints),
        "bbox_aspect_median": median_metrics["bbox_aspect"],
        "bbox_aspect_target": round(float(constraints.get("bbox_aspect", median_metrics["bbox_aspect"])), 6),
        "bbox_aspect_conservative": cons_metrics["bbox_aspect"],
        "bbox_aspect_balanced": balanced_metrics["bbox_aspect"],
        "lower_half_width_median": median_metrics["lower_half_width"],
        "lower_half_width_target": round(target_lower_abs, 6),
        "lower_half_width_conservative": cons_metrics["lower_half_width"],
        "lower_half_width_balanced": balanced_metrics["lower_half_width"],
        "left_right_spread_median": median_metrics["left_right_spread"],
        "left_right_spread_target": round(float(constraints.get("left_right_spread", median_metrics["left_right_spread"])), 6),
        "left_right_spread_conservative": cons_metrics["left_right_spread"],
        "left_right_spread_balanced": balanced_metrics["left_right_spread"],
        "max_point_shift_px": {
            "conservative": cons_metrics["max_point_shift_px"],
            "balanced": balanced_metrics["max_point_shift_px"],
        },
        "mean_point_shift_px": {
            "conservative": cons_metrics["mean_point_shift_px"],
            "balanced": balanced_metrics["mean_point_shift_px"],
        },
        "path_length_ratio": {
            "conservative": cons_metrics["path_length_ratio"],
            "balanced": balanced_metrics["path_length_ratio"],
        },
        "stroke_count_preserved": len(conservative) == len(median) and len(balanced) == len(median),
        "warning": "",
        "recommended_for_visual_followup": True,
    }
    summary_json = sample_dir / "h1_lite_summary.json"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    row = {
        "char": char,
        "char_id": char_id,
        "style": style,
        "sample_dir": str(sample_dir),
        "summary_json": str(summary_json),
        "compare_png": str(compare_png),
        "stroke_count": summary["stroke_count"],
        "point_count": summary["point_count"],
        "used_constraints": ";".join(summary["used_constraints"]),
        "bbox_aspect_median": summary["bbox_aspect_median"],
        "bbox_aspect_target": summary["bbox_aspect_target"],
        "bbox_aspect_conservative": summary["bbox_aspect_conservative"],
        "bbox_aspect_balanced": summary["bbox_aspect_balanced"],
        "lower_half_width_median": summary["lower_half_width_median"],
        "lower_half_width_target": summary["lower_half_width_target"],
        "lower_half_width_conservative": summary["lower_half_width_conservative"],
        "lower_half_width_balanced": summary["lower_half_width_balanced"],
        "left_right_spread_median": summary["left_right_spread_median"],
        "left_right_spread_target": summary["left_right_spread_target"],
        "left_right_spread_conservative": summary["left_right_spread_conservative"],
        "left_right_spread_balanced": summary["left_right_spread_balanced"],
        "max_point_shift_px_conservative": summary["max_point_shift_px"]["conservative"],
        "max_point_shift_px_balanced": summary["max_point_shift_px"]["balanced"],
        "mean_point_shift_px_conservative": summary["mean_point_shift_px"]["conservative"],
        "mean_point_shift_px_balanced": summary["mean_point_shift_px"]["balanced"],
        "path_length_ratio_conservative": summary["path_length_ratio"]["conservative"],
        "path_length_ratio_balanced": summary["path_length_ratio"]["balanced"],
        "stroke_count_preserved": summary["stroke_count_preserved"],
        "warning": "",
        "recommended_for_visual_followup": True,
    }
    manifest = [
        {
            "char": char,
            "char_id": char_id,
            "style": style,
            "variant": "conservative",
            "trial_csv": str(sample_dir / "h1_lite_conservative.csv"),
            "compare_png": str(compare_png),
            "summary_json": str(summary_json),
            "warning": "",
        },
        {
            "char": char,
            "char_id": char_id,
            "style": style,
            "variant": "balanced",
            "trial_csv": str(sample_dir / "h1_lite_balanced.csv"),
            "compare_png": str(compare_png),
            "summary_json": str(summary_json),
            "warning": "",
        },
    ]
    return row, manifest


def run_constraint_bounded_adaptation_h1_lite(
    output_dir: Path | str | None = None,
    constraints_json_path: Path | str = DEFAULT_H2_CONSTRAINTS_JSON,
    sample_specs: Sequence[tuple[str, str]] = DEFAULT_SAMPLE_SPECS,
    image_size: int = 256,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"constraint_bounded_adaptation_h1_lite_{timestamp}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    constraints_json = Path(constraints_json_path)

    rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for char, style in sample_specs:
        row, manifest = _process_sample(char, style, output_dir, constraints_json, image_size=image_size)
        rows.append(row)
        manifest_rows.extend(manifest)

    summary_csv = output_dir / "h1_lite_summary.csv"
    report_md = output_dir / "h1_lite_report.md"
    manifest_csv = output_dir / "h1_lite_manifest.csv"
    _write_csv(summary_csv, rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, output_dir, rows)

    paper_index = ""
    if copy_to_paper:
        DEFAULT_PAPER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "constraint_bounded_adaptation_h1_lite_summary.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "constraint_bounded_adaptation_h1_lite_report.md")
        index_path = DEFAULT_PAPER_DIR / "constraint_bounded_adaptation_h1_lite_index.md"
        _write_paper_index(index_path, output_dir, rows)
        paper_index = str(index_path)

    return {
        "output_dir": str(output_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "paper_index": paper_index,
        "rows": rows,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--constraints-json", type=Path, default=DEFAULT_H2_CONSTRAINTS_JSON)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_constraint_bounded_adaptation_h1_lite(
        output_dir=args.out_dir,
        constraints_json_path=args.constraints_json,
        image_size=args.image_size,
        copy_to_paper=not args.no_copy_to_paper,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
