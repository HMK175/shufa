"""Lishu component-level alignment prototype for 山 / lishu.

This B-route diagnostic prototype stops increasing global structure pulling.
It keeps MakeMeAHanzi stroke order and stroke count, assigns median points to
simple component groups, and applies group-specific shifts toward lishu font
mask hints. It is not wired into the default pipeline and does not write formal
trajectory.csv, execution, workspace, CoppeliaSim, AUBO, or SDK outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from lishu_structure_adaptation_v3 import (
    CHAR,
    STYLE,
    _cap_to_original,
    _lower_half_points,
    _lower_half_width_from_mask,
    _mask_points,
    lower_half_width,
)
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
from lishu_structure_adaptation_v3 import structure_spread_points


COMPONENT_GROUPS = [
    "left_group",
    "center_group",
    "right_group",
    "lower_support_group",
]
TRIAL_FIELDS = ["y", "x", "stroke_id", "point_index", "component_group", "is_break", "variant", "source"]
SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "sample_dir",
    "summary_json",
    "compare_png",
    "stroke_count",
    "point_count",
    "component_groups",
    "group_point_counts",
    "projection_distance_original",
    "projection_distance_v2_stronger",
    "projection_distance_v3_stronger",
    "projection_distance_component_conservative",
    "projection_distance_component_stronger",
    "bbox_aspect_original",
    "bbox_aspect_font",
    "bbox_aspect_v3_stronger",
    "bbox_aspect_component_conservative",
    "bbox_aspect_component_stronger",
    "lower_half_width_original",
    "lower_half_width_font",
    "lower_half_width_v3_stronger",
    "lower_half_width_component_conservative",
    "lower_half_width_component_stronger",
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
VARIANTS = {
    "conservative": {"left_right_alpha": 0.20, "lower_alpha": 0.22, "center_alpha": 0.06, "bottom_alpha": 0.10},
    "stronger": {"left_right_alpha": 0.32, "lower_alpha": 0.35, "center_alpha": 0.08, "bottom_alpha": 0.16},
}


def assign_component_groups(strokes: Sequence[np.ndarray]) -> list[list[str]]:
    flat = _flatten(strokes)
    if len(flat) == 0:
        return [[] for _ in strokes]
    bbox = _bbox_from_points(flat)
    left_cut = bbox["x_min"] + bbox["width"] / 3.0
    right_cut = bbox["x_min"] + 2.0 * bbox["width"] / 3.0
    lower_cut = bbox["y_min"] + 0.58 * max(bbox["height"], 1e-9)
    labels: list[list[str]] = []
    for stroke in strokes:
        stroke_labels: list[str] = []
        for y, x in np.asarray(stroke, dtype=float):
            if y >= lower_cut:
                stroke_labels.append("lower_support_group")
            elif x <= left_cut:
                stroke_labels.append("left_group")
            elif x >= right_cut:
                stroke_labels.append("right_group")
            else:
                stroke_labels.append("center_group")
        labels.append(stroke_labels)
    return labels


def _group_point_counts(labels: Sequence[Sequence[str]]) -> dict[str, int]:
    counts = {group: 0 for group in COMPONENT_GROUPS}
    for stroke_labels in labels:
        for label in stroke_labels:
            counts[label] = counts.get(label, 0) + 1
    return counts


def _font_targets(mask: np.ndarray) -> dict[str, float]:
    bbox = _bbox_from_mask(mask)
    points = _mask_points(mask)
    lower = _lower_half_points(points)
    if len(lower):
        lower_left = float(np.min(lower[:, 1]))
        lower_right = float(np.max(lower[:, 1]))
        lower_bottom = float(np.max(lower[:, 0]))
    else:
        lower_left = bbox["x_min"]
        lower_right = bbox["x_max"]
        lower_bottom = bbox["y_max"]
    left_zone = points[points[:, 1] <= bbox["x_min"] + bbox["width"] * 0.36] if len(points) else points
    center_zone = points[
        (points[:, 1] >= bbox["x_min"] + bbox["width"] * 0.36)
        & (points[:, 1] <= bbox["x_min"] + bbox["width"] * 0.64)
    ] if len(points) else points
    right_zone = points[points[:, 1] >= bbox["x_min"] + bbox["width"] * 0.64] if len(points) else points
    return {
        "left_x": float(np.mean(left_zone[:, 1])) if len(left_zone) else bbox["x_min"],
        "center_x": float(np.mean(center_zone[:, 1])) if len(center_zone) else 0.5 * (bbox["x_min"] + bbox["x_max"]),
        "right_x": float(np.mean(right_zone[:, 1])) if len(right_zone) else bbox["x_max"],
        "lower_left_x": lower_left,
        "lower_right_x": lower_right,
        "lower_bottom_y": lower_bottom,
    }


def component_align_points(
    strokes: Sequence[np.ndarray],
    labels: Sequence[Sequence[str]],
    targets: dict[str, float],
    left_right_alpha: float,
    lower_alpha: float,
    center_alpha: float,
    bottom_alpha: float,
    max_shift_px: float = 24.0,
) -> list[np.ndarray]:
    flat = _flatten(strokes)
    bbox = _bbox_from_points(flat)
    center_x = 0.5 * (bbox["x_min"] + bbox["x_max"])
    out: list[np.ndarray] = []
    for stroke, stroke_labels in zip(strokes, labels):
        pts = np.asarray(stroke, dtype=float).copy()
        for idx, label in enumerate(stroke_labels):
            y, x = pts[idx]
            if label == "left_group":
                target_x = min(float(targets["left_x"]), x)
                pts[idx, 1] = x + float(left_right_alpha) * (target_x - x)
            elif label == "right_group":
                target_x = max(float(targets["right_x"]), x)
                pts[idx, 1] = x + float(left_right_alpha) * (target_x - x)
            elif label == "center_group":
                pts[idx, 1] = x + float(center_alpha) * (float(targets["center_x"]) - x)
            else:
                side_target = targets["lower_left_x"] if x < center_x else targets["lower_right_x"]
                if x < center_x:
                    side_target = min(float(side_target), x)
                else:
                    side_target = max(float(side_target), x)
                pts[idx, 1] = x + float(lower_alpha) * (side_target - x)
                pts[idx, 0] = y + float(bottom_alpha) * (float(targets["lower_bottom_y"]) - y)
        out.append(pts)
    return _cap_to_original(strokes, out, max_shift_px=max_shift_px)


def _write_trial_csv(path: Path, strokes: Sequence[np.ndarray], labels: Sequence[Sequence[str]], variant: str) -> None:
    rows: list[dict[str, Any]] = []
    for stroke_id, (stroke, stroke_labels) in enumerate(zip(strokes, labels), start=1):
        pts = np.asarray(stroke, dtype=float)
        for point_index, ((y, x), label) in enumerate(zip(pts, stroke_labels)):
            rows.append(
                {
                    "y": round(float(y), 6),
                    "x": round(float(x), 6),
                    "stroke_id": stroke_id,
                    "point_index": point_index,
                    "component_group": label,
                    "is_break": 0,
                    "variant": variant,
                    "source": "lishu_component_alignment_trial",
                }
            )
        rows.append(
            {
                "y": "nan",
                "x": "nan",
                "stroke_id": stroke_id,
                "point_index": "",
                "component_group": "",
                "is_break": 1,
                "variant": variant,
                "source": "lishu_component_alignment_trial",
            }
        )
    _write_csv(path, rows, TRIAL_FIELDS)


def _metrics(original: Sequence[np.ndarray], candidate: Sequence[np.ndarray], reference: np.ndarray, font_aspect: float, original_length: float) -> dict[str, float]:
    shifts = _shift_stats(original, candidate)
    path_length = _path_length(candidate)
    aspect = bbox_aspect(candidate)
    return {
        "projection_distance": _projection_distance(candidate, reference),
        "bbox_aspect": aspect,
        "aspect_gap": _aspect_gap(aspect, font_aspect),
        "lower_half_width": lower_half_width(candidate),
        "max_point_shift_px": shifts["max_point_shift_px"],
        "path_length_ratio": round(path_length / original_length if original_length > 1e-9 else 0.0, 6),
    }


def _draw_strokes(ax: Any, strokes: Sequence[np.ndarray], title: str, color: str, labels: Sequence[Sequence[str]] | None = None) -> None:
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.invert_yaxis()
    group_colors = {
        "left_group": "#1f77b4",
        "center_group": "#ff7f0e",
        "right_group": "#2ca02c",
        "lower_support_group": "#d62728",
    }
    for idx, stroke in enumerate(strokes, start=1):
        pts = np.asarray(stroke, dtype=float)
        if len(pts) < 2:
            continue
        ax.plot(pts[:, 1], pts[:, 0], color=color, linewidth=1.5, alpha=0.9)
        ax.scatter(pts[0, 1], pts[0, 0], s=8, color=color)
        if labels:
            for (y, x), label in zip(pts, labels[idx - 1]):
                ax.scatter(x, y, s=10, color=group_colors.get(label, "#666666"), alpha=0.8)
        mid = pts[len(pts) // 2]
        ax.text(mid[1], mid[0], str(idx), fontsize=7, color="#111111")


def _write_compare_figure(
    mask: np.ndarray,
    skeleton: np.ndarray,
    median: Sequence[np.ndarray],
    v2: Sequence[np.ndarray],
    v3: Sequence[np.ndarray],
    component_conservative: Sequence[np.ndarray],
    component_stronger: Sequence[np.ndarray],
    labels: Sequence[Sequence[str]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 6, figsize=(18.4, 3.4), dpi=150)
    _draw_strokes(axes[0], median, "original median + groups", "#333333", labels)
    axes[1].set_title("lishu font mask + skeleton", fontsize=8)
    axes[1].imshow(np.where(mask, 0.88, 1.0), cmap="gray", vmin=0, vmax=1)
    ys, xs = np.nonzero(skeleton)
    axes[1].scatter(xs, ys, s=0.7, color="#1f77b4", alpha=0.9)
    axes[1].set_aspect("equal")
    axes[1].set_xticks([])
    axes[1].set_yticks([])
    _draw_strokes(axes[2], v2, "v2 stronger", "#9467bd")
    _draw_strokes(axes[3], v3, "v3 stronger", "#8c564b")
    _draw_strokes(axes[4], component_conservative, "component conservative", "#d62728", labels)
    _draw_strokes(axes[5], component_stronger, "component stronger", "#2ca02c", labels)
    for ax in axes:
        ax.set_xlim(0, mask.shape[1])
        ax.set_ylim(mask.shape[0], 0)
    fig.suptitle("u5c71 / lishu component-level alignment prototype", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(path)
    plt.close(fig)


def _write_report(path: Path, output_dir: Path, row: dict[str, Any]) -> None:
    lines = [
        "# Lishu component-level alignment prototype",
        "",
        "This diagnostic prototype only handles 山/lishu and applies component-level alignment.",
        "",
        "## Boundary",
        "",
        "- 保留 MakeMeAHanzi stroke order 和 stroke_count。",
        "- 不恢复真实笔顺，不跨 stroke 合并，不重排笔顺。",
        "- 不生成正式 `trajectory.csv`，只输出 `lishu_component_alignment_*.csv`。",
        "- 不接默认 pipeline，不接 execution/workspace/CoppeliaSim/AUBO/SDK。",
        "- component-level alignment 是诊断性启发式，不等同真实隶书生成。",
        "",
        "## Output",
        "",
        f"`{output_dir}`",
        "",
        "## Main comparison",
        "",
        "| sample | v3_dist | comp_cons_dist | comp_strong_dist | v3_aspect | comp_cons_aspect | comp_strong_aspect | lower_v3 | lower_comp_cons | lower_comp_strong | warning |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        (
            f"| 山/lishu | {row['projection_distance_v3_stronger']} | "
            f"{row['projection_distance_component_conservative']} | {row['projection_distance_component_stronger']} | "
            f"{row['bbox_aspect_v3_stronger']} | {row['bbox_aspect_component_conservative']} | "
            f"{row['bbox_aspect_component_stronger']} | {row['lower_half_width_v3_stronger']} | "
            f"{row['lower_half_width_component_conservative']} | {row['lower_half_width_component_stronger']} | "
            f"{row['warning']} |"
        ),
        "",
        "## Diagnostic answers",
        "",
        "- component-level alignment 是否比 v3 更有效：请同时看 lower_half_width、aspect gap 和 compare 图。",
        "- 是否避免纯全局拉扯：本轮按 left/center/right/lower support 点级 group 分别移动。",
        "- 是否保留 stroke_count / stroke order：输出仍沿用 MakeMeAHanzi stroke 顺序和断笔。",
        "- 是否出现不自然变形：重点看 stronger 的 shift cap、path_length_ratio 和人工图像效果。",
        "",
        "## Manual visual questions",
        "",
        "- 山/lishu 是否更像隶书宽底结构？",
        "- component groups 是否合理？",
        "- component stronger 是否过度拉扯？",
        "- conservative 是否更自然？",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(paper_dir: Path, output_dir: Path, summary_csv: Path, report_md: Path, row: dict[str, Any]) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    index = paper_dir / "lishu_component_alignment_index.md"
    lines = [
        "# Lishu component-level alignment prototype index",
        "",
        f"- Output directory: `{output_dir}`",
        f"- Summary: `{summary_csv}`",
        f"- Report: `{report_md}`",
        f"- Compare: `{row['compare_png']}`",
        "",
        "| sample | v3_dist | component_conservative_dist | component_stronger_dist | lower_v3 | lower_component_conservative | lower_component_stronger |",
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| 山/lishu | {row['projection_distance_v3_stronger']} | "
            f"{row['projection_distance_component_conservative']} | {row['projection_distance_component_stronger']} | "
            f"{row['lower_half_width_v3_stronger']} | {row['lower_half_width_component_conservative']} | "
            f"{row['lower_half_width_component_stronger']} |"
        ),
        "",
        "Boundary: diagnostic only; no formal trajectory.csv, no default pipeline integration, no robot interface.",
    ]
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index


def run_lishu_component_alignment(
    output_dir: Path | str | None = None,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    image_size: int = 256,
    skeleton_method: str = "auto",
    max_point_shift_px: float = 24.0,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"lishu_component_alignment_{timestamp}"
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
    original_length = _path_length(median_strokes)
    labels = assign_component_groups(median_strokes)
    group_counts = _group_point_counts(labels)
    targets = _font_targets(mask)

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
    v3_stronger = structure_spread_points(
        v2_stronger,
        target_left_x=target_left_x,
        target_right_x=target_right_x,
        target_bottom_y=target_bottom_y,
        spread_alpha=0.45,
        bottom_alpha=0.28,
        side_alpha=0.34,
        max_shift_px=22.0,
    )
    v3_stronger = _cap_to_original(median_strokes, v3_stronger, max_shift_px=22.0)

    component_by_variant: dict[str, list[np.ndarray]] = {}
    metrics_by_variant: dict[str, dict[str, float]] = {}
    manifest_rows: list[dict[str, Any]] = []
    for variant, params in VARIANTS.items():
        adapted = component_align_points(
            v3_stronger,
            labels,
            targets,
            left_right_alpha=float(params["left_right_alpha"]),
            lower_alpha=float(params["lower_alpha"]),
            center_alpha=float(params["center_alpha"]),
            bottom_alpha=float(params["bottom_alpha"]),
            max_shift_px=max_point_shift_px,
        )
        adapted = _cap_to_original(median_strokes, adapted, max_shift_px=max_point_shift_px)
        component_by_variant[variant] = adapted
        metrics_by_variant[variant] = _metrics(median_strokes, adapted, reference, font_aspect, original_length)
        trial_csv = sample_dir / f"lishu_component_alignment_{variant}.csv"
        _write_trial_csv(trial_csv, adapted, labels, variant)
        manifest_rows.append(
            {
                "char": CHAR,
                "char_id": _char_id(CHAR),
                "style": STYLE,
                "sample_dir": str(sample_dir),
                "variant": variant,
                "trial_csv": str(trial_csv),
                "compare_png": str(sample_dir / "lishu_component_alignment_compare.png"),
                "warning": "",
            }
        )

    v2_metrics = _metrics(median_strokes, v2_stronger, reference, font_aspect, original_length)
    v3_metrics = _metrics(median_strokes, v3_stronger, reference, font_aspect, original_length)
    compare_png = sample_dir / "lishu_component_alignment_compare.png"
    _write_compare_figure(
        mask,
        clean_skeleton,
        median_strokes,
        v2_stronger,
        v3_stronger,
        component_by_variant["conservative"],
        component_by_variant["stronger"],
        labels,
        compare_png,
    )

    warning_parts: list[str] = []
    for variant in ["conservative", "stronger"]:
        if metrics_by_variant[variant]["max_point_shift_px"] >= max_point_shift_px - 1e-6:
            warning_parts.append(f"{variant}_reaches_shift_cap")
        if metrics_by_variant[variant]["path_length_ratio"] < 0.80:
            warning_parts.append(f"{variant}_path_length_ratio_below_0.80")

    summary = {
        "char": CHAR,
        "char_id": _char_id(CHAR),
        "style": STYLE,
        "stroke_count": len(median_strokes),
        "adapted_stroke_count": len(component_by_variant["conservative"]),
        "point_count": int(sum(len(stroke) for stroke in median_strokes)),
        "component_groups": COMPONENT_GROUPS,
        "group_point_counts": group_counts,
        "projection_distance_original": _projection_distance(median_strokes, reference),
        "projection_distance_v2_stronger": v2_metrics["projection_distance"],
        "projection_distance_v3_stronger": v3_metrics["projection_distance"],
        "projection_distance_component_conservative": metrics_by_variant["conservative"]["projection_distance"],
        "projection_distance_component_stronger": metrics_by_variant["stronger"]["projection_distance"],
        "bbox_aspect_original": bbox_aspect(median_strokes),
        "bbox_aspect_font": font_aspect,
        "bbox_aspect_v3_stronger": v3_metrics["bbox_aspect"],
        "bbox_aspect_component_conservative": metrics_by_variant["conservative"]["bbox_aspect"],
        "bbox_aspect_component_stronger": metrics_by_variant["stronger"]["bbox_aspect"],
        "aspect_gap_v3_stronger": v3_metrics["aspect_gap"],
        "aspect_gap_component_conservative": metrics_by_variant["conservative"]["aspect_gap"],
        "aspect_gap_component_stronger": metrics_by_variant["stronger"]["aspect_gap"],
        "lower_half_width_original": lower_half_width(median_strokes),
        "lower_half_width_font": _lower_half_width_from_mask(mask),
        "lower_half_width_v3_stronger": v3_metrics["lower_half_width"],
        "lower_half_width_component_conservative": metrics_by_variant["conservative"]["lower_half_width"],
        "lower_half_width_component_stronger": metrics_by_variant["stronger"]["lower_half_width"],
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
        "scope": "diagnostic lishu component-level alignment only; not formal trajectory; no robot",
    }
    summary_json = sample_dir / "lishu_component_alignment_summary.json"
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
        "component_groups": ";".join(COMPONENT_GROUPS),
        "group_point_counts": json.dumps(group_counts, ensure_ascii=False, sort_keys=True),
        "projection_distance_original": summary["projection_distance_original"],
        "projection_distance_v2_stronger": summary["projection_distance_v2_stronger"],
        "projection_distance_v3_stronger": summary["projection_distance_v3_stronger"],
        "projection_distance_component_conservative": summary["projection_distance_component_conservative"],
        "projection_distance_component_stronger": summary["projection_distance_component_stronger"],
        "bbox_aspect_original": summary["bbox_aspect_original"],
        "bbox_aspect_font": summary["bbox_aspect_font"],
        "bbox_aspect_v3_stronger": summary["bbox_aspect_v3_stronger"],
        "bbox_aspect_component_conservative": summary["bbox_aspect_component_conservative"],
        "bbox_aspect_component_stronger": summary["bbox_aspect_component_stronger"],
        "lower_half_width_original": summary["lower_half_width_original"],
        "lower_half_width_font": summary["lower_half_width_font"],
        "lower_half_width_v3_stronger": summary["lower_half_width_v3_stronger"],
        "lower_half_width_component_conservative": summary["lower_half_width_component_conservative"],
        "lower_half_width_component_stronger": summary["lower_half_width_component_stronger"],
        "max_point_shift_px_conservative": summary["max_point_shift_px"]["conservative"],
        "max_point_shift_px_stronger": summary["max_point_shift_px"]["stronger"],
        "path_length_ratio_conservative": summary["path_length_ratio"]["conservative"],
        "path_length_ratio_stronger": summary["path_length_ratio"]["stronger"],
        "warning": summary["warning"],
        "recommended_for_visual_followup": True,
    }

    summary_csv = output_dir / "lishu_component_alignment_summary.csv"
    manifest_csv = output_dir / "lishu_component_alignment_manifest.csv"
    report_md = output_dir / "lishu_component_alignment_report.md"
    _write_csv(summary_csv, [row], SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, output_dir, row)

    paper_index = ""
    if copy_to_paper:
        index = _write_paper_index(DEFAULT_PAPER_DIR, output_dir, summary_csv, report_md, row)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "lishu_component_alignment_summary.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "lishu_component_alignment_report.md")
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
    parser.add_argument("--max-point-shift-px", type=float, default=24.0)
    parser.add_argument("--no-paper-copy", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_lishu_component_alignment(
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
