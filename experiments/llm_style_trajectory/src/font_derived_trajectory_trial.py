"""Minimal font-derived trajectory trial for selected low-risk samples.

This module turns previously prototyped font skeleton path segments into
candidate trial trajectories for visual inspection only. It does not write a
formal trajectory.csv, execution trajectory, robot workspace file, or connect to
the default MakeMeAHanzi-based pipeline.
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
from font_skeleton_path_extraction_prototype import (
    PathExtractionResult,
    PathSegment,
    extract_path_segments,
)
from knowledge import MakeMeAHanziKnowledge
from trajectory_tools import normalize_medians


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_PATH_EXTRACTION_DIR = EXP_DIR / "outputs" / "font_skeleton_path_extraction_20260619_123527"
DEFAULT_STYLE_SOURCES = EXP_DIR / "configs" / "style_sources.json"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
DEFAULT_SAMPLE_SPECS = [
    ("\u5c71", "kaishu"),  # 山
    ("\u4eba", "kaishu"),  # 人
    ("\u5c71", "lishu"),  # 山
]

TRIAL_FIELDS = ["y", "x", "segment_id", "point_index", "is_break", "source"]
SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "sample_dir",
    "trial_csv",
    "summary_json",
    "compare_png",
    "segment_count",
    "point_count",
    "break_count",
    "total_path_length_px",
    "median_path_length_px",
    "bbox_width",
    "bbox_height",
    "aspect_ratio",
    "recommended_for_visual_followup",
    "warning",
]
MANIFEST_FIELDS = ["char", "char_id", "style", "sample_dir", "trial_csv", "compare_png", "warning"]


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


def _median_strokes(char: str, image_size: int) -> list[np.ndarray]:
    knowledge = MakeMeAHanziKnowledge(DEFAULT_GRAPHICS)
    glyph = knowledge.get_glyph(char)
    return list(normalize_medians(glyph.medians, image_size=image_size))


def _path_length(points: Sequence[tuple[float, float]] | np.ndarray) -> float:
    arr = np.asarray(points, dtype=float)
    if len(arr) < 2:
        return 0.0
    total = 0.0
    for p0, p1 in zip(arr[:-1], arr[1:]):
        total += math.hypot(float(p1[0] - p0[0]), float(p1[1] - p0[1]))
    return total


def _median_path_length(strokes: Sequence[np.ndarray]) -> float:
    return round(sum(_path_length(stroke) for stroke in strokes), 6)


def _trial_bbox(segments: Sequence[PathSegment]) -> dict[str, float]:
    pts: list[tuple[float, float]] = []
    for segment in segments:
        pts.extend((float(y), float(x)) for y, x in segment.points)
    if not pts:
        return {"bbox_width": 0.0, "bbox_height": 0.0, "aspect_ratio": 0.0}
    arr = np.asarray(pts, dtype=float)
    y0, x0 = arr.min(axis=0)
    y1, x1 = arr.max(axis=0)
    width = float(x1 - x0)
    height = float(y1 - y0)
    return {
        "bbox_width": round(width, 6),
        "bbox_height": round(height, 6),
        "aspect_ratio": round(width / height if height > 1e-9 else 0.0, 6),
    }


def _write_trial_csv(path: Path, segments: Sequence[PathSegment]) -> tuple[int, int]:
    rows: list[dict[str, Any]] = []
    point_count = 0
    break_count = 0
    for segment in segments:
        for point_index, (y, x) in enumerate(segment.points):
            rows.append(
                {
                    "y": float(y),
                    "x": float(x),
                    "segment_id": segment.order_index,
                    "point_index": point_index,
                    "is_break": 0,
                    "source": "font_skeleton_trial",
                }
            )
            point_count += 1
        rows.append(
            {
                "y": "nan",
                "x": "nan",
                "segment_id": segment.order_index,
                "point_index": "",
                "is_break": 1,
                "source": "font_skeleton_trial",
            }
        )
        break_count += 1
    _write_csv(path, rows, TRIAL_FIELDS)
    return point_count, break_count


def _draw_median(ax: Any, strokes: Sequence[np.ndarray], image_size: int) -> None:
    ax.set_xlim(0, image_size)
    ax.set_ylim(image_size, 0)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(True, color="#eeeeee", linewidth=0.4)
    for stroke in strokes:
        pts = np.asarray(stroke, dtype=float)
        if len(pts):
            ax.plot(pts[:, 1], pts[:, 0], color="#333333", linewidth=1.4)


def _draw_segments(ax: Any, result: PathExtractionResult) -> None:
    colors = plt.cm.tab20(np.linspace(0, 1, max(1, min(20, len(result.segments)))))
    for idx, segment in enumerate(result.segments):
        points = np.asarray(segment.points, dtype=float)
        if len(points) < 2:
            continue
        color = colors[idx % len(colors)]
        ax.plot(points[:, 1], points[:, 0], linewidth=1.4, color=color)
        mid = points[len(points) // 2]
        ax.text(mid[1], mid[0], str(segment.order_index), fontsize=6, color="#111111")


def _write_compare_figure(
    char: str,
    style: str,
    median_strokes: Sequence[np.ndarray],
    mask: np.ndarray,
    raw_skeleton: np.ndarray,
    clean_skeleton: np.ndarray,
    result: PathExtractionResult,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_y, raw_x = np.nonzero(raw_skeleton)
    clean_y, clean_x = np.nonzero(clean_skeleton)
    fig, axes = plt.subplots(2, 3, figsize=(10.8, 7.0), dpi=150)
    flat = axes.ravel()
    titles = [
        "MakeMeAHanzi median",
        "font mask",
        "raw font skeleton",
        "cleaned skeleton",
        "extracted path segments",
        "font-derived trial trajectory",
    ]
    for ax, title in zip(flat, titles):
        ax.set_title(title, fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect("equal")
    _draw_median(flat[0], median_strokes, mask.shape[0])
    for idx in [1, 2, 3, 4, 5]:
        flat[idx].imshow(np.where(mask, 0.88, 1.0), cmap="gray", vmin=0, vmax=1)
    flat[2].scatter(raw_x, raw_y, s=0.7, color="#d62728", alpha=0.85)
    flat[3].scatter(clean_x, clean_y, s=0.7, color="#1f77b4", alpha=0.85)
    flat[4].scatter(clean_x, clean_y, s=0.35, color="#bdbdbd", alpha=0.4)
    flat[5].scatter(clean_x, clean_y, s=0.25, color="#d9d9d9", alpha=0.35)
    _draw_segments(flat[4], result)
    _draw_segments(flat[5], result)
    fig.suptitle(f"{_char_id(char)} / {style} font-derived trajectory trial", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(path)
    plt.close(fig)


def _process_sample(
    char: str,
    style: str,
    out_dir: Path,
    style_sources: dict[str, Any],
    style_sources_dir: Path,
    image_size: int,
    skeleton_method: str,
    min_component_pixels: int,
    spur_prune_length: int,
    endpoint_merge_distance: int,
    min_segment_pixels: int,
    simplify_epsilon: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    sample_dir = out_dir / f"{_char_id(char)}_{style}"
    sample_dir.mkdir(parents=True, exist_ok=True)
    trial_csv = sample_dir / "font_derived_trial_trajectory.csv"
    summary_json = sample_dir / "font_derived_trial_summary.json"
    compare_png = sample_dir / "font_derived_trial_compare.png"

    warnings: list[str] = []
    font_path = first_existing_font(style_sources, style, style_sources_dir)
    if font_path is None:
        warnings.append("missing_font")
        result = None
        point_count = 0
        break_count = 0
        total_length = 0.0
        bbox = {"bbox_width": 0.0, "bbox_height": 0.0, "aspect_ratio": 0.0}
    else:
        mask = render_char_with_font(char, font_path, image_size=image_size)
        skel_result = skeletonize_font_mask(mask, method=skeleton_method)
        warnings.extend(skel_result.warnings)
        raw_skeleton = np.asarray(skel_result.skeleton, dtype=bool)
        clean_skeleton, _stats = cleanup_skeleton(
            raw_skeleton,
            min_component_pixels=min_component_pixels,
            spur_prune_length=spur_prune_length,
            endpoint_merge_distance=endpoint_merge_distance,
        )
        result = extract_path_segments(
            clean_skeleton,
            min_segment_pixels=min_segment_pixels,
            simplify_epsilon=simplify_epsilon,
        )
        warnings.extend(result.warnings)
        point_count, break_count = _write_trial_csv(trial_csv, result.segments)
        total_length = result.total_path_length_px
        bbox = _trial_bbox(result.segments)
        median_strokes = _median_strokes(char, image_size=image_size)
        _write_compare_figure(char, style, median_strokes, mask, raw_skeleton, clean_skeleton, result, compare_png)

    if result is None:
        median_length = 0.0
        segment_count = 0
        recommended = False
    else:
        median_length = _median_path_length(_median_strokes(char, image_size=image_size))
        segment_count = result.extracted_segment_count
        recommended = result.recommended_for_next_stage and point_count > 0

    summary = {
        "char": char,
        "style": style,
        "segment_count": segment_count,
        "point_count": point_count,
        "break_count": break_count,
        "total_path_length_px": round(total_length, 6),
        "median_path_length_px": median_length,
        "bbox_width": bbox["bbox_width"],
        "bbox_height": bbox["bbox_height"],
        "aspect_ratio": bbox["aspect_ratio"],
        "warning": ";".join(sorted(set(warnings))),
        "recommended_for_visual_followup": bool(recommended),
        "scope": "font-derived trajectory trial only; not formal trajectory; no real stroke order",
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    row = {
        "char": char,
        "char_id": _char_id(char),
        "style": style,
        "sample_dir": str(sample_dir),
        "trial_csv": str(trial_csv),
        "summary_json": str(summary_json),
        "compare_png": str(compare_png),
        "segment_count": segment_count,
        "point_count": point_count,
        "break_count": break_count,
        "total_path_length_px": round(total_length, 6),
        "median_path_length_px": median_length,
        "bbox_width": bbox["bbox_width"],
        "bbox_height": bbox["bbox_height"],
        "aspect_ratio": bbox["aspect_ratio"],
        "recommended_for_visual_followup": bool(recommended),
        "warning": summary["warning"],
    }
    manifest = {
        "char": char,
        "char_id": _char_id(char),
        "style": style,
        "sample_dir": str(sample_dir),
        "trial_csv": str(trial_csv),
        "compare_png": str(compare_png),
        "warning": summary["warning"],
    }
    return row, manifest


def _write_report(path: Path, out_dir: Path, rows: Sequence[dict[str, Any]]) -> None:
    lines = [
        "# Font-derived trajectory trial",
        "",
        "本轮只处理 3 个低风险样本，把 extracted path segments 转成 font-derived candidate trajectory。它不是正式轨迹，不含真实笔顺，不含执行层 width/pressure，不接机器人，也不接默认 pipeline。",
        "",
        f"- output_dir: `{out_dir.resolve()}`",
        "- samples: 山/kaishu, 人/kaishu, 山/lishu",
        "- excluded: xingkai, 中/kaishu, 永/lishu, 德/福/国/风, other complex chars",
        "- CSV name is intentionally `font_derived_trial_trajectory.csv`; no formal `trajectory.csv` is written.",
        "",
        "## Trial samples",
        "",
        "| char | style | segments | points | total_path_px | median_path_px | recommended | warning | compare_png |",
        "|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['segment_count']} | {row['point_count']} | "
            f"{row['total_path_length_px']} | {row['median_path_length_px']} | "
            f"{row['recommended_for_visual_followup']} | {row['warning']} | `{row['compare_png']}` |"
        )
    lines.extend(
        [
            "",
            "## Manual visual questions",
            "",
            "- trial trajectory 是否比 MakeMeAHanzi median 更有字体风格？",
            "- 路径是否过碎，是否还需要 simplification？",
            "- segment order 是否看起来严重不合理？",
            "- 是否适合作为下一步 stroke ordering / simplification 的输入？",
            "",
            "## Boundary",
            "",
            "这不是正式轨迹，不含真实笔顺，不含执行层 width/pressure，不生成 execution_trajectory、robot_workspace、CoppeliaSim 或 AUBO 文件。当前只用于判断 font-outline basis 是否值得继续。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_sample_specs(items: Sequence[str] | None) -> list[tuple[str, str]]:
    if not items:
        return list(DEFAULT_SAMPLE_SPECS)
    specs: list[tuple[str, str]] = []
    for item in items:
        if ":" not in item:
            raise ValueError(f"sample spec must be char:style, got {item!r}")
        char, style = item.split(":", 1)
        specs.append((char, style))
    return specs


def run_font_derived_trajectory_trial(
    path_extraction_dir: Path | str = DEFAULT_PATH_EXTRACTION_DIR,
    output_dir: Path | str | None = None,
    sample_specs: Sequence[tuple[str, str]] | None = None,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    image_size: int = 256,
    skeleton_method: str = "auto",
    min_component_pixels: int = 12,
    spur_prune_length: int = 6,
    endpoint_merge_distance: int = 3,
    min_segment_pixels: int = 4,
    simplify_epsilon: float = 1.0,
    copy_to_paper: bool = True,
) -> dict[str, str]:
    path_extraction_dir = Path(path_extraction_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"font_derived_trajectory_trial_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    style_sources_path = Path(style_sources_path)
    style_sources = _read_json(style_sources_path)
    specs = list(sample_specs or DEFAULT_SAMPLE_SPECS)

    rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for char, style in specs:
        if style == "xingkai":
            continue
        row, manifest = _process_sample(
            char=char,
            style=style,
            out_dir=out_dir,
            style_sources=style_sources,
            style_sources_dir=style_sources_path.parent,
            image_size=image_size,
            skeleton_method=skeleton_method,
            min_component_pixels=min_component_pixels,
            spur_prune_length=spur_prune_length,
            endpoint_merge_distance=endpoint_merge_distance,
            min_segment_pixels=min_segment_pixels,
            simplify_epsilon=simplify_epsilon,
        )
        rows.append(row)
        manifest_rows.append(manifest)

    summary_csv = out_dir / "font_derived_trial_summary.csv"
    manifest_csv = out_dir / "font_derived_trial_manifest.csv"
    report_md = out_dir / "font_derived_trial_report.md"
    _write_csv(summary_csv, rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, out_dir, rows)

    paper_index = ""
    if copy_to_paper:
        paper_subdir = DEFAULT_PAPER_DIR / "font_derived_trajectory_trial"
        paper_subdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "font_derived_trial_summary.csv")
        shutil.copy2(manifest_csv, DEFAULT_PAPER_DIR / "font_derived_trial_manifest.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "font_derived_trial_report.md")
        copied: list[Path] = []
        for row in rows:
            source = Path(str(row.get("compare_png", "")))
            if source.exists():
                target = paper_subdir / f"{Path(row['sample_dir']).name}_compare.png"
                shutil.copy2(source, target)
                copied.append(target)
        index_path = DEFAULT_PAPER_DIR / "font_derived_trajectory_trial_index.md"
        index_lines = [
            "# Font-derived trajectory trial index",
            "",
            f"- source_path_extraction_dir: `{path_extraction_dir.resolve()}`",
            f"- source_trial_dir: `{out_dir.resolve()}`",
            "- Scope: 山/kaishu, 人/kaishu, 山/lishu only.",
            "- Diagnostic only: no formal trajectory.csv, no execution/workspace/robot files, no default pipeline integration.",
            "",
            "| file | content |",
            "|---|---|",
            "| `font_derived_trial_report.md` | trial report and manual visual questions |",
            "| `font_derived_trial_summary.csv` | per-sample trial metrics |",
            "| `font_derived_trial_manifest.csv` | trial output manifest |",
        ]
        for figure in sorted(copied):
            index_lines.append(f"| `font_derived_trajectory_trial/{figure.name}` | trial compare figure |")
        index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
        paper_index = str(index_path)

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "paper_index": paper_index,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run minimal font-derived trajectory trial")
    parser.add_argument("--path-extraction-dir", default=str(DEFAULT_PATH_EXTRACTION_DIR))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--samples", nargs="*", default=None, help="Optional char:style entries")
    parser.add_argument("--style-sources", default=str(DEFAULT_STYLE_SOURCES))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--skeleton-method", choices=["auto", "skimage", "opencv", "ridge"], default="auto")
    parser.add_argument("--min-component-pixels", type=int, default=12)
    parser.add_argument("--spur-prune-length", type=int, default=6)
    parser.add_argument("--endpoint-merge-distance", type=int, default=3)
    parser.add_argument("--min-segment-pixels", type=int, default=4)
    parser.add_argument("--simplify-epsilon", type=float, default=1.0)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args()
    result = run_font_derived_trajectory_trial(
        path_extraction_dir=Path(args.path_extraction_dir),
        output_dir=Path(args.out_dir) if args.out_dir else None,
        sample_specs=_parse_sample_specs(args.samples),
        style_sources_path=Path(args.style_sources),
        image_size=args.image_size,
        skeleton_method=args.skeleton_method,
        min_component_pixels=args.min_component_pixels,
        spur_prune_length=args.spur_prune_length,
        endpoint_merge_distance=args.endpoint_merge_distance,
        min_segment_pixels=args.min_segment_pixels,
        simplify_epsilon=args.simplify_epsilon,
        copy_to_paper=not args.no_copy_to_paper,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
