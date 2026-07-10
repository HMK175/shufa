"""Lightweight cleanup prototype for font-outline skeleton candidates.

This module is diagnostic only. It re-renders kaishu/lishu font masks,
extracts skeleton candidates, applies small cleanup operations, and writes
before/after figures plus metrics. It does not create trajectory.csv files and
does not change the default MakeMeAHanzi-based pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import Counter, deque
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
    skeleton_topology_metrics,
    skeletonize_font_mask,
)


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_FEASIBILITY_DIR = EXP_DIR / "outputs" / "font_outline_basis_feasibility_20260619_115008"
DEFAULT_STYLE_SOURCES = EXP_DIR / "configs" / "style_sources.json"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
DEFAULT_CHARS = ["山", "中", "人", "永", "风"]
DEFAULT_STYLES = ["kaishu", "lishu"]

SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "font_path",
    "skeleton_method",
    "raw_component_count",
    "clean_component_count",
    "raw_endpoint_count",
    "clean_endpoint_count",
    "raw_branch_point_count",
    "clean_branch_point_count",
    "raw_skeleton_pixel_count",
    "clean_skeleton_pixel_count",
    "removed_component_count",
    "merged_endpoint_count",
    "pruned_branch_count",
    "cleanup_status",
    "warning",
]

MANIFEST_FIELDS = [
    "char",
    "char_id",
    "style",
    "figure_path",
    "cleanup_status",
    "warning",
]


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


def _neighbors(shape: tuple[int, int], y: int, x: int) -> Iterable[tuple[int, int]]:
    height, width = shape
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width:
                yield ny, nx


def _degree(grid: np.ndarray, y: int, x: int) -> int:
    return sum(1 for ny, nx in _neighbors(grid.shape, y, x) if grid[ny, nx])


def _components(grid: np.ndarray) -> list[list[tuple[int, int]]]:
    skel = np.asarray(grid, dtype=bool)
    seen = np.zeros(skel.shape, dtype=bool)
    components: list[list[tuple[int, int]]] = []
    for y, x in zip(*np.nonzero(skel)):
        y = int(y)
        x = int(x)
        if seen[y, x]:
            continue
        queue: deque[tuple[int, int]] = deque([(y, x)])
        seen[y, x] = True
        comp: list[tuple[int, int]] = []
        while queue:
            cy, cx = queue.popleft()
            comp.append((cy, cx))
            for ny, nx in _neighbors(skel.shape, cy, cx):
                if skel[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        components.append(comp)
    return components


def skeleton_metrics(skeleton: np.ndarray) -> dict[str, int]:
    skel = np.asarray(skeleton, dtype=bool)
    topology = skeleton_topology_metrics(skel)
    return {
        "connected_component_count": len(_components(skel)),
        "skeleton_pixel_count": int(topology["skeleton_pixel_count"]),
        "endpoint_count": int(topology["endpoint_count"]),
        "branch_point_count": int(topology["branch_point_count"]),
    }


def _remove_small_components(skeleton: np.ndarray, min_component_pixels: int) -> tuple[np.ndarray, int]:
    skel = np.asarray(skeleton, dtype=bool).copy()
    components = _components(skel)
    if not components:
        return skel, 0
    largest_size = max(len(comp) for comp in components)
    cleaned = np.zeros_like(skel)
    removed = 0
    for comp in components:
        keep = len(comp) >= min_component_pixels or len(comp) == largest_size
        if keep:
            for y, x in comp:
                cleaned[y, x] = True
        else:
            removed += 1
    return cleaned, removed


def _endpoints(skeleton: np.ndarray) -> list[tuple[int, int]]:
    skel = np.asarray(skeleton, dtype=bool)
    return [(int(y), int(x)) for y, x in zip(*np.nonzero(skel)) if _degree(skel, int(y), int(x)) == 1]


def _trace_from_endpoint(
    skeleton: np.ndarray,
    start: tuple[int, int],
    max_length: int,
) -> tuple[list[tuple[int, int]], str]:
    skel = np.asarray(skeleton, dtype=bool)
    path = [start]
    prev: tuple[int, int] | None = None
    current = start
    for _ in range(max_length):
        candidates = [(ny, nx) for ny, nx in _neighbors(skel.shape, *current) if skel[ny, nx] and (ny, nx) != prev]
        if not candidates:
            return path, "dead_end"
        if len(candidates) > 1:
            return path, "branch"
        nxt = candidates[0]
        prev, current = current, nxt
        path.append(current)
        degree = _degree(skel, *current)
        if degree >= 3:
            return path, "branch"
        if degree == 1 and current != start:
            return path, "endpoint"
    return path, "long"


def _prune_short_spurs(skeleton: np.ndarray, max_length: int) -> tuple[np.ndarray, int]:
    if max_length <= 0:
        return np.asarray(skeleton, dtype=bool).copy(), 0
    skel = np.asarray(skeleton, dtype=bool).copy()
    remove: set[tuple[int, int]] = set()
    pruned = 0
    for endpoint in _endpoints(skel):
        if endpoint in remove:
            continue
        path, terminal = _trace_from_endpoint(skel, endpoint, max_length)
        if terminal == "branch" and 1 < len(path) <= max_length + 1:
            remove.update(path[:-1])
            pruned += 1
        elif terminal in {"dead_end", "endpoint"} and len(path) <= max_length:
            remove.update(path)
            pruned += 1
    for y, x in remove:
        skel[y, x] = False
    return skel, pruned


def _draw_line(grid: np.ndarray, start: tuple[int, int], end: tuple[int, int]) -> None:
    y0, x0 = start
    y1, x1 = end
    steps = max(abs(y1 - y0), abs(x1 - x0), 1) + 1
    ys = np.linspace(y0, y1, steps)
    xs = np.linspace(x0, x1, steps)
    for y, x in zip(ys, xs):
        grid[int(round(y)), int(round(x))] = True


def _merge_close_endpoints(skeleton: np.ndarray, max_distance: int) -> tuple[np.ndarray, int]:
    skel = np.asarray(skeleton, dtype=bool).copy()
    if max_distance <= 0:
        return skel, 0
    endpoints = _endpoints(skel)
    used: set[int] = set()
    merged = 0
    for i, p0 in enumerate(endpoints):
        if i in used:
            continue
        best_j = None
        best_dist = float("inf")
        for j, p1 in enumerate(endpoints):
            if i == j or j in used:
                continue
            dist = math.hypot(p0[0] - p1[0], p0[1] - p1[1])
            if 1.5 < dist <= max_distance and dist < best_dist:
                best_j = j
                best_dist = dist
        if best_j is not None:
            _draw_line(skel, p0, endpoints[best_j])
            used.add(i)
            used.add(best_j)
            merged += 1
    return skel, merged


def cleanup_skeleton(
    skeleton: np.ndarray,
    min_component_pixels: int = 12,
    spur_prune_length: int = 6,
    endpoint_merge_distance: int = 3,
) -> tuple[np.ndarray, dict[str, int]]:
    """Apply conservative cleanup to a binary skeleton.

    The operations are intentionally simple and diagnostic:
    remove tiny components, prune short endpoint-to-branch spurs, optionally
    connect very close endpoint pairs, then remove tiny components again.
    """

    skel = np.asarray(skeleton, dtype=bool).copy()
    skel, removed_first = _remove_small_components(skel, min_component_pixels)
    skel, pruned = _prune_short_spurs(skel, spur_prune_length)
    skel, merged = _merge_close_endpoints(skel, endpoint_merge_distance)
    skel, removed_second = _remove_small_components(skel, min_component_pixels)
    return skel, {
        "removed_component_count": int(removed_first + removed_second),
        "pruned_branch_count": int(pruned),
        "merged_endpoint_count": int(merged),
    }


def _write_compare_figure(
    char: str,
    style: str,
    mask: np.ndarray,
    raw_skeleton: np.ndarray,
    clean_skeleton: np.ndarray,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_y, raw_x = np.nonzero(raw_skeleton)
    clean_y, clean_x = np.nonzero(clean_skeleton)
    fig, axes = plt.subplots(1, 4, figsize=(11.5, 3.1), dpi=150)
    panels = [
        ("font mask", axes[0]),
        ("raw skeleton", axes[1]),
        ("cleaned skeleton", axes[2]),
        ("overlay raw/clean", axes[3]),
    ]
    for title, ax in panels:
        ax.set_title(title, fontsize=8)
        ax.imshow(np.where(mask, 0.88, 1.0), cmap="gray", vmin=0, vmax=1)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect("equal")
    axes[1].scatter(raw_x, raw_y, s=0.8, color="#d62728", alpha=0.9)
    axes[2].scatter(clean_x, clean_y, s=0.8, color="#1f77b4", alpha=0.9)
    axes[3].scatter(raw_x, raw_y, s=0.8, color="#d62728", alpha=0.45, label="raw")
    axes[3].scatter(clean_x, clean_y, s=0.8, color="#1f77b4", alpha=0.85, label="clean")
    axes[3].legend(loc="lower right", fontsize=6, frameon=False)
    fig.suptitle(f"{_char_id(char)} / {style} font skeleton cleanup prototype", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(path)
    plt.close(fig)


def _style_success_rates(rows: Sequence[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    counts: dict[str, Counter[str]] = {}
    for row in rows:
        style = str(row.get("style", ""))
        counts.setdefault(style, Counter())
        counts[style]["total"] += 1
        if row.get("cleanup_status") == "success":
            counts[style]["success"] += 1
    return {style: (counter["success"], counter["total"]) for style, counter in counts.items()}


def _mean_delta(rows: Sequence[dict[str, Any]], raw_field: str, clean_field: str) -> float:
    vals: list[float] = []
    for row in rows:
        vals.append(float(row.get(clean_field, 0)) - float(row.get(raw_field, 0)))
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def _write_report(path: Path, output_dir: Path, rows: Sequence[dict[str, Any]], manifest_rows: Sequence[dict[str, Any]]) -> None:
    rates = _style_success_rates(rows)
    by_style: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_style.setdefault(str(row.get("style", "")), []).append(dict(row))
    simplified = sorted(
        rows,
        key=lambda row: (
            int(row.get("raw_endpoint_count", 0)) - int(row.get("clean_endpoint_count", 0))
            + int(row.get("raw_branch_point_count", 0)) - int(row.get("clean_branch_point_count", 0))
        ),
        reverse=True,
    )[:8]
    still_noisy = sorted(
        rows,
        key=lambda row: int(row.get("clean_endpoint_count", 0)) + int(row.get("clean_branch_point_count", 0)),
        reverse=True,
    )[:8]
    figure_by_key = {(row["char"], row["style"]): row["figure_path"] for row in manifest_rows}

    lines = [
        "# Font skeleton cleanup prototype",
        "",
        "本轮只针对 kaishu / lishu 的字体轮廓 skeleton 做轻量后处理诊断，不生成正式 trajectory.csv，不替换默认 pipeline。",
        "",
        f"- output_dir: `{output_dir.resolve()}`",
        "- scope: kaishu / lishu only; xingkai is intentionally excluded.",
        "- cleanup operations: remove small connected components, prune short endpoint branches, optionally merge very close endpoints.",
        "",
        "## Success rate",
        "",
        "| style | success | total | success_rate |",
        "|---|---:|---:|---:|",
    ]
    for style in DEFAULT_STYLES:
        success, total = rates.get(style, (0, 0))
        rate = success / total if total else 0.0
        lines.append(f"| {style} | {success} | {total} | {rate:.3f} |")

    lines.extend(
        [
            "",
            "## Mean cleanup deltas",
            "",
            "| style | endpoint_delta | branch_delta | component_delta | skeleton_pixel_delta |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for style in DEFAULT_STYLES:
        style_rows = by_style.get(style, [])
        lines.append(
            f"| {style} | {_mean_delta(style_rows, 'raw_endpoint_count', 'clean_endpoint_count')} | "
            f"{_mean_delta(style_rows, 'raw_branch_point_count', 'clean_branch_point_count')} | "
            f"{_mean_delta(style_rows, 'raw_component_count', 'clean_component_count')} | "
            f"{_mean_delta(style_rows, 'raw_skeleton_pixel_count', 'clean_skeleton_pixel_count')} |"
        )

    lines.extend(
        [
            "",
            "## Cleaner after cleanup",
            "",
            "| char | style | raw_endpoints | clean_endpoints | raw_branches | clean_branches | figure |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in simplified:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['raw_endpoint_count']} | {row['clean_endpoint_count']} | "
            f"{row['raw_branch_point_count']} | {row['clean_branch_point_count']} | "
            f"`{figure_by_key.get((row['char'], row['style']), '')}` |"
        )

    lines.extend(
        [
            "",
            "## Still noisy or fragmented after cleanup",
            "",
            "| char | style | clean_components | clean_endpoints | clean_branches | warning |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for row in still_noisy:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['clean_component_count']} | "
            f"{row['clean_endpoint_count']} | {row['clean_branch_point_count']} | {row['warning']} |"
        )

    lines.extend(
        [
            "",
            "## 人工看图重点",
            "",
            "- cleaned skeleton 是否比 raw skeleton 更连续、更少噪声？",
            "- 是否保留了楷书/隶书的字体风格，而不是被清理成过于普通的中心线？",
            "- 是否出现过度清理，导致隶书横向笔形或楷书关键结构丢失？",
            "- 是否已经接近可提取 path 的程度，还是仍需要图结构级主路径提取？",
            "",
            "## Diagnostic boundary",
            "",
            "当前仍不是正式书写轨迹，也不是真实书法风格学习结果。本轮只回答：轻量 cleanup 是否能让 kaishu / lishu 的 font skeleton 更接近可写轨迹候选。若人工看图认为有价值，下一步才应进入 path extraction prototype。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _process_one(
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
) -> tuple[dict[str, Any], dict[str, Any]]:
    warnings: list[str] = []
    font_path = first_existing_font(style_sources, style, style_sources_dir)
    empty = np.zeros((image_size, image_size), dtype=bool)
    if font_path is None:
        raw_metrics = skeleton_metrics(empty)
        row = {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "font_path": "",
            "skeleton_method": "none",
            "raw_component_count": raw_metrics["connected_component_count"],
            "clean_component_count": 0,
            "raw_endpoint_count": raw_metrics["endpoint_count"],
            "clean_endpoint_count": 0,
            "raw_branch_point_count": raw_metrics["branch_point_count"],
            "clean_branch_point_count": 0,
            "raw_skeleton_pixel_count": raw_metrics["skeleton_pixel_count"],
            "clean_skeleton_pixel_count": 0,
            "removed_component_count": 0,
            "merged_endpoint_count": 0,
            "pruned_branch_count": 0,
            "cleanup_status": "failed",
            "warning": "missing_font",
        }
        return row, {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "figure_path": "",
            "cleanup_status": "failed",
            "warning": "missing_font",
        }

    try:
        mask = render_char_with_font(char, font_path, image_size=image_size)
        skel_result = skeletonize_font_mask(mask, method=skeleton_method)
        warnings.extend(skel_result.warnings)
        raw_skeleton = np.asarray(skel_result.skeleton, dtype=bool)
        cleaned, stats = cleanup_skeleton(
            raw_skeleton,
            min_component_pixels=min_component_pixels,
            spur_prune_length=spur_prune_length,
            endpoint_merge_distance=endpoint_merge_distance,
        )
        raw_metrics = skeleton_metrics(raw_skeleton)
        clean_metrics = skeleton_metrics(cleaned)
        status = "success" if skel_result.skeleton_success and clean_metrics["skeleton_pixel_count"] > 0 else "failed"
        if clean_metrics["connected_component_count"] > 1:
            warnings.append("cleaned_skeleton_disconnected")
        if clean_metrics["branch_point_count"] > raw_metrics["branch_point_count"]:
            warnings.append("branch_count_increased")
        figure_path = figures_dir / f"cleanup_compare_{_char_id(char)}_{style}.png"
        _write_compare_figure(char, style, mask, raw_skeleton, cleaned, figure_path)
        row = {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "font_path": str(font_path),
            "skeleton_method": skel_result.method,
            "raw_component_count": raw_metrics["connected_component_count"],
            "clean_component_count": clean_metrics["connected_component_count"],
            "raw_endpoint_count": raw_metrics["endpoint_count"],
            "clean_endpoint_count": clean_metrics["endpoint_count"],
            "raw_branch_point_count": raw_metrics["branch_point_count"],
            "clean_branch_point_count": clean_metrics["branch_point_count"],
            "raw_skeleton_pixel_count": raw_metrics["skeleton_pixel_count"],
            "clean_skeleton_pixel_count": clean_metrics["skeleton_pixel_count"],
            **stats,
            "cleanup_status": status,
            "warning": ";".join(sorted(set(warnings))),
        }
        manifest = {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "figure_path": str(figure_path),
            "cleanup_status": status,
            "warning": row["warning"],
        }
        return row, manifest
    except Exception as exc:  # pragma: no cover - defensive around font/rendering libraries
        raw_metrics = skeleton_metrics(empty)
        warning = f"cleanup_failed:{type(exc).__name__}"
        row = {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "font_path": str(font_path),
            "skeleton_method": "none",
            "raw_component_count": raw_metrics["connected_component_count"],
            "clean_component_count": 0,
            "raw_endpoint_count": raw_metrics["endpoint_count"],
            "clean_endpoint_count": 0,
            "raw_branch_point_count": raw_metrics["branch_point_count"],
            "clean_branch_point_count": 0,
            "raw_skeleton_pixel_count": raw_metrics["skeleton_pixel_count"],
            "clean_skeleton_pixel_count": 0,
            "removed_component_count": 0,
            "merged_endpoint_count": 0,
            "pruned_branch_count": 0,
            "cleanup_status": "failed",
            "warning": warning,
        }
        return row, {
            "char": char,
            "char_id": _char_id(char),
            "style": style,
            "figure_path": "",
            "cleanup_status": "failed",
            "warning": warning,
        }


def run_font_skeleton_cleanup_prototype(
    feasibility_dir: Path | str = DEFAULT_FEASIBILITY_DIR,
    output_dir: Path | str | None = None,
    chars: Sequence[str] | None = None,
    styles: Sequence[str] | None = None,
    style_sources_path: Path | str = DEFAULT_STYLE_SOURCES,
    image_size: int = 256,
    skeleton_method: str = "auto",
    min_component_pixels: int = 12,
    spur_prune_length: int = 6,
    endpoint_merge_distance: int = 3,
    copy_to_paper: bool = True,
) -> dict[str, str]:
    feasibility_dir = Path(feasibility_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"font_skeleton_cleanup_prototype_{timestamp}"
    figures_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    style_sources_path = Path(style_sources_path)
    style_sources = _read_json(style_sources_path)
    selected_chars = list(chars or DEFAULT_CHARS)
    selected_styles = list(styles or DEFAULT_STYLES)

    rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for char in selected_chars:
        for style in selected_styles:
            if style not in DEFAULT_STYLES:
                continue
            row, manifest = _process_one(
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
            )
            rows.append(row)
            manifest_rows.append(manifest)

    summary_csv = out_dir / "skeleton_cleanup_summary.csv"
    manifest_csv = out_dir / "skeleton_cleanup_manifest.csv"
    report_md = out_dir / "skeleton_cleanup_report.md"
    _write_csv(summary_csv, rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, out_dir, rows, manifest_rows)

    paper_index = ""
    if copy_to_paper:
        paper_subdir = DEFAULT_PAPER_DIR / "font_skeleton_cleanup_prototype"
        paper_subdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "skeleton_cleanup_summary.csv")
        shutil.copy2(manifest_csv, DEFAULT_PAPER_DIR / "skeleton_cleanup_manifest.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "skeleton_cleanup_report.md")
        copied_figures = []
        for manifest in manifest_rows:
            source = Path(str(manifest.get("figure_path", "")))
            if source.exists():
                target = paper_subdir / source.name
                shutil.copy2(source, target)
                copied_figures.append(target)
        index_path = DEFAULT_PAPER_DIR / "font_skeleton_cleanup_prototype_index.md"
        index_lines = [
            "# Font skeleton cleanup prototype index",
            "",
            f"- source_feasibility_dir: `{feasibility_dir.resolve()}`",
            f"- source_cleanup_dir: `{out_dir.resolve()}`",
            "- Scope: kaishu / lishu only. Xingkai is intentionally excluded.",
            "- This is a diagnostic cleanup prototype; it does not generate trajectory.csv and does not replace the default pipeline.",
            "",
            "| file | content |",
            "|---|---|",
            "| `skeleton_cleanup_report.md` | cleanup report and manual visual audit questions |",
            "| `skeleton_cleanup_summary.csv` | before/after metrics per char/style |",
            "| `skeleton_cleanup_manifest.csv` | cleanup figure manifest |",
        ]
        for figure in sorted(copied_figures):
            index_lines.append(f"| `font_skeleton_cleanup_prototype/{figure.name}` | before/after cleanup comparison |")
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
    parser = argparse.ArgumentParser(description="Run kaishu/lishu font skeleton cleanup prototype diagnostics")
    parser.add_argument("--feasibility-dir", default=str(DEFAULT_FEASIBILITY_DIR))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--chars", nargs="*", default=None)
    parser.add_argument("--styles", nargs="*", default=None)
    parser.add_argument("--style-sources", default=str(DEFAULT_STYLE_SOURCES))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--skeleton-method", choices=["auto", "skimage", "opencv", "ridge"], default="auto")
    parser.add_argument("--min-component-pixels", type=int, default=12)
    parser.add_argument("--spur-prune-length", type=int, default=6)
    parser.add_argument("--endpoint-merge-distance", type=int, default=3)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args()
    result = run_font_skeleton_cleanup_prototype(
        feasibility_dir=Path(args.feasibility_dir),
        output_dir=Path(args.out_dir) if args.out_dir else None,
        chars=args.chars,
        styles=args.styles,
        style_sources_path=Path(args.style_sources),
        image_size=args.image_size,
        skeleton_method=args.skeleton_method,
        min_component_pixels=args.min_component_pixels,
        spur_prune_length=args.spur_prune_length,
        endpoint_merge_distance=args.endpoint_merge_distance,
        copy_to_paper=not args.no_copy_to_paper,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
