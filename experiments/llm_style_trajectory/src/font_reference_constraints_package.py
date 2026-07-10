"""H2 font-reference constraint package for the hybrid trajectory route.

This module extracts interpretable constraints from local font masks and
skeletons. It is reference-only: it does not move median points, does not write
trajectory.csv, and does not connect to execution, workspace, CoppeliaSim, AUBO,
or SDK flows.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter, deque
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

try:  # package import used by pytest
    from .font_outline_basis_feasibility import (
        first_existing_font,
        render_char_with_font,
        skeleton_topology_metrics,
        skeletonize_font_mask,
    )
except ImportError:  # direct script execution
    from font_outline_basis_feasibility import (
        first_existing_font,
        render_char_with_font,
        skeleton_topology_metrics,
        skeletonize_font_mask,
    )


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
DEFAULT_STYLE_SOURCES = EXP_DIR / "configs" / "style_sources.json"
DEFAULT_SAMPLES: list[tuple[str, str]] = [
    ("山", "kaishu"),
    ("人", "kaishu"),
    ("中", "kaishu"),
    ("山", "lishu"),
    ("中", "lishu"),
    ("永", "lishu"),
    ("风", "lishu"),
]

CONSTRAINT_FIELDS = [
    "char",
    "char_id",
    "style",
    "constraint_name",
    "constraint_value",
    "constraint_unit",
    "source",
    "confidence",
    "recommended_use",
    "risk_level",
    "note",
]

SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "bbox_aspect",
    "lower_half_width_ratio",
    "left_right_spread",
    "bbox_center_shift_x",
    "bbox_center_shift_y",
    "skeleton_component_count",
    "skeleton_endpoint_count",
    "skeleton_branch_count",
    "skeleton_complexity_score",
    "connectedness_hint",
    "usable_constraint_count",
    "visual_reference_only_count",
    "unsafe_constraint_count",
    "overall_recommendation",
]

MANIFEST_FIELDS = ["char", "char_id", "style", "figure_path", "overall_recommendation", "note"]


def _char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else ""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _neighbors(shape: tuple[int, int], y: int, x: int) -> list[tuple[int, int]]:
    height, width = shape
    result: list[tuple[int, int]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width:
                result.append((ny, nx))
    return result


def _component_count(grid: np.ndarray) -> int:
    skel = np.asarray(grid, dtype=bool)
    seen = np.zeros(skel.shape, dtype=bool)
    count = 0
    for y, x in zip(*np.nonzero(skel)):
        y = int(y)
        x = int(x)
        if seen[y, x]:
            continue
        count += 1
        queue: deque[tuple[int, int]] = deque([(y, x)])
        seen[y, x] = True
        while queue:
            cy, cx = queue.popleft()
            for ny, nx in _neighbors(skel.shape, cy, cx):
                if skel[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
    return count


def skeleton_metrics(skeleton: np.ndarray) -> dict[str, int]:
    skel = np.asarray(skeleton, dtype=bool)
    topology = skeleton_topology_metrics(skel)
    return {
        "connected_component_count": _component_count(skel),
        "skeleton_pixel_count": int(topology["skeleton_pixel_count"]),
        "endpoint_count": int(topology["endpoint_count"]),
        "branch_point_count": int(topology["branch_point_count"]),
    }


def _bbox(mask: np.ndarray) -> dict[str, float]:
    grid = np.asarray(mask, dtype=bool)
    if not np.any(grid):
        return {
            "x_min": 0.0,
            "x_max": 0.0,
            "y_min": 0.0,
            "y_max": 0.0,
            "width": 0.0,
            "height": 0.0,
            "aspect": 0.0,
            "center_x": 0.0,
            "center_y": 0.0,
        }
    ys, xs = np.nonzero(grid)
    x_min = float(xs.min())
    x_max = float(xs.max())
    y_min = float(ys.min())
    y_max = float(ys.max())
    width = x_max - x_min + 1.0
    height = y_max - y_min + 1.0
    return {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "width": width,
        "height": height,
        "aspect": width / height if height > 1e-9 else 0.0,
        "center_x": (x_min + x_max) / 2.0,
        "center_y": (y_min + y_max) / 2.0,
    }


def _lower_half_width_ratio(mask: np.ndarray, bbox: dict[str, float]) -> float:
    grid = np.asarray(mask, dtype=bool)
    if not np.any(grid) or bbox["width"] <= 1e-9:
        return 0.0
    threshold = bbox["y_min"] + bbox["height"] * 0.5
    ys, xs = np.nonzero(grid & (np.indices(grid.shape)[0] >= threshold))
    if len(xs) == 0:
        return 0.0
    lower_width = float(xs.max() - xs.min() + 1)
    return lower_width / bbox["width"]


def _left_right_spread(mask: np.ndarray, bbox: dict[str, float]) -> float:
    grid = np.asarray(mask, dtype=bool)
    if not np.any(grid):
        return 0.0
    ys, xs = np.nonzero(grid)
    center = bbox["center_x"]
    left = center - float(xs.min())
    right = float(xs.max()) - center
    denom = max(bbox["width"], 1.0)
    return (left + right) / denom


def _complexity_score(metrics: dict[str, int]) -> float:
    components = float(metrics.get("connected_component_count", 0))
    endpoints = float(metrics.get("endpoint_count", 0))
    branches = float(metrics.get("branch_point_count", 0))
    pixels = max(float(metrics.get("skeleton_pixel_count", 0)), 1.0)
    raw = 0.18 * max(components - 1.0, 0.0) + 0.018 * endpoints + 0.026 * branches + 0.00045 * pixels
    return round(min(raw, 1.0), 6)


def classify_constraint(
    constraint_name: str,
    value: float,
    style: str,
    component_count: int,
    endpoint_count: int,
    branch_count: int,
    complexity_score: float,
) -> dict[str, str]:
    """Classify a single font-reference constraint for future B adaptation use."""

    unsafe_names = {"raw_skeleton_path", "unordered_skeleton_segments", "complex_skeleton_graph"}
    visual_names = {
        "skeleton_component_count",
        "skeleton_endpoint_count",
        "skeleton_branch_count",
        "skeleton_complexity_score",
        "connectedness_hint",
    }
    usable_names = {"bbox_aspect", "lower_half_width_ratio", "left_right_spread", "bbox_center_shift_x", "bbox_center_shift_y"}

    if constraint_name in unsafe_names or complexity_score >= 0.75 or component_count > 3 or branch_count >= 35:
        return {
            "recommended_use": "unsafe_for_direct_use",
            "risk_level": "high",
            "confidence": "low",
            "note": "Do not drive point movement directly; requires manual audit and cleanup.",
        }
    if constraint_name in visual_names:
        confidence = "medium" if complexity_score < 0.55 else "low"
        return {
            "recommended_use": "visual_reference_only",
            "risk_level": "medium" if complexity_score < 0.55 else "high",
            "confidence": confidence,
            "note": "Use for complexity diagnosis and manual visual audit, not direct adaptation.",
        }
    if constraint_name in usable_names:
        if style == "kaishu" and component_count <= 2 and endpoint_count <= 12 and branch_count <= 20:
            confidence = "high"
            risk = "low"
        elif complexity_score < 0.55:
            confidence = "medium"
            risk = "medium"
        else:
            confidence = "low"
            risk = "medium"
        return {
            "recommended_use": "usable_for_adaptation",
            "risk_level": risk,
            "confidence": confidence,
            "note": "Use only as bounded, low-weight future B constraint; do not hard-pull points.",
        }
    return {
        "recommended_use": "visual_reference_only",
        "risk_level": "medium",
        "confidence": "low",
        "note": "Unrecognized constraint type; keep as diagnostic reference.",
    }


def _connectedness_hint(component_count: int, endpoint_count: int, branch_count: int) -> str:
    if component_count > 1:
        return "disconnected_or_multi_component"
    if branch_count >= 30:
        return "high_branch_complexity"
    if endpoint_count >= 16:
        return "many_endpoints"
    return "relatively_clean"


def _constraint_row(
    char: str,
    style: str,
    name: str,
    value: float | int | str,
    unit: str,
    component_count: int,
    endpoint_count: int,
    branch_count: int,
    complexity_score: float,
    source: str = "font_mask_skeleton",
) -> dict[str, Any]:
    numeric_value = float(value) if isinstance(value, (int, float, np.floating)) else 0.0
    classification = classify_constraint(
        name,
        numeric_value,
        style=style,
        component_count=component_count,
        endpoint_count=endpoint_count,
        branch_count=branch_count,
        complexity_score=complexity_score,
    )
    return {
        "char": char,
        "char_id": _char_id(char),
        "style": style,
        "constraint_name": name,
        "constraint_value": round(numeric_value, 6) if isinstance(value, (int, float, np.floating)) else value,
        "constraint_unit": unit,
        "source": source,
        **classification,
    }


def _draw_reference_figure(
    char: str,
    style: str,
    mask: np.ndarray,
    skeleton: np.ndarray,
    bbox: dict[str, float],
    lower_half_ratio: float,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.2), dpi=150)
    titles = ["font mask + bbox", "skeleton", "constraint guides"]
    for ax, title in zip(axes, titles):
        ax.set_title(title, fontsize=8)
        ax.imshow(np.where(mask, 0.88, 1.0), cmap="gray", vmin=0, vmax=1)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
    if bbox["width"] > 0:
        rect_x = bbox["x_min"]
        rect_y = bbox["y_min"]
        rect_w = bbox["width"]
        rect_h = bbox["height"]
        for ax in (axes[0], axes[2]):
            ax.add_patch(plt.Rectangle((rect_x, rect_y), rect_w, rect_h, fill=False, color="#1f77b4", linewidth=1.2))
        lower_y = bbox["y_min"] + bbox["height"] * 0.5
        lower_mask = mask & (np.indices(mask.shape)[0] >= lower_y)
        if np.any(lower_mask):
            ys, xs = np.nonzero(lower_mask)
            axes[2].add_patch(
                plt.Rectangle(
                    (float(xs.min()), float(ys.min())),
                    float(xs.max() - xs.min() + 1),
                    float(ys.max() - ys.min() + 1),
                    fill=False,
                    color="#d62728",
                    linewidth=1.2,
                )
            )
        axes[2].axvline(bbox["x_min"], color="#2ca02c", linewidth=0.8, alpha=0.8)
        axes[2].axvline(bbox["x_max"], color="#2ca02c", linewidth=0.8, alpha=0.8)
        axes[2].scatter([bbox["center_x"]], [bbox["center_y"]], color="#9467bd", s=12)
        axes[2].text(3, 12, f"aspect={bbox['aspect']:.3f}\nlower={lower_half_ratio:.3f}", fontsize=7, color="#333333")
    ys, xs = np.nonzero(skeleton)
    if len(xs):
        axes[1].scatter(xs, ys, s=0.7, color="#ff7f0e", alpha=0.9)
        axes[2].scatter(xs, ys, s=0.5, color="#ff7f0e", alpha=0.35)
    fig.suptitle(f"H2 font reference constraints {char} / {style}", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(path)
    plt.close(fig)


def _sample_constraints(
    char: str,
    style: str,
    style_sources: dict[str, Any],
    style_sources_dir: Path,
    figures_dir: Path,
    image_size: int,
    skeleton_method: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    font_path = first_existing_font(style_sources, style, style_sources_dir)
    if font_path is None:
        empty = np.zeros((image_size, image_size), dtype=bool)
        metrics = skeleton_metrics(empty)
        complexity = _complexity_score(metrics)
        bbox = _bbox(empty)
        lower_ratio = 0.0
        hint = "missing_font"
        warning = "missing_font"
        skeleton = empty
        mask = empty
    else:
        mask = render_char_with_font(char, font_path, image_size=image_size)
        skeleton_result = skeletonize_font_mask(mask, method=skeleton_method)
        skeleton = skeleton_result.skeleton
        metrics = skeleton_metrics(skeleton)
        complexity = _complexity_score(metrics)
        bbox = _bbox(mask)
        lower_ratio = _lower_half_width_ratio(mask, bbox)
        hint = _connectedness_hint(
            metrics["connected_component_count"],
            metrics["endpoint_count"],
            metrics["branch_point_count"],
        )
        warning = ";".join(skeleton_result.warnings)

    component_count = int(metrics["connected_component_count"])
    endpoint_count = int(metrics["endpoint_count"])
    branch_count = int(metrics["branch_point_count"])
    left_right_spread = _left_right_spread(mask, bbox)
    center_shift_x = (bbox["center_x"] - image_size / 2.0) / image_size if image_size else 0.0
    center_shift_y = (bbox["center_y"] - image_size / 2.0) / image_size if image_size else 0.0

    constraint_specs: list[tuple[str, float | int | str, str, str]] = [
        ("bbox_aspect", bbox["aspect"], "ratio", "font_mask"),
        ("lower_half_width_ratio", lower_ratio, "ratio", "font_mask"),
        ("left_right_spread", left_right_spread, "ratio", "font_mask"),
        ("bbox_center_shift_x", center_shift_x, "normalized_image", "font_mask"),
        ("bbox_center_shift_y", center_shift_y, "normalized_image", "font_mask"),
        ("skeleton_component_count", component_count, "count", "font_skeleton"),
        ("skeleton_endpoint_count", endpoint_count, "count", "font_skeleton"),
        ("skeleton_branch_count", branch_count, "count", "font_skeleton"),
        ("skeleton_complexity_score", complexity, "score_0_1", "font_skeleton"),
        ("connectedness_hint", hint, "category", "font_skeleton"),
        ("raw_skeleton_path", 1.0, "presence_flag", "font_skeleton"),
        ("unordered_skeleton_segments", 1.0, "presence_flag", "font_skeleton"),
    ]
    constraints = [
        _constraint_row(
            char,
            style,
            name,
            value,
            unit,
            component_count,
            endpoint_count,
            branch_count,
            complexity,
            source=source,
        )
        for name, value, unit, source in constraint_specs
    ]
    counts = Counter(row["recommended_use"] for row in constraints)
    if counts["usable_for_adaptation"] >= 3 and counts["unsafe_for_direct_use"] <= 2 and complexity < 0.65:
        overall = "candidate_for_bounded_B_adaptation"
    elif counts["unsafe_for_direct_use"] >= 3 or complexity >= 0.75:
        overall = "visual_reference_only_high_risk"
    else:
        overall = "visual_reference_with_limited_constraints"

    figure_path = figures_dir / f"constraint_reference_{_char_id(char)}_{style}.png"
    _draw_reference_figure(char, style, mask, skeleton, bbox, lower_ratio, figure_path)
    summary = {
        "char": char,
        "char_id": _char_id(char),
        "style": style,
        "bbox_aspect": round(float(bbox["aspect"]), 6),
        "lower_half_width_ratio": round(float(lower_ratio), 6),
        "left_right_spread": round(float(left_right_spread), 6),
        "bbox_center_shift_x": round(float(center_shift_x), 6),
        "bbox_center_shift_y": round(float(center_shift_y), 6),
        "skeleton_component_count": component_count,
        "skeleton_endpoint_count": endpoint_count,
        "skeleton_branch_count": branch_count,
        "skeleton_complexity_score": complexity,
        "connectedness_hint": hint,
        "usable_constraint_count": counts["usable_for_adaptation"],
        "visual_reference_only_count": counts["visual_reference_only"],
        "unsafe_constraint_count": counts["unsafe_for_direct_use"],
        "overall_recommendation": overall,
    }
    manifest = {
        "char": char,
        "char_id": _char_id(char),
        "style": style,
        "figure_path": str(figure_path),
        "overall_recommendation": overall,
        "note": warning,
    }
    sample_json = {
        "char": char,
        "char_id": _char_id(char),
        "style": style,
        "font_path": str(font_path) if font_path else "",
        "overall_recommendation": overall,
        "warnings": [item for item in warning.split(";") if item],
        "constraints": {
            row["constraint_name"]: {
                "value": row["constraint_value"],
                "unit": row["constraint_unit"],
                "source": row["source"],
                "confidence": row["confidence"],
                "recommended_use": row["recommended_use"],
                "risk_level": row["risk_level"],
                "note": row["note"],
            }
            for row in constraints
        },
    }
    return summary, constraints, manifest, sample_json


def _write_report(
    path: Path,
    output_dir: Path,
    summaries: Sequence[dict[str, Any]],
    constraint_rows: Sequence[dict[str, Any]],
) -> None:
    use_counts = Counter(row["recommended_use"] for row in constraint_rows)
    by_style: dict[str, list[dict[str, Any]]] = {}
    for row in summaries:
        by_style.setdefault(str(row["style"]), []).append(row)

    lines = [
        "# Font Reference Constraints Package",
        "",
        "H2 purpose: extract interpretable font mask / skeleton constraints as a reference package only. 本轮不移动轨迹点，不生成 adapted trajectory，不生成正式 trajectory.csv，不接默认 pipeline。",
        "",
        f"- output_dir: `{output_dir.resolve()}`",
        "- status: `reference_constraints_only_not_used_by_default`",
        "- scope: kaishu / lishu representative samples only; xingkai and complex broad samples are excluded.",
        "",
        "## Constraint use counts",
        "",
        "| recommended_use | count |",
        "|---|---:|",
    ]
    for key in ["usable_for_adaptation", "visual_reference_only", "unsafe_for_direct_use"]:
        lines.append(f"| {key} | {use_counts.get(key, 0)} |")

    lines.extend(["", "## Summary by sample", "", "| char | style | aspect | lower_half_width_ratio | complexity | usable | visual | unsafe | recommendation |", "|---|---|---:|---:|---:|---:|---:|---:|---|"])
    for row in summaries:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['bbox_aspect']:.3f} | "
            f"{row['lower_half_width_ratio']:.3f} | {row['skeleton_complexity_score']:.3f} | "
            f"{row['usable_constraint_count']} | {row['visual_reference_only_count']} | {row['unsafe_constraint_count']} | "
            f"{row['overall_recommendation']} |"
        )

    lines.extend(["", "## Style-level notes", ""])
    for style, rows in sorted(by_style.items()):
        avg_complexity = sum(float(row["skeleton_complexity_score"]) for row in rows) / max(len(rows), 1)
        usable = sum(int(row["usable_constraint_count"]) for row in rows)
        unsafe = sum(int(row["unsafe_constraint_count"]) for row in rows)
        lines.append(f"- `{style}`: samples={len(rows)}, avg_complexity={avg_complexity:.3f}, usable_constraints={usable}, unsafe_constraints={unsafe}.")

    lines.extend(
        [
            "",
            "## Usable for future B adaptation",
            "",
            "- `bbox_aspect`: usable only as bounded low-weight width/height hint.",
            "- `lower_half_width_ratio`: useful for lishu lower support diagnostics, especially simple characters such as 山.",
            "- `left_right_spread`: useful as a soft spread hint; must not hard-pull points.",
            "- `bbox_center_shift_x/y`: only safe for tiny centering adjustments.",
            "",
            "## Visual reference only",
            "",
            "- `skeleton_component_count`, `skeleton_endpoint_count`, `skeleton_branch_count`, `skeleton_complexity_score`, and `connectedness_hint` are complexity and audit signals.",
            "- These fields should guide manual review and future constraint selection, not direct point movement.",
            "",
            "## Unsafe for direct use",
            "",
            "- `raw_skeleton_path` and `unordered_skeleton_segments` are explicitly marked unsafe.",
            "- High-branch, disconnected, or complex skeleton graphs must not drive trajectory deformation without cleanup, ordering, and manual audit.",
            "",
            "## Next B adaptation suggestion",
            "",
            "Use this package to choose a small set of low-risk constraints before any future B prototype. Prefer bounded `bbox_aspect`, `lower_half_width_ratio`, and `left_right_spread` over raw skeleton paths. Do not connect these constraints to `run_demo.py` or execution/robot files until a future explicit promotion task.",
            "",
            "## Boundary",
            "",
            "This package is reference-only and not used by default. It does not alter `style_profiles.json`, does not change `run_demo.py`, does not create adapted or formal trajectory files, and does not call API/CoppeliaSim/AUBO/SDK.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, samples: Sequence[dict[str, Any]]) -> None:
    payload = {
        "status": "reference_constraints_only_not_used_by_default",
        "date": "2026-06-19",
        "default_pipeline_integration": False,
        "adapted_trajectory_generated": False,
        "formal_trajectory_generated": False,
        "scope": "H2 font reference constraints package for hybrid route; no point movement",
        "samples": list(samples),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_paper_index(index_path: Path, output_dir: Path) -> None:
    lines = [
        "# Font Reference Constraints Package Index",
        "",
        f"- source_output_dir: `{output_dir.resolve()}`",
        "- Hybrid route H2: A median + C font reference constraints only.",
        "- Status: reference constraints only, not used by default.",
        "- Boundary: no trajectory movement, no adapted CSV, no execution/workspace/robot files.",
        "",
        "| file | content |",
        "|---|---|",
        "| `font_reference_constraints_report.md` | H2 report and next B-adaptation guidance |",
        "| `font_reference_constraints.json` | machine-readable constraints package |",
        "| `font_reference_constraints.csv` | one row per constraint |",
        "| `font_reference_constraints_summary.csv` | one row per char/style sample |",
        "| `font_reference_constraints_manifest.csv` | figure manifest |",
    ]
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_font_reference_constraints_package(
    output_dir: Path | str | None = None,
    samples: Sequence[tuple[str, str]] | None = None,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    image_size: int = 256,
    skeleton_method: str = "auto",
    copy_to_paper: bool = True,
) -> dict[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"font_reference_constraints_{timestamp}"
    figures_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    style_sources_path = Path(style_sources_path)
    style_sources = _read_json(style_sources_path)
    selected_samples = list(samples or DEFAULT_SAMPLES)

    summaries: list[dict[str, Any]] = []
    constraint_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    sample_json_rows: list[dict[str, Any]] = []
    for char, style in selected_samples:
        if style not in {"kaishu", "lishu"}:
            continue
        summary, constraints, manifest, sample_json = _sample_constraints(
            char=char,
            style=style,
            style_sources=style_sources,
            style_sources_dir=style_sources_path.parent,
            figures_dir=figures_dir,
            image_size=image_size,
            skeleton_method=skeleton_method,
        )
        summaries.append(summary)
        constraint_rows.extend(constraints)
        manifest_rows.append(manifest)
        sample_json_rows.append(sample_json)

    constraints_csv = out_dir / "font_reference_constraints.csv"
    constraints_json = out_dir / "font_reference_constraints.json"
    summary_csv = out_dir / "font_reference_constraints_summary.csv"
    report_md = out_dir / "font_reference_constraints_report.md"
    manifest_csv = out_dir / "font_reference_constraints_manifest.csv"

    _write_csv(constraints_csv, constraint_rows, CONSTRAINT_FIELDS)
    _write_csv(summary_csv, summaries, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_json(constraints_json, sample_json_rows)
    _write_report(report_md, out_dir, summaries, constraint_rows)

    paper_index = ""
    if copy_to_paper:
        DEFAULT_PAPER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "font_reference_constraints_report.md")
        shutil.copy2(constraints_json, DEFAULT_PAPER_DIR / "font_reference_constraints.json")
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "font_reference_constraints_summary.csv")
        index_path = DEFAULT_PAPER_DIR / "font_reference_constraints_index.md"
        _write_paper_index(index_path, out_dir)
        paper_index = str(index_path)

    return {
        "output_dir": str(out_dir),
        "constraints_csv": str(constraints_csv),
        "constraints_json": str(constraints_json),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "figures_dir": str(figures_dir),
        "paper_index": paper_index,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build H2 font-reference constraints package")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--style-sources", default=str(DEFAULT_STYLE_SOURCES))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--skeleton-method", choices=["auto", "skimage", "opencv", "ridge"], default="auto")
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args()
    result = run_font_reference_constraints_package(
        output_dir=Path(args.out_dir) if args.out_dir else None,
        style_sources_path=Path(args.style_sources),
        image_size=args.image_size,
        skeleton_method=args.skeleton_method,
        copy_to_paper=not args.no_copy_to_paper,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
