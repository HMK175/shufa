"""Hybrid section refinement v1 for 风 / lishu.

This trial-only diagnostic prototype keeps the MakeMeAHanzi median stroke
order and stroke count, then applies bounded section-level adjustments using
safe H2 constraints plus font component bbox hints. Section partition prefers
font component boxes; when component extraction is unstable, it falls back to
top/mid/bottom bands.

It does not write formal trajectory.csv, execution/workspace/robot outputs, or
modify the default pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from constraint_bounded_adaptation_h1_lite import (
    DEFAULT_H2_CONSTRAINTS_JSON,
    _bbox,
    _cap_to_original,
    _draw_strokes,
    _flatten,
    _load_median,
    _path_length,
    _shift_stats,
    _variant_metrics,
    _write_csv,
    bbox_aspect,
    lower_half_width,
    load_usable_constraints,
)
from font_outline_basis_feasibility import DEFAULT_OUTPUT, DEFAULT_PAPER_DIR, first_existing_font, render_char_with_font
from median_font_adaptation_v2 import _bbox_aspect_from_bbox, DEFAULT_STYLE_SOURCES


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
TRIAL_FIELDS = ["y", "x", "stroke_id", "point_index", "section_name", "is_break", "variant", "source"]
SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "sample_dir",
    "summary_json",
    "compare_png",
    "stroke_count",
    "point_count",
    "section_count",
    "section_names",
    "section_source",
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
MANIFEST_FIELDS = [
    "char",
    "char_id",
    "style",
    "artifact_type",
    "path",
    "variant",
    "note",
]

CHAR = "\u98ce"
STYLE = "lishu"
IMAGE_SIZE = 256
VARIANT_PARAMS = {
    "conservative": {
        "aspect_alpha": 0.14,
        "lower_alpha": 0.16,
        "spread_alpha": 0.12,
        "center_shift_alpha": 0.18,
        "section_alpha": 0.20,
        "max_point_shift_px": 14.0,
    },
    "balanced": {
        "aspect_alpha": 0.24,
        "lower_alpha": 0.24,
        "spread_alpha": 0.18,
        "center_shift_alpha": 0.28,
        "section_alpha": 0.28,
        "max_point_shift_px": 17.0,
    },
}


def _char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else ""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_style_sources(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _neighbors(shape: tuple[int, int], y: int, x: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    h, w = shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                out.append((ny, nx))
    return out


def _component_bboxes(mask: np.ndarray, min_pixels: int = 48) -> list[dict[str, float]]:
    grid = np.asarray(mask, dtype=bool)
    if not np.any(grid):
        return []
    seen = np.zeros(grid.shape, dtype=bool)
    boxes: list[dict[str, float]] = []
    for y, x in zip(*np.nonzero(grid)):
        y = int(y)
        x = int(x)
        if seen[y, x]:
            continue
        queue: deque[tuple[int, int]] = deque([(y, x)])
        seen[y, x] = True
        pixels: list[tuple[int, int]] = []
        while queue:
            cy, cx = queue.popleft()
            pixels.append((cy, cx))
            for ny, nx in _neighbors(grid.shape, cy, cx):
                if grid[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        if len(pixels) < min_pixels:
            continue
        ys = np.asarray([p[0] for p in pixels], dtype=float)
        xs = np.asarray([p[1] for p in pixels], dtype=float)
        boxes.append(
            {
                "x_min": float(xs.min()),
                "x_max": float(xs.max()),
                "y_min": float(ys.min()),
                "y_max": float(ys.max()),
                "width": float(xs.max() - xs.min()),
                "height": float(ys.max() - ys.min()),
                "center_x": float(xs.mean()),
                "center_y": float(ys.mean()),
            }
        )
    boxes.sort(key=lambda item: (item["center_y"], item["center_x"]))
    return boxes


def build_hybrid_sections(mask: np.ndarray, max_sections: int = 4) -> dict[str, Any]:
    boxes = _component_bboxes(mask)
    if 2 <= len(boxes) <= max_sections:
        sections = []
        for idx, box in enumerate(boxes[:max_sections], start=1):
            sections.append(
                {
                    "name": f"component_{idx}",
                    "bbox": box,
                    "center_x": box["center_x"],
                    "center_y": box["center_y"],
                }
            )
        return {"section_source": "component_bbox", "sections": sections}

    grid = np.asarray(mask, dtype=bool)
    if np.any(grid):
        ys, xs = np.nonzero(grid)
        y_min = float(ys.min())
        y_max = float(ys.max())
        x_min = float(xs.min())
        x_max = float(xs.max())
    else:
        y_min = x_min = 0.0
        y_max = x_max = float(mask.shape[0] - 1)
    total_h = max(y_max - y_min, 1.0)
    boundaries = [y_min, y_min + total_h / 3.0, y_min + 2.0 * total_h / 3.0, y_max]
    names = ["top_band", "mid_band", "bottom_band"]
    sections = []
    for idx, name in enumerate(names):
        box = {
            "x_min": x_min,
            "x_max": x_max,
            "y_min": boundaries[idx],
            "y_max": boundaries[idx + 1],
            "width": max(x_max - x_min, 1.0),
            "height": max(boundaries[idx + 1] - boundaries[idx], 1.0),
            "center_x": 0.5 * (x_min + x_max),
            "center_y": 0.5 * (boundaries[idx] + boundaries[idx + 1]),
        }
        sections.append({"name": name, "bbox": box, "center_x": box["center_x"], "center_y": box["center_y"]})
    return {"section_source": "top_mid_bottom_fallback", "sections": sections}


def assign_sections_to_points(strokes: Sequence[np.ndarray], sections: Sequence[dict[str, Any]]) -> list[list[str]]:
    if not sections:
        return [[] for _ in strokes]
    out: list[list[str]] = []
    for stroke in strokes:
        labels: list[str] = []
        pts = np.asarray(stroke, dtype=float)
        for y, x in pts:
            best_name = str(sections[0]["name"])
            best_score = float("inf")
            for section in sections:
                box = section["bbox"]
                center_x = float(section.get("center_x", 0.5 * (box["x_min"] + box["x_max"])))
                center_y = float(section.get("center_y", 0.5 * (box["y_min"] + box["y_max"])))
                if box["x_min"] <= x <= box["x_max"] and box["y_min"] <= y <= box["y_max"]:
                    score = 0.0
                else:
                    score = abs(float(x) - center_x) + abs(float(y) - center_y)
                if score < best_score:
                    best_score = score
                    best_name = str(section["name"])
            labels.append(best_name)
        out.append(labels)
    return out


def _section_group_stats(
    labels: Sequence[Sequence[str]],
    strokes: Sequence[np.ndarray],
) -> dict[str, dict[str, float]]:
    groups: dict[str, list[list[float]]] = {}
    for stroke, stroke_labels in zip(strokes, labels):
        for (y, x), label in zip(np.asarray(stroke, dtype=float), stroke_labels):
            groups.setdefault(label, []).append([float(y), float(x)])
    stats: dict[str, dict[str, float]] = {}
    for name, pts in groups.items():
        arr = np.asarray(pts, dtype=float)
        stats[name] = {
            "center_x": float(np.mean(arr[:, 1])),
            "center_y": float(np.mean(arr[:, 0])),
            "x_min": float(np.min(arr[:, 1])),
            "x_max": float(np.max(arr[:, 1])),
            "y_min": float(np.min(arr[:, 0])),
            "y_max": float(np.max(arr[:, 0])),
        }
    return stats


def _left_right_spread_abs(strokes: Sequence[np.ndarray]) -> float:
    pts = _flatten(strokes)
    if len(pts) == 0:
        return 0.0
    return round(float(np.max(pts[:, 1]) - np.min(pts[:, 1])), 6)


def _bbox_metrics(strokes: Sequence[np.ndarray]) -> dict[str, float]:
    return {
        "bbox_aspect": bbox_aspect(strokes),
        "lower_half_width": lower_half_width(strokes),
        "left_right_spread": _left_right_spread_abs(strokes),
    }


def _hybrid_variant_metrics(original: Sequence[np.ndarray], variant: Sequence[np.ndarray]) -> dict[str, float]:
    shifts = _shift_stats(original, variant)
    original_length = _path_length(original)
    variant_length = _path_length(variant)
    metrics = _bbox_metrics(variant)
    return {
        "bbox_aspect": metrics["bbox_aspect"],
        "lower_half_width": metrics["lower_half_width"],
        "left_right_spread": metrics["left_right_spread"],
        "max_point_shift_px": shifts["max_point_shift_px"],
        "mean_point_shift_px": shifts["mean_point_shift_px"],
        "path_length_ratio": round(variant_length / original_length if original_length > 1e-9 else 0.0, 6),
    }


def _scaled_for_aspect(
    strokes: Sequence[np.ndarray],
    target_aspect: float,
    aspect_alpha: float,
    max_scale_delta: float = 0.16,
) -> list[np.ndarray]:
    pts = _flatten(strokes)
    box = _bbox(pts)
    current_aspect = bbox_aspect(strokes)
    if current_aspect <= 1e-9 or target_aspect <= 1e-9 or box["width"] <= 1e-9 or box["height"] <= 1e-9:
        return [np.asarray(stroke, dtype=float).copy() for stroke in strokes]
    ratio = max(target_aspect / current_aspect, 1e-9) ** 0.5
    sx_raw = ratio
    sy_raw = 1.0 / ratio
    sx_lim = max(1.0 - max_scale_delta, min(1.0 + max_scale_delta, sx_raw))
    sy_lim = max(1.0 - max_scale_delta, min(1.0 + max_scale_delta, sy_raw))
    sx = 1.0 + aspect_alpha * (sx_lim - 1.0)
    sy = 1.0 + aspect_alpha * (sy_lim - 1.0)
    cy = 0.5 * (box["y_min"] + box["y_max"])
    cx = 0.5 * (box["x_min"] + box["x_max"])
    out: list[np.ndarray] = []
    for stroke in strokes:
        arr = np.asarray(stroke, dtype=float).copy()
        arr[:, 0] = cy + (arr[:, 0] - cy) * sy
        arr[:, 1] = cx + (arr[:, 1] - cx) * sx
        out.append(arr)
    return out


def _apply_global_shift(
    strokes: Sequence[np.ndarray],
    dx: float,
    dy: float,
) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    for stroke in strokes:
        arr = np.asarray(stroke, dtype=float).copy()
        arr[:, 1] += dx
        arr[:, 0] += dy
        out.append(arr)
    return out


def _section_bounded_adjustment(
    original: Sequence[np.ndarray],
    section_labels: Sequence[Sequence[str]],
    median_section_stats: dict[str, dict[str, float]],
    target_sections: Sequence[dict[str, Any]],
    constraints: dict[str, float],
    variant: str,
    image_size: int,
) -> list[np.ndarray]:
    params = VARIANT_PARAMS[variant]
    target_aspect = float(constraints.get("bbox_aspect", bbox_aspect(original)))
    adapted = _scaled_for_aspect(original, target_aspect, float(params["aspect_alpha"]))
    box = _bbox(_flatten(adapted))
    current_metrics = _bbox_metrics(adapted)
    target_lower_ratio = float(constraints.get("lower_half_width_ratio", 0.0))
    target_lower_abs = target_lower_ratio * max(box["width"], 0.0)
    target_spread_abs = max(box["width"], 0.0) * float(constraints.get("left_right_spread", 0.0))
    lower_deficit = max(0.0, target_lower_abs - current_metrics["lower_half_width"])
    spread_deficit = max(0.0, target_spread_abs - current_metrics["left_right_spread"])
    dx = float(constraints.get("bbox_center_shift_x", 0.0)) * image_size * float(params["center_shift_alpha"])
    dy = float(constraints.get("bbox_center_shift_y", 0.0)) * image_size * float(params["center_shift_alpha"])
    adapted = _apply_global_shift(adapted, dx=dx, dy=dy)

    target_by_name = {str(item["name"]): item for item in target_sections}
    out: list[np.ndarray] = []
    center_x = 0.5 * (box["x_min"] + box["x_max"])
    for stroke, labels in zip(adapted, section_labels):
        arr = np.asarray(stroke, dtype=float).copy()
        for idx, label in enumerate(labels):
            if label not in target_by_name:
                continue
            target = target_by_name[label]
            med = median_section_stats.get(label, {"center_x": arr[idx, 1], "center_y": arr[idx, 0]})
            box_t = target["bbox"]
            target_cx = float(target.get("center_x", 0.5 * (box_t["x_min"] + box_t["x_max"])))
            target_cy = float(target.get("center_y", 0.5 * (box_t["y_min"] + box_t["y_max"])))
            local_alpha = float(params["section_alpha"])
            arr[idx, 1] += local_alpha * 0.55 * (target_cx - float(med["center_x"]))
            arr[idx, 0] += local_alpha * 0.28 * (target_cy - float(med["center_y"]))
            lower_weight = max(0.0, min(1.0, (arr[idx, 0] - (box["y_min"] + 0.5 * box["height"])) / max(0.5 * box["height"], 1e-9)))
            side = -1.0 if arr[idx, 1] < center_x else 1.0
            arr[idx, 1] += side * (float(params["spread_alpha"]) * spread_deficit * 0.18 + float(params["lower_alpha"]) * lower_deficit * lower_weight * 0.16)
        out.append(arr)
    return _cap_to_original(original, out, max_shift_px=float(params["max_point_shift_px"]))


def _write_trial_csv(path: Path, strokes: Sequence[np.ndarray], labels: Sequence[Sequence[str]], variant: str) -> int:
    rows: list[dict[str, Any]] = []
    point_count = 0
    for stroke_id, (stroke, stroke_labels) in enumerate(zip(strokes, labels), start=1):
        pts = np.asarray(stroke, dtype=float)
        for point_index, ((y, x), section_name) in enumerate(zip(pts, stroke_labels)):
            rows.append(
                {
                    "y": round(float(y), 6),
                    "x": round(float(x), 6),
                    "stroke_id": stroke_id,
                    "point_index": point_index,
                    "section_name": section_name,
                    "is_break": 0,
                    "variant": variant,
                    "source": "hybrid_section_refinement_v1_trial",
                }
            )
            point_count += 1
        rows.append(
            {
                "y": "nan",
                "x": "nan",
                "stroke_id": stroke_id,
                "point_index": "",
                "section_name": "",
                "is_break": 1,
                "variant": variant,
                "source": "hybrid_section_refinement_v1_trial",
            }
        )
    _write_csv(path, rows, TRIAL_FIELDS)
    return point_count


def _draw_mask_with_sections(ax: Any, mask: np.ndarray, sections: Sequence[dict[str, Any]], title: str) -> None:
    ax.set_title(title, fontsize=8)
    ax.imshow(np.where(mask, 0.88, 1.0), cmap="gray", vmin=0, vmax=1)
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    for idx, section in enumerate(sections):
        box = section["bbox"]
        color = colors[idx % len(colors)]
        ax.add_patch(
            plt.Rectangle(
                (box["x_min"], box["y_min"]),
                max(box["x_max"] - box["x_min"], 1.0),
                max(box["y_max"] - box["y_min"], 1.0),
                fill=False,
                edgecolor=color,
                linewidth=1.1,
            )
        )
        ax.text(box["x_min"] + 2, box["y_min"] + 10, str(section["name"]), color=color, fontsize=6)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def _draw_section_overlay(ax: Any, strokes: Sequence[np.ndarray], labels: Sequence[Sequence[str]], title: str) -> None:
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlim(0, IMAGE_SIZE)
    ax.set_ylim(IMAGE_SIZE, 0)
    ax.set_xticks([])
    ax.set_yticks([])
    colors = {
        "component_1": "#1f77b4",
        "component_2": "#ff7f0e",
        "component_3": "#2ca02c",
        "component_4": "#d62728",
        "top_band": "#1f77b4",
        "mid_band": "#ff7f0e",
        "bottom_band": "#2ca02c",
    }
    for stroke, stroke_labels in zip(strokes, labels):
        pts = np.asarray(stroke, dtype=float)
        ax.plot(pts[:, 1], pts[:, 0], color="#888888", linewidth=1.2, alpha=0.6)
        for (y, x), label in zip(pts, stroke_labels):
            ax.scatter(x, y, s=12, color=colors.get(label, "#666666"), alpha=0.85)


def _write_compare(
    path: Path,
    mask: np.ndarray,
    median: Sequence[np.ndarray],
    labels: Sequence[Sequence[str]],
    sections: Sequence[dict[str, Any]],
    conservative: Sequence[np.ndarray],
    balanced: Sequence[np.ndarray],
    section_source: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 5, figsize=(15.6, 3.4), dpi=150)
    _draw_strokes(axes[0], median, "original median", "#333333")
    _draw_mask_with_sections(axes[1], mask, sections, f"font sections ({section_source})")
    _draw_section_overlay(axes[2], median, labels, "median + section labels")
    _draw_strokes(axes[3], conservative, "hybrid section conservative", "#d62728")
    _draw_strokes(axes[4], balanced, "hybrid section balanced", "#2ca02c")
    fig.suptitle("u98ce / lishu hybrid section refinement v1", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(path)
    plt.close(fig)


def _write_report(path: Path, output_dir: Path, row: dict[str, Any], summary: dict[str, Any]) -> None:
    lines = [
        "# Hybrid section refinement v1",
        "",
        "This diagnostic prototype only handles 风/lishu and applies hybrid section refinement.",
        "",
        "## Boundary",
        "",
        "- trial-only / not_used_by_default。",
        "- component bbox 为主，top/mid/bottom 作为 fallback。",
        "- 只使用 H2 safe constraints，不使用 raw_skeleton_path / unordered_skeleton_segments / 最近点吸附。",
        "- 保留 stroke_count / stroke_order / stroke_breaks。",
        "- 不生成正式 trajectory.csv，不生成 execution/workspace/robot 文件，不接默认 pipeline。",
        "",
        f"- output_dir: `{output_dir}`",
        "",
        "## Main results",
        "",
        f"- section_count: {summary['section_count']}",
        f"- section_names: {', '.join(summary['section_names'])}",
        f"- section_source: {summary['section_source']}",
        f"- bbox aspect: {summary['bbox_aspect_median']} -> {summary['bbox_aspect_conservative']} / {summary['bbox_aspect_balanced']}",
        f"- lower-half width: {summary['lower_half_width_median']} -> {summary['lower_half_width_conservative']} / {summary['lower_half_width_balanced']}",
        f"- left-right spread: {summary['left_right_spread_median']} -> {summary['left_right_spread_conservative']} / {summary['left_right_spread_balanced']}",
        f"- max shift: {summary['max_point_shift_px']['conservative']} / {summary['max_point_shift_px']['balanced']} px",
        f"- path ratio: {summary['path_length_ratio']['conservative']} / {summary['path_length_ratio']['balanced']}",
        "",
        "## Questions for manual visual audit",
        "",
        "- hybrid section refinement 是否比前面的 component-only 更稳？",
        "- 风/lishu 是否仍保持可写性？",
        "- 是否真的比 H1-lite 更自然地保留了隶书结构？",
        "- component bbox 为主 + top/mid/bottom fallback 是否比纯 component 或纯三段更合理？",
        "- 是否建议下一步把同样方法扩展到 山/lishu 或先整理 section 约束包？",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(index_path: Path, output_dir: Path, row: dict[str, Any], summary: dict[str, Any]) -> None:
    lines = [
        "# Hybrid section refinement v1 index",
        "",
        f"- source_output_dir: `{output_dir}`",
        "- Status: trial-only, not used by default.",
        "- Boundary: no formal trajectory.csv, no execution/workspace/robot outputs, no default pipeline integration.",
        "",
        f"- compare_png: `{row['compare_png']}`",
        f"- summary_json: `{row['summary_json']}`",
        f"- section_source: `{summary['section_source']}`",
        f"- section_names: {', '.join(summary['section_names'])}",
        f"- bbox_aspect: {summary['bbox_aspect_median']} -> {summary['bbox_aspect_conservative']} / {summary['bbox_aspect_balanced']}",
        f"- lower_half_width: {summary['lower_half_width_median']} -> {summary['lower_half_width_conservative']} / {summary['lower_half_width_balanced']}",
    ]
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sample_dir_name(char: str, style: str) -> str:
    return f"{_char_id(char)}_{style}"


def _prepare_font_mask(style_sources_path: Path, image_size: int) -> np.ndarray:
    style_sources = _load_style_sources(style_sources_path)
    font_path = first_existing_font(style_sources, STYLE, style_sources_path.parent)
    if font_path is None:
        return np.zeros((image_size, image_size), dtype=bool)
    return render_char_with_font(CHAR, font_path, image_size=image_size)


def run_hybrid_section_refinement_v1(
    output_dir: Path | str | None = None,
    constraints_json_path: Path | str = DEFAULT_H2_CONSTRAINTS_JSON,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    image_size: int = IMAGE_SIZE,
    skeleton_method: str = "auto",
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    del skeleton_method  # documented boundary: no raw skeleton-path pulling in this prototype
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"hybrid_section_refinement_{timestamp}"
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sample_dir = out_dir / _sample_dir_name(CHAR, STYLE)
    sample_dir.mkdir(parents=True, exist_ok=True)
    constraints = load_usable_constraints(Path(constraints_json_path), _char_id(CHAR), STYLE)
    median = _load_median(CHAR, image_size=image_size)
    mask = _prepare_font_mask(Path(style_sources_path), image_size=image_size)
    section_info = build_hybrid_sections(mask, max_sections=4)
    sections = section_info["sections"]
    labels = assign_sections_to_points(median, sections)
    stats = _section_group_stats(labels, median)

    conservative = _section_bounded_adjustment(
        median,
        section_labels=labels,
        median_section_stats=stats,
        target_sections=sections,
        constraints=constraints,
        variant="conservative",
        image_size=image_size,
    )
    balanced = _section_bounded_adjustment(
        median,
        section_labels=labels,
        median_section_stats=stats,
        target_sections=sections,
        constraints=constraints,
        variant="balanced",
        image_size=image_size,
    )

    point_count_cons = _write_trial_csv(sample_dir / "hybrid_section_conservative.csv", conservative, labels, "conservative")
    point_count_bal = _write_trial_csv(sample_dir / "hybrid_section_balanced.csv", balanced, labels, "balanced")
    if point_count_cons != point_count_bal:
        raise RuntimeError("Hybrid section variants diverged in point count")

    median_metrics = _bbox_metrics(median)
    cons_metrics = _hybrid_variant_metrics(median, conservative)
    bal_metrics = _hybrid_variant_metrics(median, balanced)
    target_lower_abs = round(float(constraints.get("lower_half_width_ratio", 0.0)) * max(_bbox(_flatten(median))["width"], 0.0), 6)
    target_spread_abs = round(max(_bbox(_flatten(median))["width"], 0.0) * float(constraints.get("left_right_spread", 0.0)), 6)

    compare_png = sample_dir / "hybrid_section_compare.png"
    _write_compare(
        compare_png,
        mask=mask,
        median=median,
        labels=labels,
        sections=sections,
        conservative=conservative,
        balanced=balanced,
        section_source=str(section_info["section_source"]),
    )

    summary = {
        "status": "trial_not_used_by_default",
        "source": "hybrid_section_refinement_v1_trial",
        "char": CHAR,
        "char_id": _char_id(CHAR),
        "style": STYLE,
        "stroke_count": len(median),
        "point_count": point_count_cons,
        "section_count": len(sections),
        "section_names": [str(section["name"]) for section in sections],
        "section_source": str(section_info["section_source"]),
        "bbox_aspect_median": median_metrics["bbox_aspect"],
        "bbox_aspect_target": round(float(constraints.get("bbox_aspect", median_metrics["bbox_aspect"])), 6),
        "bbox_aspect_conservative": cons_metrics["bbox_aspect"],
        "bbox_aspect_balanced": bal_metrics["bbox_aspect"],
        "lower_half_width_median": median_metrics["lower_half_width"],
        "lower_half_width_target": target_lower_abs,
        "lower_half_width_conservative": cons_metrics["lower_half_width"],
        "lower_half_width_balanced": bal_metrics["lower_half_width"],
        "left_right_spread_median": median_metrics["left_right_spread"],
        "left_right_spread_target": target_spread_abs,
        "left_right_spread_conservative": cons_metrics["left_right_spread"],
        "left_right_spread_balanced": bal_metrics["left_right_spread"],
        "max_point_shift_px": {
            "conservative": cons_metrics["max_point_shift_px"],
            "balanced": bal_metrics["max_point_shift_px"],
        },
        "mean_point_shift_px": {
            "conservative": cons_metrics["mean_point_shift_px"],
            "balanced": bal_metrics["mean_point_shift_px"],
        },
        "path_length_ratio": {
            "conservative": cons_metrics["path_length_ratio"],
            "balanced": bal_metrics["path_length_ratio"],
        },
        "stroke_count_preserved": len(conservative) == len(median) and len(balanced) == len(median),
        "warning": "",
        "recommended_for_visual_followup": True,
        "scope": "hybrid section refinement v1 trial only; not used by default; no execution/workspace/robot outputs",
    }
    summary_json = sample_dir / "hybrid_section_summary.json"
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    row = {
        "char": CHAR,
        "char_id": _char_id(CHAR),
        "style": STYLE,
        "sample_dir": str(sample_dir),
        "summary_json": str(summary_json),
        "compare_png": str(compare_png),
        "stroke_count": summary["stroke_count"],
        "point_count": summary["point_count"],
        "section_count": summary["section_count"],
        "section_names": ";".join(summary["section_names"]),
        "section_source": summary["section_source"],
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
        "warning": summary["warning"],
        "recommended_for_visual_followup": summary["recommended_for_visual_followup"],
    }

    summary_csv = out_dir / "hybrid_section_refinement_summary.csv"
    report_md = out_dir / "hybrid_section_refinement_report.md"
    manifest_csv = out_dir / "hybrid_section_refinement_manifest.csv"
    manifest_rows = [
        {
            "char": CHAR,
            "char_id": _char_id(CHAR),
            "style": STYLE,
            "artifact_type": "summary_json",
            "path": str(summary_json),
            "variant": "",
            "note": "trial_not_used_by_default",
        },
        {
            "char": CHAR,
            "char_id": _char_id(CHAR),
            "style": STYLE,
            "artifact_type": "compare_png",
            "path": str(compare_png),
            "variant": "",
            "note": summary["section_source"],
        },
        {
            "char": CHAR,
            "char_id": _char_id(CHAR),
            "style": STYLE,
            "artifact_type": "trial_csv",
            "path": str(sample_dir / "hybrid_section_conservative.csv"),
            "variant": "conservative",
            "note": summary["section_source"],
        },
        {
            "char": CHAR,
            "char_id": _char_id(CHAR),
            "style": STYLE,
            "artifact_type": "trial_csv",
            "path": str(sample_dir / "hybrid_section_balanced.csv"),
            "variant": "balanced",
            "note": summary["section_source"],
        },
    ]
    _write_csv(summary_csv, [row], SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, out_dir, row, summary)

    paper_index = ""
    if copy_to_paper:
        DEFAULT_PAPER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "hybrid_section_refinement_summary.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "hybrid_section_refinement_report.md")
        index_path = DEFAULT_PAPER_DIR / "hybrid_section_refinement_index.md"
        _write_paper_index(index_path, out_dir, row, summary)
        paper_index = str(index_path)

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "sample_dir": str(sample_dir),
        "paper_index": paper_index,
    }


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run hybrid section refinement v1 for 风/lishu.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--constraints-json", type=Path, default=DEFAULT_H2_CONSTRAINTS_JSON)
    parser.add_argument("--style-sources", type=Path, default=DEFAULT_STYLE_SOURCES)
    parser.add_argument("--image-size", type=int, default=IMAGE_SIZE)
    parser.add_argument("--skeleton-method", default="auto")
    parser.add_argument("--no-paper-copy", action="store_true")
    return parser


def main() -> None:
    parser = _build_argparser()
    args = parser.parse_args()
    result = run_hybrid_section_refinement_v1(
        output_dir=args.output_dir,
        constraints_json_path=args.constraints_json,
        style_sources_path=args.style_sources,
        image_size=args.image_size,
        skeleton_method=args.skeleton_method,
        copy_to_paper=not args.no_paper_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
