"""Median-to-font adaptation v2 prototype.

This diagnostic layer keeps MakeMeAHanzi median stroke order, then combines:
1. conservative global bbox scale/translation toward the font mask bbox, and
2. local stroke-anchor attraction toward the cleaned font skeleton.

It is not wired into run_demo.py or any default pipeline, and it does not write a
formal trajectory.csv or robot/execution/workspace outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from font_outline_basis_feasibility import (
    DEFAULT_GRAPHICS,
    first_existing_font,
    render_char_with_font,
    skeletonize_font_mask,
)
from font_skeleton_cleanup_prototype import cleanup_skeleton
from knowledge import MakeMeAHanziKnowledge
from median_font_alignment_prototype import (
    _nearest_reference,
    _reference_points,
    adapt_strokes_to_reference,
)
from trajectory_tools import normalize_medians, stroke_path_length


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_STYLE_SOURCES = EXP_DIR / "configs" / "style_sources.json"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
DEFAULT_SAMPLE_SPECS = [
    ("\u4eba", "kaishu"),  # 人
    ("\u5c71", "lishu"),  # 山
]
DEFAULT_VARIANTS = {
    "conservative": {"bbox_alpha": 0.25, "anchor_alpha": 0.25},
    "stronger": {"bbox_alpha": 0.40, "anchor_alpha": 0.35},
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
    "projection_distance_before",
    "projection_distance_v1_alpha025",
    "projection_distance_v2_conservative",
    "projection_distance_v2_stronger",
    "bbox_aspect_median",
    "bbox_aspect_font",
    "bbox_aspect_v1",
    "bbox_aspect_v2_conservative",
    "bbox_aspect_v2_stronger",
    "aspect_gap_before",
    "aspect_gap_v1",
    "aspect_gap_v2_conservative",
    "aspect_gap_v2_stronger",
    "max_point_shift_px_conservative",
    "max_point_shift_px_stronger",
    "mean_point_shift_px_conservative",
    "mean_point_shift_px_stronger",
    "path_length_ratio_conservative",
    "path_length_ratio_stronger",
    "warning",
    "recommended_for_visual_followup",
]
MANIFEST_FIELDS = [
    "char",
    "char_id",
    "style",
    "sample_dir",
    "variant",
    "trial_csv",
    "compare_png",
    "warning",
]


def _char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else ""


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _bbox_from_points(points: np.ndarray) -> dict[str, float]:
    arr = np.asarray(points, dtype=float)
    if len(arr) == 0:
        return {"y_min": 0.0, "y_max": 0.0, "x_min": 0.0, "x_max": 0.0, "height": 0.0, "width": 0.0}
    y_min, x_min = np.min(arr, axis=0)
    y_max, x_max = np.max(arr, axis=0)
    return {
        "y_min": float(y_min),
        "y_max": float(y_max),
        "x_min": float(x_min),
        "x_max": float(x_max),
        "height": float(y_max - y_min),
        "width": float(x_max - x_min),
    }


def _bbox_from_mask(mask: np.ndarray) -> dict[str, float]:
    grid = np.asarray(mask, dtype=bool)
    if not np.any(grid):
        return {"y_min": 0.0, "y_max": 0.0, "x_min": 0.0, "x_max": 0.0, "height": 0.0, "width": 0.0}
    ys, xs = np.nonzero(grid)
    return {
        "y_min": float(ys.min()),
        "y_max": float(ys.max()),
        "x_min": float(xs.min()),
        "x_max": float(xs.max()),
        "height": float(ys.max() - ys.min()),
        "width": float(xs.max() - xs.min()),
    }


def _complete_bbox(bbox: dict[str, float]) -> dict[str, float]:
    y_min = float(bbox.get("y_min", 0.0))
    y_max = float(bbox.get("y_max", y_min))
    x_min = float(bbox.get("x_min", 0.0))
    x_max = float(bbox.get("x_max", x_min))
    out = dict(bbox)
    out["y_min"] = y_min
    out["y_max"] = y_max
    out["x_min"] = x_min
    out["x_max"] = x_max
    out["height"] = float(out.get("height", y_max - y_min))
    out["width"] = float(out.get("width", x_max - x_min))
    return out


def bbox_aspect(strokes: Sequence[np.ndarray]) -> float:
    bbox = _bbox_from_points(_flatten(strokes))
    return round(bbox["width"] / bbox["height"] if bbox["height"] > 1e-9 else 0.0, 6)


def _bbox_aspect_from_bbox(bbox: dict[str, float]) -> float:
    bbox = _complete_bbox(bbox)
    return round(bbox["width"] / bbox["height"] if bbox["height"] > 1e-9 else 0.0, 6)


def _limit_scale(value: float, max_scale_delta: float) -> float:
    return max(1.0 - max_scale_delta, min(1.0 + max_scale_delta, value))


def apply_global_bbox_alignment(
    strokes: Sequence[np.ndarray],
    target_bbox: dict[str, float],
    bbox_alpha: float,
    max_scale_delta: float = 0.35,
) -> list[np.ndarray]:
    """Scale/translate median strokes partway toward target bbox, no rotation."""

    target_bbox = _complete_bbox(target_bbox)
    source_bbox = _bbox_from_points(_flatten(strokes))
    if source_bbox["height"] <= 1e-9 or source_bbox["width"] <= 1e-9:
        return [np.asarray(stroke, dtype=float).copy() for stroke in strokes]
    src_cy = 0.5 * (source_bbox["y_min"] + source_bbox["y_max"])
    src_cx = 0.5 * (source_bbox["x_min"] + source_bbox["x_max"])
    tgt_cy = 0.5 * (target_bbox["y_min"] + target_bbox["y_max"])
    tgt_cx = 0.5 * (target_bbox["x_min"] + target_bbox["x_max"])
    raw_sy = target_bbox["height"] / max(source_bbox["height"], 1e-9)
    raw_sx = target_bbox["width"] / max(source_bbox["width"], 1e-9)
    sy = 1.0 + float(bbox_alpha) * (_limit_scale(raw_sy, max_scale_delta) - 1.0)
    sx = 1.0 + float(bbox_alpha) * (_limit_scale(raw_sx, max_scale_delta) - 1.0)
    dy = float(bbox_alpha) * (tgt_cy - src_cy)
    dx = float(bbox_alpha) * (tgt_cx - src_cx)
    out: list[np.ndarray] = []
    for stroke in strokes:
        pts = np.asarray(stroke, dtype=float).copy()
        pts[:, 0] = src_cy + (pts[:, 0] - src_cy) * sy + dy
        pts[:, 1] = src_cx + (pts[:, 1] - src_cx) * sx + dx
        out.append(pts)
    return out


def _anchor_indices(length: int) -> list[int]:
    if length <= 0:
        return []
    candidates = {0, length - 1, length // 2, length // 4, (3 * length) // 4}
    return sorted(idx for idx in candidates if 0 <= idx < length)


def _smooth_anchor_delta(
    stroke: np.ndarray,
    anchor_deltas: dict[int, np.ndarray],
    radius: float,
) -> np.ndarray:
    pts = np.asarray(stroke, dtype=float)
    if not anchor_deltas:
        return np.zeros_like(pts)
    out = np.zeros_like(pts)
    for point_idx in range(len(pts)):
        weighted = np.zeros((2,), dtype=float)
        total = 0.0
        for anchor_idx, delta in anchor_deltas.items():
            dist = abs(point_idx - anchor_idx)
            weight = math.exp(-(dist * dist) / (2.0 * radius * radius))
            weighted += weight * delta
            total += weight
        if total > 1e-12:
            out[point_idx] = weighted / total
    return out


def _cap_relative_to_original(
    original: Sequence[np.ndarray],
    candidate: Sequence[np.ndarray],
    max_shift_px: float,
) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    for src, cand in zip(original, candidate):
        src_arr = np.asarray(src, dtype=float)
        cand_arr = np.asarray(cand, dtype=float)
        delta = cand_arr - src_arr
        lengths = np.linalg.norm(delta, axis=1)
        limited = cand_arr.copy()
        for idx, length in enumerate(lengths):
            if length > max_shift_px:
                limited[idx] = src_arr[idx] + delta[idx] * (max_shift_px / max(length, 1e-9))
        out.append(limited)
    return out


def apply_stroke_anchor_alignment(
    strokes: Sequence[np.ndarray],
    reference_points: np.ndarray,
    anchor_alpha: float,
    max_anchor_distance_px: float = 60.0,
    local_radius_ratio: float = 0.35,
) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    ref = np.asarray(reference_points, dtype=float)
    for stroke in strokes:
        pts = np.asarray(stroke, dtype=float)
        anchor_deltas: dict[int, np.ndarray] = {}
        for anchor_idx in _anchor_indices(len(pts)):
            point = pts[anchor_idx : anchor_idx + 1]
            nearest, dist = _nearest_reference(point, ref)
            if len(dist) and math.isfinite(float(dist[0])) and dist[0] <= max_anchor_distance_px:
                anchor_deltas[anchor_idx] = (nearest[0] - point[0]) * float(anchor_alpha)
        radius = max(1.0, len(pts) * local_radius_ratio)
        out.append(pts + _smooth_anchor_delta(pts, anchor_deltas, radius))
    return out


def _projection_distance(strokes: Sequence[np.ndarray], reference: np.ndarray) -> float:
    pts = _flatten(strokes)
    _, distances = _nearest_reference(pts, reference)
    finite = distances[np.isfinite(distances)]
    return round(float(np.mean(finite)) if len(finite) else 0.0, 6)


def _path_length(strokes: Sequence[np.ndarray]) -> float:
    return float(sum(stroke_path_length(np.asarray(stroke, dtype=float)) for stroke in strokes))


def _shift_stats(original: Sequence[np.ndarray], candidate: Sequence[np.ndarray]) -> dict[str, float]:
    shifts: list[float] = []
    for src, cand in zip(original, candidate):
        delta = np.asarray(cand, dtype=float) - np.asarray(src, dtype=float)
        shifts.extend(float(v) for v in np.linalg.norm(delta, axis=1))
    return {
        "max_point_shift_px": round(max(shifts) if shifts else 0.0, 6),
        "mean_point_shift_px": round(float(np.mean(shifts)) if shifts else 0.0, 6),
    }


def adapt_v2(
    median_strokes: Sequence[np.ndarray],
    target_bbox: dict[str, float],
    reference_points: np.ndarray,
    bbox_alpha: float,
    anchor_alpha: float,
    max_point_shift_px: float = 18.0,
) -> list[np.ndarray]:
    bbox_adapted = apply_global_bbox_alignment(median_strokes, target_bbox, bbox_alpha=bbox_alpha)
    anchor_adapted = apply_stroke_anchor_alignment(
        bbox_adapted,
        reference_points,
        anchor_alpha=anchor_alpha,
    )
    return _cap_relative_to_original(median_strokes, anchor_adapted, max_point_shift_px)


def _write_trial_csv(path: Path, strokes: Sequence[np.ndarray], variant: str) -> tuple[int, int]:
    rows: list[dict[str, Any]] = []
    point_count = 0
    break_count = 0
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
                    "source": "median_font_adaptation_v2_trial",
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
                "source": "median_font_adaptation_v2_trial",
            }
        )
        break_count += 1
    _write_csv(path, rows, TRIAL_FIELDS)
    return point_count, break_count


def _draw_strokes(ax: Any, strokes: Sequence[np.ndarray], title: str, color: str, width: float = 1.6) -> None:
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.invert_yaxis()
    for idx, stroke in enumerate(strokes, start=1):
        pts = np.asarray(stroke, dtype=float)
        if len(pts) < 2:
            continue
        ax.plot(pts[:, 1], pts[:, 0], color=color, linewidth=width)
        ax.scatter(pts[0, 1], pts[0, 0], s=8, color=color)
        mid = pts[len(pts) // 2]
        ax.text(mid[1], mid[0], str(idx), fontsize=7, color="#111111")


def _write_compare_figure(
    char: str,
    style: str,
    median_strokes: Sequence[np.ndarray],
    mask: np.ndarray,
    skeleton: np.ndarray,
    v1_strokes: Sequence[np.ndarray],
    v2_by_variant: dict[str, Sequence[np.ndarray]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 5, figsize=(15.4, 3.4), dpi=150)
    _draw_strokes(axes[0], median_strokes, "original median", "#333333")
    axes[1].set_title("font mask + skeleton", fontsize=8)
    axes[1].imshow(np.where(mask, 0.88, 1.0), cmap="gray", vmin=0, vmax=1)
    ys, xs = np.nonzero(skeleton)
    axes[1].scatter(xs, ys, s=0.7, color="#1f77b4", alpha=0.9)
    axes[1].set_aspect("equal")
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    _draw_strokes(axes[2], v1_strokes, "v1 alpha-only", "#9467bd")
    _draw_strokes(axes[3], v2_by_variant.get("conservative", []), "v2 conservative", "#d62728")
    _draw_strokes(axes[4], v2_by_variant.get("stronger", []), "v2 stronger", "#2ca02c")
    for ax in axes:
        ax.set_xlim(0, mask.shape[1])
        ax.set_ylim(mask.shape[0], 0)
    fig.suptitle(f"{_char_id(char)} / {style} median-font adaptation v2", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(path)
    plt.close(fig)


def _style_font(style_sources_path: Path, style: str) -> Path | None:
    sources = json.loads(style_sources_path.read_text(encoding="utf-8"))
    return first_existing_font(sources, style, style_sources_path.parent)


def _prepare_sample(char: str, style: str, image_size: int, skeleton_method: str, style_sources_path: Path) -> tuple[list[np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    glyph = MakeMeAHanziKnowledge(DEFAULT_GRAPHICS).get_glyph(char)
    median_strokes = list(normalize_medians(glyph.medians, image_size=image_size))
    font_path = _style_font(style_sources_path, style)
    if font_path is None:
        mask = np.zeros((image_size, image_size), dtype=bool)
        clean_skeleton = np.zeros_like(mask)
    else:
        mask = render_char_with_font(char, font_path, image_size=image_size)
        skeleton_result = skeletonize_font_mask(mask, method=skeleton_method)
        clean_skeleton, _ = cleanup_skeleton(
            skeleton_result.skeleton,
            min_component_pixels=12,
            spur_prune_length=6,
            endpoint_merge_distance=3,
        )
    reference = _reference_points(clean_skeleton, mask)
    return median_strokes, mask, clean_skeleton, reference


def _aspect_gap(aspect: float, font_aspect: float) -> float:
    return round(abs(float(aspect) - float(font_aspect)), 6)


def _variant_metrics(original: Sequence[np.ndarray], variant: Sequence[np.ndarray], reference: np.ndarray, font_aspect: float) -> dict[str, float]:
    shifts = _shift_stats(original, variant)
    original_len = _path_length(original)
    variant_len = _path_length(variant)
    aspect = bbox_aspect(variant)
    return {
        "projection_distance": _projection_distance(variant, reference),
        "bbox_aspect": aspect,
        "aspect_gap": _aspect_gap(aspect, font_aspect),
        "max_point_shift_px": shifts["max_point_shift_px"],
        "mean_point_shift_px": shifts["mean_point_shift_px"],
        "path_length_ratio": round(variant_len / original_len if original_len > 1e-9 else 0.0, 6),
    }


def _write_report(path: Path, output_dir: Path, rows: Sequence[dict[str, Any]]) -> None:
    lines = [
        "# Median-font adaptation v2 prototype",
        "",
        "This is a diagnostic-only B-route prototype using global bbox alignment plus stroke-level anchor alignment.",
        "",
        "## Boundary",
        "",
        "- 保留 MakeMeAHanzi stroke order 和 stroke_count。",
        "- 不恢复真实笔顺，不跨 stroke 合并，不重排笔顺。",
        "- 不生成正式 `trajectory.csv`，只输出 `adapted_v2_*.csv`。",
        "- 不接默认 pipeline，不接 execution/workspace/CoppeliaSim/AUBO/SDK。",
        "- projection distance 不能作为唯一标准，必须同时看 aspect gap 和人工图像效果。",
        "",
        "## Output",
        "",
        f"`{output_dir}`",
        "",
        "## Results",
        "",
        "| char | style | before_dist | v1_dist | v2_cons_dist | v2_strong_dist | aspect_gap_before | aspect_gap_v1 | aspect_gap_v2_cons | aspect_gap_v2_strong | warning | compare |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {char} | {style} | {projection_distance_before} | {projection_distance_v1_alpha025} | "
            "{projection_distance_v2_conservative} | {projection_distance_v2_stronger} | "
            "{aspect_gap_before} | {aspect_gap_v1} | {aspect_gap_v2_conservative} | {aspect_gap_v2_stronger} | "
            "{warning} | `{compare_png}` |".format(**row)
        )
    lines.extend(
        [
            "",
            "## Manual visual questions",
            "",
            "- v2 是否比 v1 更接近 font aspect / font skeleton？",
            "- 人/kaishu 是否没有被过度扭曲？",
            "- 山/lishu 是否比 v1 更有隶书宽底/结构特征？",
            "- conservative 是否比 stronger 更适合作为下一阶段默认候选？",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(paper_dir: Path, output_dir: Path, summary_csv: Path, report_md: Path, rows: Sequence[dict[str, Any]]) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    index = paper_dir / "median_font_adaptation_v2_index.md"
    lines = [
        "# Median-font adaptation v2 prototype index",
        "",
        f"- Output directory: `{output_dir}`",
        f"- Summary: `{summary_csv}`",
        f"- Report: `{report_md}`",
        "",
        "| char | style | v1_dist | v2_conservative_dist | v2_stronger_dist | compare |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['projection_distance_v1_alpha025']} | "
            f"{row['projection_distance_v2_conservative']} | {row['projection_distance_v2_stronger']} | "
            f"`{row['compare_png']}` |"
        )
    lines.extend(
        [
            "",
            "Boundary: diagnostic only; no formal trajectory.csv, no default pipeline integration, no robot interface.",
        ]
    )
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index


def _process_sample(
    char: str,
    style: str,
    output_dir: Path,
    style_sources_path: Path,
    image_size: int,
    skeleton_method: str,
    max_point_shift_px: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sample_dir = output_dir / f"{_char_id(char)}_{style}"
    sample_dir.mkdir(parents=True, exist_ok=True)
    median_strokes, mask, clean_skeleton, reference = _prepare_sample(
        char,
        style,
        image_size=image_size,
        skeleton_method=skeleton_method,
        style_sources_path=style_sources_path,
    )
    target_bbox = _bbox_from_mask(mask)
    font_aspect = _bbox_aspect_from_bbox(target_bbox)
    median_aspect = bbox_aspect(median_strokes)
    projection_before = _projection_distance(median_strokes, reference)
    v1_strokes, _ = adapt_strokes_to_reference(
        median_strokes,
        reference,
        alpha=0.25,
        max_shift_px=15.0,
        max_snap_distance_px=45.0,
    )
    v1_metrics = _variant_metrics(median_strokes, v1_strokes, reference, font_aspect)

    v2_by_variant: dict[str, list[np.ndarray]] = {}
    metrics_by_variant: dict[str, dict[str, float]] = {}
    manifest_rows: list[dict[str, Any]] = []
    point_count = int(sum(len(stroke) for stroke in median_strokes))
    for variant, params in DEFAULT_VARIANTS.items():
        adapted = adapt_v2(
            median_strokes,
            target_bbox,
            reference,
            bbox_alpha=float(params["bbox_alpha"]),
            anchor_alpha=float(params["anchor_alpha"]),
            max_point_shift_px=max_point_shift_px,
        )
        v2_by_variant[variant] = adapted
        metrics_by_variant[variant] = _variant_metrics(median_strokes, adapted, reference, font_aspect)
        trial_csv = sample_dir / f"adapted_v2_{variant}.csv"
        _write_trial_csv(trial_csv, adapted, variant)
        manifest_rows.append(
            {
                "char": char,
                "char_id": _char_id(char),
                "style": style,
                "sample_dir": str(sample_dir),
                "variant": variant,
                "trial_csv": str(trial_csv),
                "compare_png": str(sample_dir / "median_font_adaptation_v2_compare.png"),
                "warning": "",
            }
        )

    compare_png = sample_dir / "median_font_adaptation_v2_compare.png"
    _write_compare_figure(char, style, median_strokes, mask, clean_skeleton, v1_strokes, v2_by_variant, compare_png)

    aspect_gap_before = _aspect_gap(median_aspect, font_aspect)
    summary = {
        "char": char,
        "char_id": _char_id(char),
        "style": style,
        "stroke_count": len(median_strokes),
        "adapted_stroke_count": len(median_strokes),
        "point_count": point_count,
        "projection_distance_before": projection_before,
        "projection_distance_v1_alpha025": v1_metrics["projection_distance"],
        "projection_distance_v2_conservative": metrics_by_variant["conservative"]["projection_distance"],
        "projection_distance_v2_stronger": metrics_by_variant["stronger"]["projection_distance"],
        "bbox_aspect_median": median_aspect,
        "bbox_aspect_font": font_aspect,
        "bbox_aspect_v1": v1_metrics["bbox_aspect"],
        "bbox_aspect_v2_conservative": metrics_by_variant["conservative"]["bbox_aspect"],
        "bbox_aspect_v2_stronger": metrics_by_variant["stronger"]["bbox_aspect"],
        "aspect_gap_before": aspect_gap_before,
        "aspect_gap_v1": v1_metrics["aspect_gap"],
        "aspect_gap_v2_conservative": metrics_by_variant["conservative"]["aspect_gap"],
        "aspect_gap_v2_stronger": metrics_by_variant["stronger"]["aspect_gap"],
        "max_point_shift_px": {
            "conservative": metrics_by_variant["conservative"]["max_point_shift_px"],
            "stronger": metrics_by_variant["stronger"]["max_point_shift_px"],
        },
        "mean_point_shift_px": {
            "conservative": metrics_by_variant["conservative"]["mean_point_shift_px"],
            "stronger": metrics_by_variant["stronger"]["mean_point_shift_px"],
        },
        "path_length_ratio": {
            "conservative": metrics_by_variant["conservative"]["path_length_ratio"],
            "stronger": metrics_by_variant["stronger"]["path_length_ratio"],
        },
        "warning": "",
        "recommended_for_visual_followup": True,
        "scope": "diagnostic median-font adaptation v2 only; not formal trajectory; no robot",
    }
    summary_json = sample_dir / "median_font_adaptation_v2_summary.json"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    row = {
        "char": char,
        "char_id": _char_id(char),
        "style": style,
        "sample_dir": str(sample_dir),
        "summary_json": str(summary_json),
        "compare_png": str(compare_png),
        "stroke_count": len(median_strokes),
        "point_count": point_count,
        "projection_distance_before": projection_before,
        "projection_distance_v1_alpha025": summary["projection_distance_v1_alpha025"],
        "projection_distance_v2_conservative": summary["projection_distance_v2_conservative"],
        "projection_distance_v2_stronger": summary["projection_distance_v2_stronger"],
        "bbox_aspect_median": median_aspect,
        "bbox_aspect_font": font_aspect,
        "bbox_aspect_v1": summary["bbox_aspect_v1"],
        "bbox_aspect_v2_conservative": summary["bbox_aspect_v2_conservative"],
        "bbox_aspect_v2_stronger": summary["bbox_aspect_v2_stronger"],
        "aspect_gap_before": summary["aspect_gap_before"],
        "aspect_gap_v1": summary["aspect_gap_v1"],
        "aspect_gap_v2_conservative": summary["aspect_gap_v2_conservative"],
        "aspect_gap_v2_stronger": summary["aspect_gap_v2_stronger"],
        "max_point_shift_px_conservative": summary["max_point_shift_px"]["conservative"],
        "max_point_shift_px_stronger": summary["max_point_shift_px"]["stronger"],
        "mean_point_shift_px_conservative": summary["mean_point_shift_px"]["conservative"],
        "mean_point_shift_px_stronger": summary["mean_point_shift_px"]["stronger"],
        "path_length_ratio_conservative": summary["path_length_ratio"]["conservative"],
        "path_length_ratio_stronger": summary["path_length_ratio"]["stronger"],
        "warning": "",
        "recommended_for_visual_followup": True,
    }
    return row, manifest_rows


def run_median_font_adaptation_v2(
    output_dir: Path | str | None = None,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    sample_specs: Sequence[tuple[str, str]] = DEFAULT_SAMPLE_SPECS,
    image_size: int = 256,
    skeleton_method: str = "auto",
    max_point_shift_px: float = 18.0,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"median_font_adaptation_v2_{timestamp}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    style_sources_path = Path(style_sources_path)

    rows: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    for char, style in sample_specs:
        row, sample_manifest = _process_sample(
            char,
            style,
            output_dir=output_dir,
            style_sources_path=style_sources_path,
            image_size=image_size,
            skeleton_method=skeleton_method,
            max_point_shift_px=max_point_shift_px,
        )
        rows.append(row)
        manifest.extend(sample_manifest)

    summary_csv = output_dir / "median_font_adaptation_v2_summary.csv"
    manifest_csv = output_dir / "median_font_adaptation_v2_manifest.csv"
    report_md = output_dir / "median_font_adaptation_v2_report.md"
    _write_csv(summary_csv, rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest, MANIFEST_FIELDS)
    _write_report(report_md, output_dir, rows)

    paper_index = ""
    if copy_to_paper:
        index = _write_paper_index(DEFAULT_PAPER_DIR, output_dir, summary_csv, report_md, rows)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "median_font_adaptation_v2_summary.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "median_font_adaptation_v2_report.md")
        paper_index = str(index)

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
    parser.add_argument("--style-sources", type=Path, default=DEFAULT_STYLE_SOURCES)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--skeleton-method", choices=["auto", "skimage", "opencv", "ridge"], default="auto")
    parser.add_argument("--max-point-shift-px", type=float, default=18.0)
    parser.add_argument("--no-paper-copy", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_median_font_adaptation_v2(
        output_dir=args.out_dir,
        style_sources_path=args.style_sources,
        image_size=args.image_size,
        skeleton_method=args.skeleton_method,
        max_point_shift_px=args.max_point_shift_px,
        copy_to_paper=not args.no_paper_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
