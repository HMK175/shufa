"""Very small-sample path extraction prototype for cleaned font skeletons.

This is a diagnostic layer only. It turns cleaned kaishu/lishu skeleton pixels
into candidate graph path segments for manual inspection. It does not generate
formal trajectory.csv files and is not connected to run_demo.py or any default
pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from font_outline_basis_feasibility import (
    first_existing_font,
    render_char_with_font,
    skeletonize_font_mask,
)
from font_skeleton_cleanup_prototype import cleanup_skeleton, skeleton_metrics


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_CLEANUP_DIR = EXP_DIR / "outputs" / "font_skeleton_cleanup_prototype_20260619_122355"
DEFAULT_STYLE_SOURCES = EXP_DIR / "configs" / "style_sources.json"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"

DEFAULT_SAMPLE_SPECS = [
    ("\u5c71", "kaishu"),  # 山
    ("\u4eba", "kaishu"),  # 人
    ("\u4e2d", "kaishu"),  # 中
    ("\u5c71", "lishu"),  # 山
    ("\u6c38", "lishu"),  # 永
]

SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "component_count",
    "endpoint_count",
    "branch_point_count",
    "extracted_segment_count",
    "total_path_length_px",
    "longest_segment_length_px",
    "short_segment_count",
    "unhandled_component_count",
    "candidate_order_method",
    "recommended_for_next_stage",
    "warning",
]

MANIFEST_FIELDS = [
    "char",
    "char_id",
    "style",
    "figure_path",
    "extracted_segment_count",
    "recommended_for_next_stage",
    "warning",
]


@dataclass(frozen=True)
class PathSegment:
    points: tuple[tuple[int, int], ...]
    length_px: float
    component_index: int
    order_index: int


@dataclass(frozen=True)
class PathExtractionResult:
    segments: tuple[PathSegment, ...]
    component_count: int
    endpoint_count: int
    branch_point_count: int
    extracted_segment_count: int
    total_path_length_px: float
    longest_segment_length_px: float
    short_segment_count: int
    unhandled_component_count: int
    candidate_order_method: str
    recommended_for_next_stage: bool
    warnings: tuple[str, ...]


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


def _neighbors(shape: tuple[int, int], point: tuple[int, int]) -> Iterable[tuple[int, int]]:
    y, x = point
    height, width = shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width:
                yield ny, nx


def _degree(skeleton: np.ndarray, point: tuple[int, int]) -> int:
    return sum(1 for ny, nx in _neighbors(skeleton.shape, point) if skeleton[ny, nx])


def _components(skeleton: np.ndarray) -> list[set[tuple[int, int]]]:
    skel = np.asarray(skeleton, dtype=bool)
    seen = np.zeros(skel.shape, dtype=bool)
    components: list[set[tuple[int, int]]] = []
    for y, x in zip(*np.nonzero(skel)):
        start = (int(y), int(x))
        if seen[start]:
            continue
        queue: deque[tuple[int, int]] = deque([start])
        seen[start] = True
        comp: set[tuple[int, int]] = set()
        while queue:
            point = queue.popleft()
            comp.add(point)
            for nb in _neighbors(skel.shape, point):
                if skel[nb] and not seen[nb]:
                    seen[nb] = True
                    queue.append(nb)
        components.append(comp)
    components.sort(key=lambda comp: (min(y for y, _ in comp), min(x for _, x in comp)))
    return components


def _edge_key(a: tuple[int, int], b: tuple[int, int]) -> tuple[tuple[int, int], tuple[int, int]]:
    return tuple(sorted([a, b]))  # type: ignore[return-value]


def _polyline_length(points: Sequence[tuple[int, int]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for (y0, x0), (y1, x1) in zip(points[:-1], points[1:]):
        total += math.hypot(float(y1 - y0), float(x1 - x0))
    return total


def _point_line_distance(point: tuple[int, int], start: tuple[int, int], end: tuple[int, int]) -> float:
    py, px = point
    sy, sx = start
    ey, ex = end
    vy, vx = ey - sy, ex - sx
    wy, wx = py - sy, px - sx
    denom = vy * vy + vx * vx
    if denom == 0:
        return math.hypot(py - sy, px - sx)
    t = max(0.0, min(1.0, (wy * vy + wx * vx) / denom))
    cy, cx = sy + t * vy, sx + t * vx
    return math.hypot(py - cy, px - cx)


def _simplify_polyline(points: Sequence[tuple[int, int]], epsilon: float) -> tuple[tuple[int, int], ...]:
    pts = list(points)
    if epsilon <= 0 or len(pts) <= 2:
        return tuple(pts)
    start, end = pts[0], pts[-1]
    max_dist = -1.0
    max_idx = 0
    for idx, point in enumerate(pts[1:-1], start=1):
        dist = _point_line_distance(point, start, end)
        if dist > max_dist:
            max_dist = dist
            max_idx = idx
    if max_dist > epsilon:
        left = _simplify_polyline(pts[: max_idx + 1], epsilon)
        right = _simplify_polyline(pts[max_idx:], epsilon)
        return left[:-1] + right
    return (start, end)


def _trace_segment(
    skeleton: np.ndarray,
    nodes: set[tuple[int, int]],
    start: tuple[int, int],
    first: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [start, first]
    prev = start
    current = first
    guard = int(skeleton.sum()) + 2
    while current not in nodes and guard > 0:
        guard -= 1
        next_points = [nb for nb in _neighbors(skeleton.shape, current) if skeleton[nb] and nb != prev]
        if not next_points:
            break
        if len(next_points) > 1:
            break
        prev, current = current, next_points[0]
        path.append(current)
    return path


def extract_path_segments(
    skeleton: np.ndarray,
    min_segment_pixels: int = 4,
    simplify_epsilon: float = 1.0,
) -> PathExtractionResult:
    skel = np.asarray(skeleton, dtype=bool)
    metrics = skeleton_metrics(skel)
    components = _components(skel)
    warnings: list[str] = []
    raw_segments: list[tuple[int, list[tuple[int, int]], float]] = []
    short_segment_count = 0
    unhandled_component_count = 0
    visited_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()

    for comp_idx, comp in enumerate(components, start=1):
        comp_nodes = {point for point in comp if _degree(skel, point) != 2}
        if not comp_nodes:
            unhandled_component_count += 1
            warnings.append(f"component_{comp_idx}_has_no_endpoint_or_branch")
            continue
        for node in sorted(comp_nodes):
            for nb in _neighbors(skel.shape, node):
                if not skel[nb] or nb not in comp:
                    continue
                first_edge = _edge_key(node, nb)
                if first_edge in visited_edges:
                    continue
                path = _trace_segment(skel, comp_nodes, node, nb)
                for p0, p1 in zip(path[:-1], path[1:]):
                    visited_edges.add(_edge_key(p0, p1))
                if len(path) < min_segment_pixels:
                    short_segment_count += 1
                    continue
                length = _polyline_length(path)
                raw_segments.append((comp_idx, path, length))

    raw_segments.sort(key=lambda item: (item[0], -item[2], item[1][0][0], item[1][0][1]))
    segments: list[PathSegment] = []
    for order_idx, (component_idx, points, length) in enumerate(raw_segments, start=1):
        simplified = _simplify_polyline(points, simplify_epsilon)
        segments.append(
            PathSegment(
                points=simplified,
                length_px=round(length, 6),
                component_index=component_idx,
                order_index=order_idx,
            )
        )

    if not segments:
        warnings.append("no_segments_extracted")
    if short_segment_count:
        warnings.append(f"short_segments_filtered:{short_segment_count}")
    if metrics["connected_component_count"] > 1:
        warnings.append("multi_component_skeleton")
    if metrics["branch_point_count"] > 20:
        warnings.append("high_branch_count")

    total_length = sum(segment.length_px for segment in segments)
    longest = max((segment.length_px for segment in segments), default=0.0)
    recommended = (
        len(segments) > 0
        and unhandled_component_count == 0
        and total_length > 20.0
        and len(segments) <= 32
    )

    return PathExtractionResult(
        segments=tuple(segments),
        component_count=metrics["connected_component_count"],
        endpoint_count=metrics["endpoint_count"],
        branch_point_count=metrics["branch_point_count"],
        extracted_segment_count=len(segments),
        total_path_length_px=round(total_length, 6),
        longest_segment_length_px=round(longest, 6),
        short_segment_count=short_segment_count,
        unhandled_component_count=unhandled_component_count,
        candidate_order_method="component_order_longest_first",
        recommended_for_next_stage=bool(recommended),
        warnings=tuple(sorted(set(warnings))),
    )


def _write_path_figure(
    char: str,
    style: str,
    mask: np.ndarray,
    raw_skeleton: np.ndarray,
    clean_skeleton: np.ndarray,
    result: PathExtractionResult,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_y, raw_x = np.nonzero(raw_skeleton)
    clean_y, clean_x = np.nonzero(clean_skeleton)
    fig, axes = plt.subplots(1, 4, figsize=(12, 3.2), dpi=150)
    titles = ["font mask", "raw skeleton", "cleaned skeleton", "candidate path segments"]
    for ax, title in zip(axes, titles):
        ax.set_title(title, fontsize=8)
        ax.imshow(np.where(mask, 0.88, 1.0), cmap="gray", vmin=0, vmax=1)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect("equal")
    axes[1].scatter(raw_x, raw_y, s=0.7, color="#d62728", alpha=0.9)
    axes[2].scatter(clean_x, clean_y, s=0.7, color="#1f77b4", alpha=0.9)
    axes[3].scatter(clean_x, clean_y, s=0.35, color="#bdbdbd", alpha=0.45)
    colors = plt.cm.tab20(np.linspace(0, 1, max(1, min(20, len(result.segments)))))
    for idx, segment in enumerate(result.segments):
        points = np.asarray(segment.points, dtype=float)
        if len(points) < 2:
            continue
        color = colors[idx % len(colors)]
        axes[3].plot(points[:, 1], points[:, 0], linewidth=1.7, color=color)
        mid = points[len(points) // 2]
        axes[3].text(mid[1], mid[0], str(segment.order_index), fontsize=6, color="#111111")
    fig.suptitle(f"{_char_id(char)} / {style} path extraction prototype", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(path)
    plt.close(fig)


def _style_rates(rows: Sequence[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    counts: dict[str, Counter[str]] = {}
    for row in rows:
        style = str(row.get("style", ""))
        counts.setdefault(style, Counter())
        counts[style]["total"] += 1
        if row.get("recommended_for_next_stage") is True:
            counts[style]["recommended"] += 1
    return {style: (counter["recommended"], counter["total"]) for style, counter in counts.items()}


def _write_report(path: Path, output_dir: Path, rows: Sequence[dict[str, Any]], manifest_rows: Sequence[dict[str, Any]]) -> None:
    rates = _style_rates(rows)
    figure_by_key = {(row["char"], row["style"]): row["figure_path"] for row in manifest_rows}
    lines = [
        "# Font skeleton path extraction prototype",
        "",
        "本轮只把 cleaned font skeleton 转成候选 path segments，作为 very small-sample diagnostic。它不是正式轨迹，不生成 `trajectory.csv`，不含真实笔顺，也不接入默认 pipeline。",
        "",
        f"- output_dir: `{output_dir.resolve()}`",
        "- samples: 山/kaishu, 人/kaishu, 中/kaishu, 山/lishu, 永/lishu",
        "- excluded: xingkai, 德, 福, 国, 风, other complex chars",
        "- candidate_order_method: `component_order_longest_first`",
        "",
        "## Recommendation counts",
        "",
        "| style | recommended | total |",
        "|---|---:|---:|",
    ]
    for style in ["kaishu", "lishu"]:
        recommended, total = rates.get(style, (0, 0))
        lines.append(f"| {style} | {recommended} | {total} |")
    lines.extend(
        [
            "",
            "## Sample results",
            "",
            "| char | style | components | endpoints | branches | segments | total_length_px | recommended | warning | figure |",
            "|---|---|---:|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['component_count']} | {row['endpoint_count']} | "
            f"{row['branch_point_count']} | {row['extracted_segment_count']} | {row['total_path_length_px']} | "
            f"{row['recommended_for_next_stage']} | {row['warning']} | `{figure_by_key.get((row['char'], row['style']), '')}` |"
        )
    lines.extend(
        [
            "",
            "## Manual visual audit focus",
            "",
            "- path 是否连续，还是仍有明显断裂？",
            "- path 是否过碎，候选 segment 是否太多？",
            "- 是否能看出可写主路径，而不是只是一团图像骨架？",
            "- candidate order 是否明显不合理？",
            "- 是否值得进入 font-derived trajectory trial？",
            "",
            "## Boundary",
            "",
            "本轮不是正式轨迹生成，不恢复真实笔顺，不替换 MakeMeAHanzi median，不修改 `style_profiles.json` 或 `run_demo.py`，也不调用 API、CoppeliaSim、AUBO 或 SDK。若人工看图认为 3 个以上样本可用，下一步才建议做 font-derived trajectory trial。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _process_sample(
    char: str,
    style: str,
    style_sources: dict[str, Any],
    style_sources_dir: Path,
    figures_dir: Path,
    image_size: int,
    skeleton_method: str,
    min_component_pixels: int,
    spur_prune_length: int,
    endpoint_merge_distance: int,
    min_segment_pixels: int,
    simplify_epsilon: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    warnings: list[str] = []
    font_path = first_existing_font(style_sources, style, style_sources_dir)
    if font_path is None:
        warning = "missing_font"
        row = {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "component_count": 0,
            "endpoint_count": 0,
            "branch_point_count": 0,
            "extracted_segment_count": 0,
            "total_path_length_px": 0.0,
            "longest_segment_length_px": 0.0,
            "short_segment_count": 0,
            "unhandled_component_count": 0,
            "candidate_order_method": "component_order_longest_first",
            "recommended_for_next_stage": False,
            "warning": warning,
        }
        return row, {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "figure_path": "",
            "extracted_segment_count": 0,
            "recommended_for_next_stage": False,
            "warning": warning,
        }
    try:
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
        figure_path = figures_dir / f"path_extraction_{_char_id(char)}_{style}.png"
        _write_path_figure(char, style, mask, raw_skeleton, clean_skeleton, result, figure_path)
        row = {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "component_count": result.component_count,
            "endpoint_count": result.endpoint_count,
            "branch_point_count": result.branch_point_count,
            "extracted_segment_count": result.extracted_segment_count,
            "total_path_length_px": result.total_path_length_px,
            "longest_segment_length_px": result.longest_segment_length_px,
            "short_segment_count": result.short_segment_count,
            "unhandled_component_count": result.unhandled_component_count,
            "candidate_order_method": result.candidate_order_method,
            "recommended_for_next_stage": result.recommended_for_next_stage,
            "warning": ";".join(sorted(set(warnings))),
        }
        manifest = {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "figure_path": str(figure_path),
            "extracted_segment_count": result.extracted_segment_count,
            "recommended_for_next_stage": result.recommended_for_next_stage,
            "warning": row["warning"],
        }
        return row, manifest
    except Exception as exc:  # pragma: no cover - defensive around font/rendering libraries
        warning = f"path_extraction_failed:{type(exc).__name__}"
        row = {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "component_count": 0,
            "endpoint_count": 0,
            "branch_point_count": 0,
            "extracted_segment_count": 0,
            "total_path_length_px": 0.0,
            "longest_segment_length_px": 0.0,
            "short_segment_count": 0,
            "unhandled_component_count": 0,
            "candidate_order_method": "component_order_longest_first",
            "recommended_for_next_stage": False,
            "warning": warning,
        }
        return row, {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "figure_path": "",
            "extracted_segment_count": 0,
            "recommended_for_next_stage": False,
            "warning": warning,
        }


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


def run_font_skeleton_path_extraction_prototype(
    cleanup_dir: Path | str = DEFAULT_CLEANUP_DIR,
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
    cleanup_dir = Path(cleanup_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"font_skeleton_path_extraction_{timestamp}"
    figures_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

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
            style_sources=style_sources,
            style_sources_dir=style_sources_path.parent,
            figures_dir=figures_dir,
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

    summary_csv = out_dir / "skeleton_path_summary.csv"
    manifest_csv = out_dir / "skeleton_path_manifest.csv"
    report_md = out_dir / "skeleton_path_report.md"
    _write_csv(summary_csv, rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, out_dir, rows, manifest_rows)

    paper_index = ""
    if copy_to_paper:
        paper_subdir = DEFAULT_PAPER_DIR / "font_skeleton_path_extraction"
        paper_subdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "skeleton_path_summary.csv")
        shutil.copy2(manifest_csv, DEFAULT_PAPER_DIR / "skeleton_path_manifest.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "skeleton_path_report.md")
        copied: list[Path] = []
        for manifest in manifest_rows:
            source = Path(str(manifest.get("figure_path", "")))
            if source.exists():
                target = paper_subdir / source.name
                shutil.copy2(source, target)
                copied.append(target)
        index_path = DEFAULT_PAPER_DIR / "font_skeleton_path_extraction_index.md"
        index_lines = [
            "# Font skeleton path extraction prototype index",
            "",
            f"- source_cleanup_dir: `{cleanup_dir.resolve()}`",
            f"- source_path_extraction_dir: `{out_dir.resolve()}`",
            "- Scope: very small sample only: 山/kaishu, 人/kaishu, 中/kaishu, 山/lishu, 永/lishu.",
            "- Excludes xingkai and complex chars such as 德/福/国/风.",
            "- Diagnostic only: no trajectory.csv, no default pipeline integration, no real stroke order recovery.",
            "",
            "| file | content |",
            "|---|---|",
            "| `skeleton_path_report.md` | path extraction report and manual visual audit questions |",
            "| `skeleton_path_summary.csv` | per sample graph path metrics |",
            "| `skeleton_path_manifest.csv` | path figure manifest |",
        ]
        for figure in sorted(copied):
            index_lines.append(f"| `font_skeleton_path_extraction/{figure.name}` | candidate path segment overlay |")
        index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
        paper_index = str(index_path)

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "figures_dir": str(figures_dir),
        "paper_index": paper_index,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run very small-sample font skeleton path extraction prototype")
    parser.add_argument("--cleanup-dir", default=str(DEFAULT_CLEANUP_DIR))
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
    result = run_font_skeleton_path_extraction_prototype(
        cleanup_dir=Path(args.cleanup_dir),
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
