"""Tiny stroke ordering and simplification prototype for font-derived trials.

This diagnostic script reads the earlier font-derived trial trajectories and
creates a more writable candidate order for two hand-picked samples only:
``人/kaishu`` and ``山/lishu``. It does not generate a formal trajectory.csv,
does not connect to run_demo.py, and does not claim to recover real stroke order.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_TRIAL_DIR = EXP_DIR / "outputs" / "font_derived_trajectory_trial_20260619_125428"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"

DEFAULT_SAMPLE_SPECS = [
    ("\u4eba", "kaishu"),  # 人
    ("\u5c71", "lishu"),  # 山
]

ORDERED_FIELDS = [
    "y",
    "x",
    "stroke_like_id",
    "point_index",
    "is_break",
    "order_index",
    "source",
]

SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "sample_dir",
    "ordered_csv",
    "summary_json",
    "compare_png",
    "raw_segment_count",
    "simplified_segment_count",
    "ordered_stroke_like_count",
    "removed_short_segment_count",
    "merged_segment_count",
    "total_path_length_px",
    "warning",
    "recommended_for_next_stage",
]

MANIFEST_FIELDS = [
    "char",
    "char_id",
    "style",
    "sample_dir",
    "source_trial_csv",
    "ordered_csv",
    "compare_png",
    "warning",
]


@dataclass(frozen=True)
class TrialSegment:
    segment_id: int
    points: tuple[tuple[float, float], ...]  # (y, x)


@dataclass(frozen=True)
class OrderedSegment:
    stroke_like_id: int
    order_index: int
    points: tuple[tuple[float, float], ...]  # (y, x)
    source_segment_ids: tuple[int, ...]


def _char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else ""


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _read_trial_segments(path: Path) -> list[TrialSegment]:
    by_segment: dict[int, list[tuple[float, float]]] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("is_break", "")).strip() == "1":
                continue
            try:
                y = float(row.get("y", "nan"))
                x = float(row.get("x", "nan"))
                segment_id = int(float(row.get("segment_id", "0")))
            except ValueError:
                continue
            if not (math.isfinite(y) and math.isfinite(x)) or segment_id <= 0:
                continue
            by_segment.setdefault(segment_id, []).append((y, x))
    return [
        TrialSegment(segment_id=segment_id, points=tuple(points))
        for segment_id, points in sorted(by_segment.items())
        if points
    ]


def _polyline_length(points: Sequence[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    return float(
        sum(
            math.hypot(float(y1 - y0), float(x1 - x0))
            for (y0, x0), (y1, x1) in zip(points[:-1], points[1:])
        )
    )


def _point_line_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    py, px = point
    sy, sx = start
    ey, ex = end
    vy, vx = ey - sy, ex - sx
    wy, wx = py - sy, px - sx
    denom = vy * vy + vx * vx
    if denom <= 1e-12:
        return math.hypot(py - sy, px - sx)
    t = max(0.0, min(1.0, (wy * vy + wx * vx) / denom))
    cy, cx = sy + t * vy, sx + t * vx
    return math.hypot(py - cy, px - cx)


def _simplify_polyline(
    points: Sequence[tuple[float, float]],
    epsilon: float,
) -> tuple[tuple[float, float], ...]:
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


def _unit_direction(points: Sequence[tuple[float, float]], head: bool) -> tuple[float, float]:
    if len(points) < 2:
        return (0.0, 0.0)
    p0, p1 = (points[0], points[1]) if head else (points[-2], points[-1])
    dy, dx = float(p1[0] - p0[0]), float(p1[1] - p0[1])
    norm = math.hypot(dy, dx)
    if norm <= 1e-12:
        return (0.0, 0.0)
    return (dy / norm, dx / norm)


def _endpoint_distance(a: Sequence[tuple[float, float]], b: Sequence[tuple[float, float]]) -> float:
    return min(
        math.hypot(a_end[0] - b_end[0], a_end[1] - b_end[1])
        for a_end in (a[0], a[-1])
        for b_end in (b[0], b[-1])
    )


def _orient_for_merge(
    a: tuple[tuple[float, float], ...],
    b: tuple[tuple[float, float], ...],
) -> tuple[tuple[tuple[float, float], ...], tuple[tuple[float, float], ...], float]:
    candidates = [
        (a, b, math.hypot(a[-1][0] - b[0][0], a[-1][1] - b[0][1])),
        (a, tuple(reversed(b)), math.hypot(a[-1][0] - b[-1][0], a[-1][1] - b[-1][1])),
        (tuple(reversed(a)), b, math.hypot(a[0][0] - b[0][0], a[0][1] - b[0][1])),
        (
            tuple(reversed(a)),
            tuple(reversed(b)),
            math.hypot(a[0][0] - b[-1][0], a[0][1] - b[-1][1]),
        ),
    ]
    return min(candidates, key=lambda item: item[2])


def _try_merge_segments(
    segments: list[OrderedSegment],
    endpoint_merge_distance: float,
    direction_cos_threshold: float,
) -> tuple[list[OrderedSegment], int]:
    if endpoint_merge_distance <= 0 or len(segments) < 2:
        return segments, 0

    pending = list(segments)
    merged_count = 0
    changed = True
    while changed:
        changed = False
        next_pending: list[OrderedSegment] = []
        used: set[int] = set()
        for i, current in enumerate(pending):
            if i in used:
                continue
            best_j = None
            best_dist = float("inf")
            best_pair: tuple[tuple[tuple[float, float], ...], tuple[tuple[float, float], ...]] | None = None
            for j, candidate in enumerate(pending):
                if i == j or j in used:
                    continue
                if _endpoint_distance(current.points, candidate.points) > endpoint_merge_distance:
                    continue
                a_points, b_points, dist = _orient_for_merge(current.points, candidate.points)
                tail = _unit_direction(a_points, head=False)
                head = _unit_direction(b_points, head=True)
                cos = tail[0] * head[0] + tail[1] * head[1]
                if cos >= direction_cos_threshold and dist < best_dist:
                    best_j = j
                    best_dist = dist
                    best_pair = (a_points, b_points)
            if best_j is None or best_pair is None:
                next_pending.append(current)
                used.add(i)
                continue
            a_points, b_points = best_pair
            combined = a_points + b_points[1:]
            source_ids = current.source_segment_ids + pending[best_j].source_segment_ids
            next_pending.append(
                OrderedSegment(
                    stroke_like_id=0,
                    order_index=0,
                    points=combined,
                    source_segment_ids=source_ids,
                )
            )
            used.add(i)
            used.add(best_j)
            merged_count += 1
            changed = True
        pending = next_pending

    return _assign_order(_sort_segments(pending)), merged_count


def _sort_segments(segments: Sequence[OrderedSegment]) -> list[OrderedSegment]:
    def key(segment: OrderedSegment) -> tuple[float, float, float]:
        arr = np.asarray(segment.points, dtype=float)
        min_y = float(arr[:, 0].min()) if len(arr) else 0.0
        min_x = float(arr[:, 1].min()) if len(arr) else 0.0
        length = _polyline_length(segment.points)
        return (min_y, min_x, -length)

    return sorted(segments, key=key)


def _assign_order(segments: Sequence[OrderedSegment]) -> list[OrderedSegment]:
    ordered: list[OrderedSegment] = []
    for idx, segment in enumerate(segments, start=1):
        ordered.append(
            OrderedSegment(
                stroke_like_id=idx,
                order_index=idx,
                points=segment.points,
                source_segment_ids=segment.source_segment_ids,
            )
        )
    return ordered


def simplify_and_order_segments(
    raw_segments: Sequence[TrialSegment],
    min_segment_length_px: float = 8.0,
    simplify_epsilon: float = 1.2,
    endpoint_merge_distance: float = 4.0,
    direction_cos_threshold: float = 0.65,
) -> tuple[list[OrderedSegment], dict[str, Any]]:
    kept: list[OrderedSegment] = []
    removed_short = 0
    for segment in raw_segments:
        length = _polyline_length(segment.points)
        if length < min_segment_length_px or len(segment.points) < 2:
            removed_short += 1
            continue
        simplified = _simplify_polyline(segment.points, simplify_epsilon)
        kept.append(
            OrderedSegment(
                stroke_like_id=0,
                order_index=0,
                points=simplified,
                source_segment_ids=(segment.segment_id,),
            )
        )

    sorted_kept = _assign_order(_sort_segments(kept))
    merged, merged_count = _try_merge_segments(
        sorted_kept,
        endpoint_merge_distance=endpoint_merge_distance,
        direction_cos_threshold=direction_cos_threshold,
    )
    metrics = {
        "raw_segment_count": len(raw_segments),
        "simplified_segment_count": len(merged),
        "ordered_stroke_like_count": len(merged),
        "removed_short_segment_count": removed_short,
        "merged_segment_count": merged_count,
        "total_path_length_px": round(sum(_polyline_length(seg.points) for seg in merged), 6),
    }
    return merged, metrics


def _write_ordered_csv(path: Path, segments: Sequence[OrderedSegment]) -> tuple[int, int]:
    rows: list[dict[str, Any]] = []
    point_count = 0
    break_count = 0
    for segment in segments:
        for point_index, (y, x) in enumerate(segment.points):
            rows.append(
                {
                    "y": round(float(y), 6),
                    "x": round(float(x), 6),
                    "stroke_like_id": segment.stroke_like_id,
                    "point_index": point_index,
                    "is_break": 0,
                    "order_index": segment.order_index,
                    "source": "font_skeleton_ordering_trial",
                }
            )
            point_count += 1
        rows.append(
            {
                "y": "nan",
                "x": "nan",
                "stroke_like_id": segment.stroke_like_id,
                "point_index": "",
                "is_break": 1,
                "order_index": segment.order_index,
                "source": "font_skeleton_ordering_trial",
            }
        )
        break_count += 1
    _write_csv(path, rows, ORDERED_FIELDS)
    return point_count, break_count


def _draw_segments(
    ax: Any,
    segments: Sequence[Sequence[tuple[float, float]]],
    label_order: bool = False,
    title: str = "",
) -> None:
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.invert_yaxis()
    colors = plt.cm.tab10(np.linspace(0, 1, max(1, len(segments))))
    for idx, points in enumerate(segments, start=1):
        arr = np.asarray(points, dtype=float)
        if len(arr) < 2:
            continue
        color = colors[(idx - 1) % len(colors)]
        ax.plot(arr[:, 1], arr[:, 0], linewidth=1.8, color=color)
        ax.scatter(arr[:, 1], arr[:, 0], s=5, color=color)
        if label_order:
            mid = arr[len(arr) // 2]
            ax.text(
                mid[1],
                mid[0],
                str(idx),
                fontsize=8,
                color="#111111",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75, "pad": 1},
            )


def _load_reference_image(path: Path) -> np.ndarray | None:
    if not path.exists():
        return None
    try:
        return plt.imread(path)
    except Exception:
        return None


def _write_compare_figure(
    char: str,
    style: str,
    source_compare: Path,
    raw_segments: Sequence[TrialSegment],
    ordered_segments: Sequence[OrderedSegment],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 4, figsize=(13.0, 3.6), dpi=150)
    reference = _load_reference_image(source_compare)
    axes[0].set_title("previous trial reference\n(median/mask/skeleton/path)", fontsize=8)
    axes[0].set_xticks([])
    axes[0].set_yticks([])
    if reference is not None:
        axes[0].imshow(reference)
    else:
        axes[0].text(0.5, 0.5, "reference image\nnot available", ha="center", va="center")
    _draw_segments(
        axes[1],
        [segment.points for segment in raw_segments],
        label_order=True,
        title="raw trial segments",
    )
    _draw_segments(
        axes[2],
        [segment.points for segment in ordered_segments],
        label_order=True,
        title="simplified candidate order",
    )
    _draw_segments(
        axes[3],
        [segment.points for segment in raw_segments],
        label_order=False,
        title="raw (thin) vs ordered (bold)",
    )
    for segment in ordered_segments:
        arr = np.asarray(segment.points, dtype=float)
        if len(arr) >= 2:
            axes[3].plot(arr[:, 1], arr[:, 0], linewidth=2.3, color="#d62728", alpha=0.85)
    fig.suptitle(f"{_char_id(char)} / {style} stroke ordering prototype", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(path)
    plt.close(fig)


def _write_report(path: Path, output_dir: Path, rows: Sequence[dict[str, Any]]) -> None:
    lines = [
        "# Font skeleton stroke ordering / simplification prototype",
        "",
        "本轮只处理 `人/kaishu` 和 `山/lishu` 两个极小样本。",
        "",
        "## 边界说明",
        "",
        "- 这仍不是正式轨迹，不生成正式 `trajectory.csv`。",
        "- 这不是真实笔顺恢复，只是一个 `candidate writable order`。",
        "- 本轮不接默认 pipeline，不替换 MakeMeAHanzi median。",
        "- 本轮不接机器人，不生成 execution/workspace/CoppeliaSim/AUBO 文件。",
        "",
        "## 输出目录",
        "",
        f"`{output_dir}`",
        "",
        "## 样本结果",
        "",
        "| char | style | raw_segment_count | simplified_segment_count | ordered_stroke_like_count | warning | recommended_for_next_stage | compare |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {char} | {style} | {raw_segment_count} | {simplified_segment_count} | "
            "{ordered_stroke_like_count} | {warning} | {recommended_for_next_stage} | `{compare_png}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## 人工看图问题",
            "",
            "- segment 是否明显少了？",
            "- 顺序是否比 raw trial 更像可写？",
            "- 是否保留字体风格？",
            "- 是否还过碎？",
            "- 是否值得进入下一步 font-derived execution mock？",
            "",
            "## 初步建议",
            "",
            "如果人工看图认为两个样本的候选顺序比 raw trial 更可写，可以进入一个仍然离线的 font-derived execution mock；",
            "如果仍然过碎或顺序明显不自然，应先继续做 graph simplification 与人工 stroke grouping。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(paper_dir: Path, output_dir: Path, summary_csv: Path, report_md: Path, rows: Sequence[dict[str, Any]]) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    index_path = paper_dir / "font_skeleton_stroke_ordering_index.md"
    lines = [
        "# Font skeleton stroke ordering prototype index",
        "",
        "本索引固定 font-outline basis 主线中极小样本 stroke ordering / simplification prototype 的结果。",
        "",
        "## Source",
        "",
        f"- Output directory: `{output_dir}`",
        f"- Summary: `{summary_csv}`",
        f"- Report: `{report_md}`",
        "",
        "## Samples",
        "",
        "| char | style | raw -> simplified | ordered_stroke_like_count | compare |",
        "|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['char']} | {row['style']} | {row['raw_segment_count']} -> "
            f"{row['simplified_segment_count']} | {row['ordered_stroke_like_count']} | "
            f"`{row['compare_png']}` |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "该结果不是正式轨迹，不是真实笔顺恢复，也不接机器人；仅用于人工判断字体骨架是否能整理成更可写的候选路径。",
        ]
    )
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index_path


def run_font_skeleton_stroke_ordering(
    trial_dir: Path | str = DEFAULT_TRIAL_DIR,
    output_dir: Path | str | None = None,
    sample_specs: Sequence[tuple[str, str]] = DEFAULT_SAMPLE_SPECS,
    min_segment_length_px: float = 8.0,
    simplify_epsilon: float = 1.2,
    endpoint_merge_distance: float = 4.0,
    direction_cos_threshold: float = 0.65,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    trial_dir = Path(trial_dir)
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"font_skeleton_stroke_ordering_{timestamp}"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for char, style in sample_specs:
        char_id = _char_id(char)
        sample_name = f"{char_id}_{style}"
        source_dir = trial_dir / sample_name
        source_csv = source_dir / "font_derived_trial_trajectory.csv"
        if not source_csv.exists():
            raise FileNotFoundError(f"Missing trial CSV for {sample_name}: {source_csv}")

        sample_dir = output_dir / sample_name
        sample_dir.mkdir(parents=True, exist_ok=True)
        raw_segments = _read_trial_segments(source_csv)
        ordered_segments, metrics = simplify_and_order_segments(
            raw_segments,
            min_segment_length_px=min_segment_length_px,
            simplify_epsilon=simplify_epsilon,
            endpoint_merge_distance=endpoint_merge_distance,
            direction_cos_threshold=direction_cos_threshold,
        )

        warnings: list[str] = []
        if not ordered_segments:
            warnings.append("no_ordered_segments")
        if metrics["simplified_segment_count"] == metrics["raw_segment_count"]:
            warnings.append("segment_count_unchanged")
        if metrics["simplified_segment_count"] > 6:
            warnings.append("still_fragmented")

        ordered_csv = sample_dir / "font_skeleton_ordered_trial_trajectory.csv"
        summary_json = sample_dir / "font_skeleton_ordering_summary.json"
        compare_png = sample_dir / "font_skeleton_ordering_compare.png"
        point_count, break_count = _write_ordered_csv(ordered_csv, ordered_segments)
        _write_compare_figure(
            char,
            style,
            source_dir / "font_derived_trial_compare.png",
            raw_segments,
            ordered_segments,
            compare_png,
        )

        recommended = bool(ordered_segments) and metrics["simplified_segment_count"] <= max(5, metrics["raw_segment_count"])
        summary = {
            "char": char,
            "char_id": char_id,
            "style": style,
            "raw_segment_count": metrics["raw_segment_count"],
            "simplified_segment_count": metrics["simplified_segment_count"],
            "ordered_stroke_like_count": metrics["ordered_stroke_like_count"],
            "removed_short_segment_count": metrics["removed_short_segment_count"],
            "merged_segment_count": metrics["merged_segment_count"],
            "point_count": point_count,
            "break_count": break_count,
            "total_path_length_px": metrics["total_path_length_px"],
            "warning": ";".join(warnings),
            "recommended_for_next_stage": recommended,
            "source_trial_dir": str(source_dir),
            "source_trial_csv": str(source_csv),
            "scope": "diagnostic candidate writable order only; not formal trajectory; no robot",
        }
        summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        row = {
            **summary,
            "sample_dir": str(sample_dir),
            "ordered_csv": str(ordered_csv),
            "summary_json": str(summary_json),
            "compare_png": str(compare_png),
        }
        summary_rows.append(row)
        manifest_rows.append(
            {
                "char": char,
                "char_id": char_id,
                "style": style,
                "sample_dir": str(sample_dir),
                "source_trial_csv": str(source_csv),
                "ordered_csv": str(ordered_csv),
                "compare_png": str(compare_png),
                "warning": summary["warning"],
            }
        )

    summary_csv = output_dir / "font_skeleton_ordering_summary.csv"
    manifest_csv = output_dir / "font_skeleton_ordering_manifest.csv"
    report_md = output_dir / "font_skeleton_ordering_report.md"
    _write_csv(summary_csv, summary_rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, output_dir, summary_rows)

    paper_index = ""
    if copy_to_paper:
        paper_index_path = _write_paper_index(DEFAULT_PAPER_DIR, output_dir, summary_csv, report_md, summary_rows)
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "font_skeleton_ordering_report.md")
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "font_skeleton_ordering_summary.csv")
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
    parser.add_argument("--trial-dir", type=Path, default=DEFAULT_TRIAL_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--min-segment-length-px", type=float, default=8.0)
    parser.add_argument("--simplify-epsilon", type=float, default=1.2)
    parser.add_argument("--endpoint-merge-distance", type=float, default=4.0)
    parser.add_argument("--direction-cos-threshold", type=float, default=0.65)
    parser.add_argument("--no-paper-copy", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_font_skeleton_stroke_ordering(
        trial_dir=args.trial_dir,
        output_dir=args.out_dir,
        min_segment_length_px=args.min_segment_length_px,
        simplify_epsilon=args.simplify_epsilon,
        endpoint_merge_distance=args.endpoint_merge_distance,
        direction_cos_threshold=args.direction_cos_threshold,
        copy_to_paper=not args.no_paper_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
