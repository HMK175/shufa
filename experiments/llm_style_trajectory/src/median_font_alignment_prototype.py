"""Median-to-font skeleton alignment/adaptation prototype.

This module explores a B-route alternative to pure font-skeleton trajectory
generation: keep MakeMeAHanzi median stroke order and softly pull median points
toward a cleaned font skeleton reference. It is diagnostic only and does not
write formal trajectory.csv, execution, workspace, CoppeliaSim, or robot files.
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
from trajectory_tools import normalize_medians


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_STYLE_SOURCES = EXP_DIR / "configs" / "style_sources.json"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
DEFAULT_SAMPLE_SPECS = [
    ("\u4eba", "kaishu"),  # 人
    ("\u5c71", "lishu"),  # 山
]
DEFAULT_ALPHA_VALUES = [0.25, 0.5]

TRIAL_FIELDS = ["y", "x", "stroke_id", "point_index", "is_break", "alpha", "source"]
SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "sample_dir",
    "summary_json",
    "compare_png",
    "stroke_count",
    "point_count",
    "alpha_values",
    "mean_projection_distance_px_before",
    "mean_projection_distance_px_after_025",
    "mean_projection_distance_px_after_050",
    "max_point_shift_px_025",
    "max_point_shift_px_050",
    "bbox_aspect_median",
    "bbox_aspect_font",
    "bbox_aspect_adapted_025",
    "bbox_aspect_adapted_050",
    "warning",
    "recommended_for_next_stage",
]
MANIFEST_FIELDS = [
    "char",
    "char_id",
    "style",
    "sample_dir",
    "alpha",
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


def _alpha_label(alpha: float) -> str:
    return f"{int(round(alpha * 100)):03d}"


def _bbox_aspect_from_points(points: np.ndarray) -> float:
    arr = np.asarray(points, dtype=float)
    if len(arr) == 0:
        return 0.0
    y0, x0 = np.min(arr, axis=0)
    y1, x1 = np.max(arr, axis=0)
    height = float(y1 - y0)
    width = float(x1 - x0)
    return round(width / height if height > 1e-9 else 0.0, 6)


def _bbox_aspect_from_mask(mask: np.ndarray) -> float:
    grid = np.asarray(mask, dtype=bool)
    if not np.any(grid):
        return 0.0
    ys, xs = np.nonzero(grid)
    height = float(ys.max() - ys.min() + 1)
    width = float(xs.max() - xs.min() + 1)
    return round(width / height if height > 1e-9 else 0.0, 6)


def _flatten_strokes(strokes: Sequence[np.ndarray]) -> np.ndarray:
    parts = [np.asarray(stroke, dtype=float) for stroke in strokes if len(stroke)]
    if not parts:
        return np.empty((0, 2), dtype=float)
    return np.vstack(parts)


def _reference_points(skeleton: np.ndarray, mask: np.ndarray) -> np.ndarray:
    skeleton = np.asarray(skeleton, dtype=bool)
    mask = np.asarray(mask, dtype=bool)
    if np.any(skeleton):
        ys, xs = np.nonzero(skeleton)
    else:
        ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return np.empty((0, 2), dtype=float)
    return np.column_stack([ys.astype(float), xs.astype(float)])


def _nearest_reference(points: np.ndarray, reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    pts = np.asarray(points, dtype=float)
    ref = np.asarray(reference, dtype=float)
    if len(pts) == 0 or len(ref) == 0:
        return pts.copy(), np.full((len(pts),), float("inf"))
    nearest = np.empty_like(pts)
    distances = np.empty((len(pts),), dtype=float)
    for idx, point in enumerate(pts):
        diff = ref - point
        dist = np.linalg.norm(diff, axis=1)
        best = int(np.argmin(dist))
        nearest[idx] = ref[best]
        distances[idx] = float(dist[best])
    return nearest, distances


def adapt_strokes_to_reference(
    strokes: Sequence[Sequence[Sequence[float]] | np.ndarray],
    reference_points: Sequence[Sequence[float]] | np.ndarray,
    alpha: float,
    max_shift_px: float = 15.0,
    max_snap_distance_px: float = 45.0,
) -> tuple[list[np.ndarray], dict[str, float]]:
    """Softly project median points toward reference points without reordering.

    Stroke count and point order are preserved. Points with a distant nearest
    reference are moved only by a capped step toward that reference.
    """

    ref = np.asarray(reference_points, dtype=float)
    adapted: list[np.ndarray] = []
    before_distances: list[float] = []
    after_distances: list[float] = []
    shifts: list[float] = []
    for stroke in strokes:
        pts = np.asarray(stroke, dtype=float)
        nearest, before = _nearest_reference(pts, ref)
        delta = nearest - pts
        raw_shift = delta * float(alpha)
        shift_len = np.linalg.norm(raw_shift, axis=1)
        limited = raw_shift.copy()
        for idx, length in enumerate(shift_len):
            nearest_dist = before[idx]
            if not math.isfinite(nearest_dist) or nearest_dist > max_snap_distance_px:
                scale = min(0.25, max_shift_px / max(nearest_dist, 1e-9))
                limited[idx] = delta[idx] * float(alpha) * scale
            elif length > max_shift_px:
                limited[idx] = raw_shift[idx] * (max_shift_px / max(length, 1e-9))
        out = pts + limited
        _, after = _nearest_reference(out, ref)
        adapted.append(out)
        before_distances.extend(float(v) for v in before if math.isfinite(float(v)))
        after_distances.extend(float(v) for v in after if math.isfinite(float(v)))
        shifts.extend(float(np.linalg.norm(v)) for v in limited)
    return adapted, {
        "mean_projection_distance_px_before": round(float(np.mean(before_distances)) if before_distances else 0.0, 6),
        "mean_projection_distance_px_after": round(float(np.mean(after_distances)) if after_distances else 0.0, 6),
        "max_point_shift_px": round(float(max(shifts)) if shifts else 0.0, 6),
    }


def _write_trial_csv(path: Path, strokes: Sequence[np.ndarray], alpha: float) -> tuple[int, int]:
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
                    "alpha": alpha,
                    "source": "median_font_alignment_trial",
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
                "alpha": alpha,
                "source": "median_font_alignment_trial",
            }
        )
        break_count += 1
    _write_csv(path, rows, TRIAL_FIELDS)
    return point_count, break_count


def _draw_strokes(ax: Any, strokes: Sequence[np.ndarray], color: str, title: str, linewidth: float = 1.5) -> None:
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.invert_yaxis()
    for idx, stroke in enumerate(strokes, start=1):
        pts = np.asarray(stroke, dtype=float)
        if len(pts) < 2:
            continue
        ax.plot(pts[:, 1], pts[:, 0], color=color, linewidth=linewidth)
        ax.scatter(pts[0, 1], pts[0, 0], s=8, color=color)
        mid = pts[len(pts) // 2]
        ax.text(mid[1], mid[0], str(idx), fontsize=7, color="#111111")


def _write_compare_figure(
    char: str,
    style: str,
    median_strokes: Sequence[np.ndarray],
    mask: np.ndarray,
    skeleton: np.ndarray,
    adapted_by_alpha: dict[str, list[np.ndarray]],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 4, figsize=(12.5, 3.4), dpi=150)
    _draw_strokes(axes[0], median_strokes, "#333333", "MakeMeAHanzi median")

    axes[1].set_title("font mask + cleaned skeleton", fontsize=8)
    axes[1].imshow(np.where(mask, 0.88, 1.0), cmap="gray", vmin=0, vmax=1)
    ys, xs = np.nonzero(skeleton)
    axes[1].scatter(xs, ys, s=0.7, color="#1f77b4", alpha=0.9)
    axes[1].set_aspect("equal")
    axes[1].set_xticks([])
    axes[1].set_yticks([])

    _draw_strokes(axes[2], adapted_by_alpha.get("0.25", []), "#d62728", "adapted alpha=0.25", linewidth=1.7)
    _draw_strokes(axes[3], adapted_by_alpha.get("0.5", []), "#2ca02c", "adapted alpha=0.5", linewidth=1.7)

    for ax in axes:
        ax.set_xlim(0, mask.shape[1])
        ax.set_ylim(mask.shape[0], 0)
    fig.suptitle(f"{_char_id(char)} / {style} median-to-font alignment prototype", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(path)
    plt.close(fig)


def _write_report(path: Path, output_dir: Path, rows: Sequence[dict[str, Any]]) -> None:
    lines = [
        "# Median-to-font skeleton alignment / adaptation prototype",
        "",
        "本轮是 B 路线：`median + font skeleton` 融合，而不是纯 skeleton -> trajectory。",
        "",
        "## 边界说明",
        "",
        "- 保留 MakeMeAHanzi stroke order 和 stroke break。",
        "- 不恢复真实笔顺，不重排笔顺，不改变 stroke 数量。",
        "- 不生成正式 `trajectory.csv`，只输出 `adapted_trial_alpha_*.csv`。",
        "- 不接机器人，不生成 execution/workspace/CoppeliaSim/AUBO 文件。",
        "- 只用于判断字体参考能否改善风格形态。",
        "",
        "## 输出目录",
        "",
        f"`{output_dir}`",
        "",
        "## 样本结果",
        "",
        "| char | style | stroke_count | alpha=0.25 distance | alpha=0.5 distance | max_shift_0.25 | max_shift_0.5 | warning | recommended | compare |",
        "|---|---|---:|---:|---:|---:|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {char} | {style} | {stroke_count} | {mean_projection_distance_px_after_025} | "
            "{mean_projection_distance_px_after_050} | {max_point_shift_px_025} | {max_point_shift_px_050} | "
            "{warning} | {recommended_for_next_stage} | `{compare_png}` |".format(**row)
        )
    lines.extend(
        [
            "",
            "## 人工看图问题",
            "",
            "- adapted 轨迹是否比原 median 更接近字体风格？",
            "- 是否仍保留可写性和笔顺结构？",
            "- alpha=0.25 是否比 alpha=0.5 更稳？",
            "- 山/lishu 是否比单纯横向压扁更有隶书感？",
            "- 人/kaishu 是否没有被过度扭曲？",
            "",
            "## 初步建议",
            "",
            "如果人工看图确认 alpha=0.25 在保持可写性的同时提升字体贴近度，可以进入 median-font adaptation v2；",
            "alpha=0.5 仅作为更强吸附对照，若出现过度扭曲，应优先保守使用更小 alpha 或 stroke-aware 限制。",
        ]
    )
    lines.extend(
        [
            "",
            "## Visual QA note",
            "",
            "- `人/kaishu`: alpha=0.25 and alpha=0.5 keep the two-stroke structure; the adaptation improves local skeleton proximity without obvious over-warping.",
            "- `山/lishu`: projection distance decreases, but the global form still follows the MakeMeAHanzi three-stroke median more than the wide-bottom lishu font outline. A v2 should add stroke-level bbox or anchor alignment, not only nearest-neighbor point attraction.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(paper_dir: Path, output_dir: Path, summary_csv: Path, report_md: Path, rows: Sequence[dict[str, Any]]) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    index_path = paper_dir / "median_font_alignment_index.md"
    lines = [
        "# Median-to-font skeleton alignment prototype index",
        "",
        "本索引固定 B 路线 very small-sample median-to-font skeleton alignment / adaptation prototype 的结果。",
        "",
        "## Source",
        "",
        f"- Output directory: `{output_dir}`",
        f"- Summary: `{summary_csv}`",
        f"- Report: `{report_md}`",
        "",
        "## Samples",
        "",
        "| char | style | stroke_count | alpha=0.25 distance | alpha=0.5 distance | compare |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['stroke_count']} | "
            f"{row['mean_projection_distance_px_after_025']} | {row['mean_projection_distance_px_after_050']} | "
            f"`{row['compare_png']}` |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "该结果是 median + font skeleton 融合诊断，不是纯 skeleton 轨迹，不是真实笔顺恢复，不生成正式 trajectory.csv，也不接机器人。",
        ]
    )
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index_path


def _style_font(style_sources_path: Path, style: str) -> Path | None:
    style_sources = _load_json(style_sources_path)
    return first_existing_font(style_sources, style, style_sources_path.parent)


def _process_sample(
    char: str,
    style: str,
    output_dir: Path,
    style_sources_path: Path,
    image_size: int,
    skeleton_method: str,
    alpha_values: Sequence[float],
    max_shift_px: float,
    max_snap_distance_px: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sample_dir = output_dir / f"{_char_id(char)}_{style}"
    sample_dir.mkdir(parents=True, exist_ok=True)

    knowledge = MakeMeAHanziKnowledge(DEFAULT_GRAPHICS)
    glyph = knowledge.get_glyph(char)
    median_strokes = list(normalize_medians(glyph.medians, image_size=image_size))
    font_path = _style_font(style_sources_path, style)
    warnings: list[str] = []
    if font_path is None:
        warnings.append("missing_font")
        mask = np.zeros((image_size, image_size), dtype=bool)
        clean_skeleton = np.zeros_like(mask)
    else:
        mask = render_char_with_font(char, font_path, image_size=image_size)
        skeleton_result = skeletonize_font_mask(mask, method=skeleton_method)
        clean_skeleton, cleanup_info = cleanup_skeleton(
            skeleton_result.skeleton,
            min_component_pixels=12,
            spur_prune_length=6,
            endpoint_merge_distance=3,
        )
        warnings.extend(skeleton_result.warnings)
        if not np.any(clean_skeleton):
            warnings.append("empty_clean_skeleton")
        if cleanup_info.get("removed_component_count", 0):
            warnings.append(f"removed_components:{cleanup_info['removed_component_count']}")

    reference = _reference_points(clean_skeleton, mask)
    median_points = _flatten_strokes(median_strokes)
    before_nearest, before_dist = _nearest_reference(median_points, reference)
    before_mean = round(float(np.mean(before_dist[np.isfinite(before_dist)])) if len(before_dist) else 0.0, 6)
    adapted_by_alpha: dict[str, list[np.ndarray]] = {}
    after_distances: dict[str, float] = {}
    max_shifts: dict[str, float] = {}
    aspects: dict[str, float] = {}
    manifest_rows: list[dict[str, Any]] = []
    point_count = int(sum(len(stroke) for stroke in median_strokes))

    for alpha in alpha_values:
        adapted, metrics = adapt_strokes_to_reference(
            median_strokes,
            reference,
            alpha=float(alpha),
            max_shift_px=max_shift_px,
            max_snap_distance_px=max_snap_distance_px,
        )
        label = str(float(alpha)).rstrip("0").rstrip(".")
        adapted_by_alpha[label] = adapted
        after_distances[label] = float(metrics["mean_projection_distance_px_after"])
        max_shifts[label] = float(metrics["max_point_shift_px"])
        aspects[label] = _bbox_aspect_from_points(_flatten_strokes(adapted))
        trial_csv = sample_dir / f"adapted_trial_alpha_{_alpha_label(float(alpha))}.csv"
        _write_trial_csv(trial_csv, adapted, float(alpha))
        manifest_rows.append(
            {
                "char": char,
                "char_id": _char_id(char),
                "style": style,
                "sample_dir": str(sample_dir),
                "alpha": alpha,
                "trial_csv": str(trial_csv),
                "compare_png": str(sample_dir / "median_font_alignment_compare.png"),
                "warning": ";".join(warnings),
            }
        )

    compare_png = sample_dir / "median_font_alignment_compare.png"
    _write_compare_figure(char, style, median_strokes, mask, clean_skeleton, adapted_by_alpha, compare_png)

    recommended = bool(reference.size) and after_distances.get("0.25", before_mean) < before_mean
    summary = {
        "char": char,
        "char_id": _char_id(char),
        "style": style,
        "stroke_count": len(median_strokes),
        "adapted_stroke_count": len(median_strokes),
        "point_count": point_count,
        "alpha_values": list(alpha_values),
        "mean_projection_distance_px_before": before_mean,
        "mean_projection_distance_px_after": after_distances,
        "max_point_shift_px": max_shifts,
        "bbox_aspect_median": _bbox_aspect_from_points(median_points),
        "bbox_aspect_font": _bbox_aspect_from_mask(mask),
        "bbox_aspect_adapted": aspects,
        "warning": ";".join(warnings),
        "recommended_for_next_stage": recommended,
        "font_path": str(font_path) if font_path else "",
        "scope": "diagnostic median-font alignment trial only; not formal trajectory; no robot",
    }
    summary_json = sample_dir / "median_font_alignment_summary.json"
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
        "alpha_values": ";".join(str(v) for v in alpha_values),
        "mean_projection_distance_px_before": before_mean,
        "mean_projection_distance_px_after_025": after_distances.get("0.25", ""),
        "mean_projection_distance_px_after_050": after_distances.get("0.5", ""),
        "max_point_shift_px_025": max_shifts.get("0.25", ""),
        "max_point_shift_px_050": max_shifts.get("0.5", ""),
        "bbox_aspect_median": summary["bbox_aspect_median"],
        "bbox_aspect_font": summary["bbox_aspect_font"],
        "bbox_aspect_adapted_025": aspects.get("0.25", ""),
        "bbox_aspect_adapted_050": aspects.get("0.5", ""),
        "warning": summary["warning"],
        "recommended_for_next_stage": recommended,
    }
    return row, manifest_rows


def run_median_font_alignment(
    output_dir: Path | str | None = None,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    sample_specs: Sequence[tuple[str, str]] = DEFAULT_SAMPLE_SPECS,
    image_size: int = 256,
    skeleton_method: str = "auto",
    alpha_values: Sequence[float] = DEFAULT_ALPHA_VALUES,
    max_shift_px: float = 15.0,
    max_snap_distance_px: float = 45.0,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"median_font_alignment_{timestamp}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    style_sources_path = Path(style_sources_path)

    summary_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for char, style in sample_specs:
        row, sample_manifest = _process_sample(
            char=char,
            style=style,
            output_dir=output_dir,
            style_sources_path=style_sources_path,
            image_size=image_size,
            skeleton_method=skeleton_method,
            alpha_values=alpha_values,
            max_shift_px=max_shift_px,
            max_snap_distance_px=max_snap_distance_px,
        )
        summary_rows.append(row)
        manifest_rows.extend(sample_manifest)

    summary_csv = output_dir / "median_font_alignment_summary.csv"
    manifest_csv = output_dir / "median_font_alignment_manifest.csv"
    report_md = output_dir / "median_font_alignment_report.md"
    _write_csv(summary_csv, summary_rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, output_dir, summary_rows)

    paper_index = ""
    if copy_to_paper:
        paper_index_path = _write_paper_index(DEFAULT_PAPER_DIR, output_dir, summary_csv, report_md, summary_rows)
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "median_font_alignment_report.md")
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "median_font_alignment_summary.csv")
        paper_index = str(paper_index_path)

    return {
        "output_dir": str(output_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "paper_index": paper_index,
        "rows": summary_rows,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--style-sources", type=Path, default=DEFAULT_STYLE_SOURCES)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--skeleton-method", choices=["auto", "skimage", "opencv", "ridge"], default="auto")
    parser.add_argument("--alpha-values", nargs="+", type=float, default=DEFAULT_ALPHA_VALUES)
    parser.add_argument("--max-shift-px", type=float, default=15.0)
    parser.add_argument("--max-snap-distance-px", type=float, default=45.0)
    parser.add_argument("--no-paper-copy", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_median_font_alignment(
        output_dir=args.out_dir,
        style_sources_path=args.style_sources,
        image_size=args.image_size,
        skeleton_method=args.skeleton_method,
        alpha_values=args.alpha_values,
        max_shift_px=args.max_shift_px,
        max_snap_distance_px=args.max_snap_distance_px,
        copy_to_paper=not args.no_paper_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
