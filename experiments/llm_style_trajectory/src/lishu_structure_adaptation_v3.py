"""Lishu structure-constrained median-font adaptation v3 prototype.

This diagnostic layer only handles 山 / lishu. It keeps MakeMeAHanzi stroke
order and stroke count, uses v2 stronger as a reference, then adds explicit
structure-level constraints for wider lower support and more open side strokes.

It is not wired into run_demo.py or any default pipeline, and it does not write
formal trajectory.csv, execution, workspace, CoppeliaSim, AUBO, or SDK outputs.
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

from median_font_adaptation_v2 import (
    DEFAULT_OUTPUT,
    DEFAULT_PAPER_DIR,
    DEFAULT_STYLE_SOURCES,
    _aspect_gap,
    _bbox_aspect_from_bbox,
    _bbox_from_mask,
    _bbox_from_points,
    _char_id,
    _flatten,
    _path_length,
    _prepare_sample,
    _projection_distance,
    _shift_stats,
    _write_csv,
    adapt_v2,
    bbox_aspect,
)


CHAR = "\u5c71"  # 山
STYLE = "lishu"

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
    "projection_distance_v2_stronger",
    "projection_distance_v3_conservative",
    "projection_distance_v3_stronger",
    "bbox_aspect_median",
    "bbox_aspect_font",
    "bbox_aspect_v2_stronger",
    "bbox_aspect_v3_conservative",
    "bbox_aspect_v3_stronger",
    "lower_half_width_median",
    "lower_half_width_font",
    "lower_half_width_v2_stronger",
    "lower_half_width_v3_conservative",
    "lower_half_width_v3_stronger",
    "max_point_shift_px_conservative",
    "max_point_shift_px_stronger",
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

V3_VARIANTS = {
    "conservative": {"spread_alpha": 0.28, "bottom_alpha": 0.18, "side_alpha": 0.22},
    "stronger": {"spread_alpha": 0.45, "bottom_alpha": 0.28, "side_alpha": 0.34},
}


def _mask_points(mask: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(np.asarray(mask, dtype=bool))
    if len(ys) == 0:
        return np.empty((0, 2), dtype=float)
    return np.column_stack([ys.astype(float), xs.astype(float)])


def _lower_half_points(points: np.ndarray) -> np.ndarray:
    pts = np.asarray(points, dtype=float)
    if len(pts) == 0:
        return pts.reshape(0, 2)
    bbox = _bbox_from_points(pts)
    threshold = bbox["y_min"] + 0.50 * max(bbox["height"], 1e-9)
    return pts[pts[:, 0] >= threshold]


def lower_half_width(strokes: Sequence[np.ndarray]) -> float:
    lower = _lower_half_points(_flatten(strokes))
    if len(lower) == 0:
        return 0.0
    return round(float(np.max(lower[:, 1]) - np.min(lower[:, 1])), 6)


def _lower_half_width_from_mask(mask: np.ndarray) -> float:
    lower = _lower_half_points(_mask_points(mask))
    if len(lower) == 0:
        return 0.0
    return round(float(np.max(lower[:, 1]) - np.min(lower[:, 1])), 6)


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


def structure_spread_points(
    strokes: Sequence[np.ndarray],
    target_left_x: float,
    target_right_x: float,
    target_bottom_y: float,
    spread_alpha: float,
    bottom_alpha: float,
    max_shift_px: float = 22.0,
    side_alpha: float | None = None,
) -> list[np.ndarray]:
    """Open lower-half and side points toward conservative lishu structure hints."""

    side_alpha = spread_alpha if side_alpha is None else side_alpha
    flat = _flatten(strokes)
    bbox = _bbox_from_points(flat)
    center_x = 0.5 * (bbox["x_min"] + bbox["x_max"])
    half_width = max(0.5 * bbox["width"], 1e-9)
    y_mid = bbox["y_min"] + 0.50 * max(bbox["height"], 1e-9)
    lower = _lower_half_points(flat)
    if len(lower):
        target_left_x = min(float(target_left_x), float(np.min(lower[:, 1])))
        target_right_x = max(float(target_right_x), float(np.max(lower[:, 1])))
    out: list[np.ndarray] = []
    for stroke in strokes:
        pts = np.asarray(stroke, dtype=float).copy()
        for idx, (y, x) in enumerate(pts):
            lower_weight = max(0.0, min(1.0, (float(y) - y_mid) / max(bbox["y_max"] - y_mid, 1e-9)))
            side_weight = min(1.0, abs(float(x) - center_x) / half_width)
            if x < center_x:
                side_target = target_left_x
            else:
                side_target = target_right_x
            x_target = (1.0 - side_weight) * (center_x + (x - center_x) * 1.10) + side_weight * side_target
            x_alpha = float(spread_alpha) * lower_weight + float(side_alpha) * side_weight * 0.35
            y_alpha = float(bottom_alpha) * lower_weight
            pts[idx, 1] = x + x_alpha * (x_target - x)
            pts[idx, 0] = y + y_alpha * (target_bottom_y - y)
        out.append(pts)
    return _cap_to_original(strokes, out, max_shift_px=max_shift_px)


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
                    "source": "lishu_structure_adaptation_v3_trial",
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
                "source": "lishu_structure_adaptation_v3_trial",
            }
        )
        break_count += 1
    _write_csv(path, rows, TRIAL_FIELDS)
    return point_count, break_count


def _draw_strokes(ax: Any, strokes: Sequence[np.ndarray], title: str, color: str, guide_bbox: dict[str, float] | None = None) -> None:
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.invert_yaxis()
    if guide_bbox:
        y_mid = guide_bbox["y_min"] + 0.50 * guide_bbox["height"]
        rect_y = y_mid
        rect_h = guide_bbox["y_max"] - y_mid
        ax.add_patch(
            plt.Rectangle(
                (guide_bbox["x_min"], rect_y),
                guide_bbox["width"],
                rect_h,
                fill=False,
                edgecolor="#999999",
                linestyle="--",
                linewidth=0.8,
            )
        )
        ax.axhline(guide_bbox["y_max"], color="#bbbbbb", linestyle=":", linewidth=0.8)
    for idx, stroke in enumerate(strokes, start=1):
        pts = np.asarray(stroke, dtype=float)
        if len(pts) < 2:
            continue
        ax.plot(pts[:, 1], pts[:, 0], color=color, linewidth=1.6)
        ax.scatter(pts[0, 1], pts[0, 0], s=8, color=color)
        mid = pts[len(pts) // 2]
        ax.text(mid[1], mid[0], str(idx), fontsize=7, color="#111111")


def _write_compare_figure(
    mask: np.ndarray,
    skeleton: np.ndarray,
    median_strokes: Sequence[np.ndarray],
    v2_strokes: Sequence[np.ndarray],
    v3_conservative: Sequence[np.ndarray],
    v3_stronger: Sequence[np.ndarray],
    font_bbox: dict[str, float],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 5, figsize=(15.4, 3.4), dpi=150)
    _draw_strokes(axes[0], median_strokes, "original median", "#333333", font_bbox)
    axes[1].set_title("lishu font mask + skeleton", fontsize=8)
    axes[1].imshow(np.where(mask, 0.88, 1.0), cmap="gray", vmin=0, vmax=1)
    ys, xs = np.nonzero(skeleton)
    axes[1].scatter(xs, ys, s=0.7, color="#1f77b4", alpha=0.9)
    y_mid = font_bbox["y_min"] + 0.50 * font_bbox["height"]
    axes[1].add_patch(
        plt.Rectangle(
            (font_bbox["x_min"], y_mid),
            font_bbox["width"],
            font_bbox["y_max"] - y_mid,
            fill=False,
            edgecolor="#999999",
            linestyle="--",
            linewidth=0.8,
        )
    )
    axes[1].set_aspect("equal")
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    _draw_strokes(axes[2], v2_strokes, "v2 stronger", "#9467bd", font_bbox)
    _draw_strokes(axes[3], v3_conservative, "v3 structure conservative", "#d62728", font_bbox)
    _draw_strokes(axes[4], v3_stronger, "v3 structure stronger", "#2ca02c", font_bbox)
    for ax in axes:
        ax.set_xlim(0, mask.shape[1])
        ax.set_ylim(mask.shape[0], 0)
    fig.suptitle("u5c71 / lishu structure-constrained adaptation v3", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(path)
    plt.close(fig)


def _variant_metrics(
    original: Sequence[np.ndarray],
    variant: Sequence[np.ndarray],
    reference: np.ndarray,
    font_aspect: float,
    original_length: float,
) -> dict[str, float]:
    shifts = _shift_stats(original, variant)
    path_length = _path_length(variant)
    aspect = bbox_aspect(variant)
    return {
        "projection_distance": _projection_distance(variant, reference),
        "bbox_aspect": aspect,
        "aspect_gap": _aspect_gap(aspect, font_aspect),
        "lower_half_width": lower_half_width(variant),
        "max_point_shift_px": shifts["max_point_shift_px"],
        "mean_point_shift_px": shifts["mean_point_shift_px"],
        "path_length_ratio": round(path_length / original_length if original_length > 1e-9 else 0.0, 6),
    }


def _write_report(path: Path, output_dir: Path, row: dict[str, Any]) -> None:
    lines = [
        "# Lishu structure adaptation v3 prototype",
        "",
        "This diagnostic prototype only handles 山/lishu. It adds structure-level constraints after v2 stronger.",
        "",
        "## Boundary",
        "",
        "- 保留 MakeMeAHanzi stroke order 和 stroke_count。",
        "- 不恢复真实笔顺，不跨 stroke 合并，不重排笔顺。",
        "- 不生成正式 `trajectory.csv`，只输出 `lishu_structure_v3_*.csv`。",
        "- 不接默认 pipeline，不接 execution/workspace/CoppeliaSim/AUBO/SDK。",
        "- structure-level constraints 只是诊断性启发式，不等同真实隶书风格学习。",
        "",
        "## Output",
        "",
        f"`{output_dir}`",
        "",
        "## Main comparison",
        "",
        "| sample | v2_dist | v3_cons_dist | v3_strong_dist | v2_aspect | v3_cons_aspect | v3_strong_aspect | lower_v2 | lower_v3_cons | lower_v3_strong | warning |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        (
            f"| 山/lishu | {row['projection_distance_v2_stronger']} | "
            f"{row['projection_distance_v3_conservative']} | {row['projection_distance_v3_stronger']} | "
            f"{row['bbox_aspect_v2_stronger']} | {row['bbox_aspect_v3_conservative']} | "
            f"{row['bbox_aspect_v3_stronger']} | {row['lower_half_width_v2_stronger']} | "
            f"{row['lower_half_width_v3_conservative']} | {row['lower_half_width_v3_stronger']} | "
            f"{row['warning']} |"
        ),
        "",
        "## Diagnostic answers",
        "",
        "- v3 是否改善 lower-half width / aspect gap：请同时看 summary 数值和 compare 图。",
        "- v3 是否比 v2 更像隶书宽底结构：本轮只给结构约束候选，不替代人工看图。",
        "- 是否过度扭曲：重点看 stronger 是否接近 22 px shift cap，以及 path_length_ratio 是否异常。",
        "- 本轮结果用于判断隶书是否需要 structure-level constraints，而不是继续 point-level projection。",
        "",
        "## Manual visual questions",
        "",
        "- 山/lishu 是否比 v2 更有隶书结构？",
        "- 底部是否更展开？",
        "- 是否仍保持可写性？",
        "- 是否有不自然拉扯、断裂或折笔？",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(paper_dir: Path, output_dir: Path, summary_csv: Path, report_md: Path, row: dict[str, Any]) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    index = paper_dir / "lishu_structure_adaptation_v3_index.md"
    lines = [
        "# Lishu structure adaptation v3 prototype index",
        "",
        f"- Output directory: `{output_dir}`",
        f"- Summary: `{summary_csv}`",
        f"- Report: `{report_md}`",
        f"- Compare: `{row['compare_png']}`",
        "",
        "| sample | v2_dist | v3_conservative_dist | v3_stronger_dist | lower_v2 | lower_v3_conservative | lower_v3_stronger |",
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| 山/lishu | {row['projection_distance_v2_stronger']} | "
            f"{row['projection_distance_v3_conservative']} | {row['projection_distance_v3_stronger']} | "
            f"{row['lower_half_width_v2_stronger']} | {row['lower_half_width_v3_conservative']} | "
            f"{row['lower_half_width_v3_stronger']} |"
        ),
        "",
        "Boundary: diagnostic only; no formal trajectory.csv, no default pipeline integration, no robot interface.",
    ]
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index


def run_lishu_structure_adaptation_v3(
    output_dir: Path | str | None = None,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    image_size: int = 256,
    skeleton_method: str = "auto",
    max_point_shift_px: float = 22.0,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"lishu_structure_adaptation_v3_{timestamp}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    style_sources_path = Path(style_sources_path)

    sample_dir = output_dir / f"{_char_id(CHAR)}_{STYLE}"
    sample_dir.mkdir(parents=True, exist_ok=True)

    median_strokes, mask, clean_skeleton, reference = _prepare_sample(
        CHAR,
        STYLE,
        image_size=image_size,
        skeleton_method=skeleton_method,
        style_sources_path=style_sources_path,
    )
    font_bbox = _bbox_from_mask(mask)
    font_aspect = _bbox_aspect_from_bbox(font_bbox)
    median_aspect = bbox_aspect(median_strokes)
    original_length = _path_length(median_strokes)

    v2_stronger = adapt_v2(
        median_strokes,
        font_bbox,
        reference,
        bbox_alpha=0.40,
        anchor_alpha=0.35,
        max_point_shift_px=18.0,
    )
    font_lower_points = _lower_half_points(_mask_points(mask))
    if len(font_lower_points):
        target_left_x = float(np.min(font_lower_points[:, 1]))
        target_right_x = float(np.max(font_lower_points[:, 1]))
        target_bottom_y = float(np.max(font_lower_points[:, 0]))
    else:
        target_left_x = font_bbox["x_min"]
        target_right_x = font_bbox["x_max"]
        target_bottom_y = font_bbox["y_max"]

    v3_by_variant: dict[str, list[np.ndarray]] = {}
    metrics_by_variant: dict[str, dict[str, float]] = {}
    manifest_rows: list[dict[str, Any]] = []
    for variant, params in V3_VARIANTS.items():
        adapted = structure_spread_points(
            v2_stronger,
            target_left_x=target_left_x,
            target_right_x=target_right_x,
            target_bottom_y=target_bottom_y,
            spread_alpha=float(params["spread_alpha"]),
            bottom_alpha=float(params["bottom_alpha"]),
            side_alpha=float(params["side_alpha"]),
            max_shift_px=max_point_shift_px,
        )
        adapted = _cap_to_original(median_strokes, adapted, max_shift_px=max_point_shift_px)
        v3_by_variant[variant] = adapted
        metrics_by_variant[variant] = _variant_metrics(median_strokes, adapted, reference, font_aspect, original_length)
        trial_csv = sample_dir / f"lishu_structure_v3_{variant}.csv"
        _write_trial_csv(trial_csv, adapted, variant)
        manifest_rows.append(
            {
                "char": CHAR,
                "char_id": _char_id(CHAR),
                "style": STYLE,
                "sample_dir": str(sample_dir),
                "variant": variant,
                "trial_csv": str(trial_csv),
                "compare_png": str(sample_dir / "lishu_structure_v3_compare.png"),
                "warning": "",
            }
        )

    v2_metrics = _variant_metrics(median_strokes, v2_stronger, reference, font_aspect, original_length)
    compare_png = sample_dir / "lishu_structure_v3_compare.png"
    _write_compare_figure(
        mask,
        clean_skeleton,
        median_strokes,
        v2_stronger,
        v3_by_variant["conservative"],
        v3_by_variant["stronger"],
        font_bbox,
        compare_png,
    )

    warning_parts: list[str] = []
    if metrics_by_variant["stronger"]["max_point_shift_px"] >= max_point_shift_px - 1e-6:
        warning_parts.append("stronger_reaches_shift_cap")
    for variant in ["conservative", "stronger"]:
        ratio = metrics_by_variant[variant]["path_length_ratio"]
        if ratio < 0.75 or ratio > 1.35:
            warning_parts.append(f"{variant}_path_length_ratio_outside_soft_range")

    summary = {
        "char": CHAR,
        "char_id": _char_id(CHAR),
        "style": STYLE,
        "stroke_count": len(median_strokes),
        "adapted_stroke_count": len(v3_by_variant["conservative"]),
        "point_count": int(sum(len(stroke) for stroke in median_strokes)),
        "projection_distance_before": _projection_distance(median_strokes, reference),
        "projection_distance_v2_stronger": v2_metrics["projection_distance"],
        "projection_distance_v3_conservative": metrics_by_variant["conservative"]["projection_distance"],
        "projection_distance_v3_stronger": metrics_by_variant["stronger"]["projection_distance"],
        "bbox_aspect_median": median_aspect,
        "bbox_aspect_font": font_aspect,
        "bbox_aspect_v2_stronger": v2_metrics["bbox_aspect"],
        "bbox_aspect_v3_conservative": metrics_by_variant["conservative"]["bbox_aspect"],
        "bbox_aspect_v3_stronger": metrics_by_variant["stronger"]["bbox_aspect"],
        "aspect_gap_before": _aspect_gap(median_aspect, font_aspect),
        "aspect_gap_v2_stronger": v2_metrics["aspect_gap"],
        "aspect_gap_v3_conservative": metrics_by_variant["conservative"]["aspect_gap"],
        "aspect_gap_v3_stronger": metrics_by_variant["stronger"]["aspect_gap"],
        "lower_half_width_median": lower_half_width(median_strokes),
        "lower_half_width_font": _lower_half_width_from_mask(mask),
        "lower_half_width_v2_stronger": v2_metrics["lower_half_width"],
        "lower_half_width_v3_conservative": metrics_by_variant["conservative"]["lower_half_width"],
        "lower_half_width_v3_stronger": metrics_by_variant["stronger"]["lower_half_width"],
        "max_point_shift_px": {
            "conservative": metrics_by_variant["conservative"]["max_point_shift_px"],
            "stronger": metrics_by_variant["stronger"]["max_point_shift_px"],
        },
        "path_length_ratio": {
            "conservative": metrics_by_variant["conservative"]["path_length_ratio"],
            "stronger": metrics_by_variant["stronger"]["path_length_ratio"],
        },
        "warning": ";".join(sorted(set(warning_parts))),
        "recommended_for_visual_followup": True,
        "scope": "diagnostic lishu structure adaptation v3 only; not formal trajectory; no robot",
    }
    summary_json = sample_dir / "lishu_structure_v3_summary.json"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    row = {
        "char": CHAR,
        "char_id": _char_id(CHAR),
        "style": STYLE,
        "sample_dir": str(sample_dir),
        "summary_json": str(summary_json),
        "compare_png": str(compare_png),
        "stroke_count": summary["stroke_count"],
        "point_count": summary["point_count"],
        "projection_distance_before": summary["projection_distance_before"],
        "projection_distance_v2_stronger": summary["projection_distance_v2_stronger"],
        "projection_distance_v3_conservative": summary["projection_distance_v3_conservative"],
        "projection_distance_v3_stronger": summary["projection_distance_v3_stronger"],
        "bbox_aspect_median": summary["bbox_aspect_median"],
        "bbox_aspect_font": summary["bbox_aspect_font"],
        "bbox_aspect_v2_stronger": summary["bbox_aspect_v2_stronger"],
        "bbox_aspect_v3_conservative": summary["bbox_aspect_v3_conservative"],
        "bbox_aspect_v3_stronger": summary["bbox_aspect_v3_stronger"],
        "lower_half_width_median": summary["lower_half_width_median"],
        "lower_half_width_font": summary["lower_half_width_font"],
        "lower_half_width_v2_stronger": summary["lower_half_width_v2_stronger"],
        "lower_half_width_v3_conservative": summary["lower_half_width_v3_conservative"],
        "lower_half_width_v3_stronger": summary["lower_half_width_v3_stronger"],
        "max_point_shift_px_conservative": summary["max_point_shift_px"]["conservative"],
        "max_point_shift_px_stronger": summary["max_point_shift_px"]["stronger"],
        "path_length_ratio_conservative": summary["path_length_ratio"]["conservative"],
        "path_length_ratio_stronger": summary["path_length_ratio"]["stronger"],
        "warning": summary["warning"],
        "recommended_for_visual_followup": True,
    }

    summary_csv = output_dir / "lishu_structure_v3_summary.csv"
    manifest_csv = output_dir / "lishu_structure_v3_manifest.csv"
    report_md = output_dir / "lishu_structure_v3_report.md"
    _write_csv(summary_csv, [row], SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, output_dir, row)

    paper_index = ""
    if copy_to_paper:
        index = _write_paper_index(DEFAULT_PAPER_DIR, output_dir, summary_csv, report_md, row)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "lishu_structure_v3_summary.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "lishu_structure_v3_report.md")
        paper_index = str(index)

    return {
        "output_dir": str(output_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "paper_index": paper_index,
        "row": row,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--style-sources", type=Path, default=DEFAULT_STYLE_SOURCES)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--skeleton-method", choices=["auto", "skimage", "opencv", "ridge"], default="auto")
    parser.add_argument("--max-point-shift-px", type=float, default=22.0)
    parser.add_argument("--no-paper-copy", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_lishu_structure_adaptation_v3(
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
