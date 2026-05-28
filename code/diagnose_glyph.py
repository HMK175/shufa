"""Visual diagnostics for one glyph image.

The script does not change extraction logic. It reuses the existing pipeline
steps and renders intermediate state so failures can be attributed to
binarization/skeletonization, topology, stroke parsing, or smoothing.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pipeline import BLUR_KSIZE, SAMPLE, SMOOTH
from skeleton import clean_junction_spurs, skeletonize, straighten_junctions
from stroke import (
    _cluster_junc_pixels,
    _expected_count_for_context,
    _extract_strokes_global,
    _extract_strokes_legacy,
    build_skeleton_graph,
    get_last_trace_diagnostics,
    get_stroke_list,
    prune_skeleton,
    set_trace_context,
)
from stroke_knowledge import _split_cross_component, get_stroke_count, guided_merge
from trajectory import smooth_strokes
from utils import estimate_stroke_width, load_image, preprocess


def _stroke_stats(strokes: Iterable[np.ndarray]) -> List[dict]:
    rows = []
    for idx, stroke in enumerate(strokes, 1):
        pts = np.array(stroke, dtype=float)
        if len(pts) < 2:
            path_len = 0.0
            endpoint = 0.0
            winding = 0.0
        else:
            path_len = float(np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1)))
            endpoint = float(np.linalg.norm(pts[-1] - pts[0]))
            winding = path_len / endpoint if endpoint > 1 else 999.0
        rows.append(
            {
                "idx": idx,
                "points": int(len(pts)),
                "length": path_len,
                "endpoint": endpoint,
                "winding": winding,
            }
        )
    return rows


def _max_winding(strokes: Iterable[np.ndarray]) -> float:
    stats = _stroke_stats(strokes)
    return max((row["winding"] for row in stats), default=0.0)


def _plot_strokes(ax, strokes: List[np.ndarray], title: str, annotate: bool = False):
    ax.set_facecolor("black")
    if strokes:
        colors = plt.cm.tab20(np.linspace(0, 1, max(len(strokes), 1)))
        for idx, stroke in enumerate(strokes):
            pts = np.array(stroke, dtype=float)
            if len(pts) == 0:
                continue
            ax.plot(pts[:, 1], pts[:, 0], "-", color=colors[idx], linewidth=1.2)
            ax.scatter(pts[0, 1], pts[0, 0], s=12, color="white", marker="o")
            ax.scatter(pts[-1, 1], pts[-1, 0], s=14, color="yellow", marker="x")
            if annotate:
                mid = pts[len(pts) // 2]
                stat = _stroke_stats([pts])[0]
                ax.text(
                    mid[1],
                    mid[0],
                    f"S{idx + 1}\nw={stat['winding']:.2f}",
                    color="white",
                    fontsize=6,
                    ha="center",
                )
    ax.set_title(title)
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.axis("off")


def _format_stats(label: str, strokes: List[np.ndarray], limit: int = 12) -> List[str]:
    rows = _stroke_stats(strokes)
    lines = [f"{label}: count={len(rows)}, max_w={_max_winding(strokes):.2f}"]
    for row in rows[:limit]:
        lines.append(
            f"  S{row['idx']}: len={row['length']:.1f}, "
            f"se={row['endpoint']:.1f}, w={row['winding']:.2f}, "
            f"pts={row['points']}"
        )
    if len(rows) > limit:
        lines.append(f"  ... {len(rows) - limit} more")
    return lines


def _subset_name(image_path: Path) -> str:
    parts = {part.lower() for part in image_path.parts}
    if "tune_set" in parts:
        return "tune"
    if "holdout_set" in parts:
        return "holdout"
    return "unknown"


def diagnose(image_path: Path, output_dir: Path) -> Tuple[Path, Path]:
    name = image_path.stem
    subset = _subset_name(image_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    img = load_image(str(image_path))
    binary = preprocess(img, blur_ksize=BLUR_KSIZE)
    half_width = estimate_stroke_width(binary)
    skeleton_raw = skeletonize(binary)
    skeleton = prune_skeleton(
        skeleton_raw,
        min_branch_len=max(30, int(half_width * 1.8)),
    )
    skeleton = straighten_junctions(skeleton)
    skeleton = clean_junction_spurs(skeleton)

    graph = build_skeleton_graph(skeleton)
    endpoints = [pt for pt, nb in graph.items() if len(nb) == 1]
    junctions = {pt for pt, nb in graph.items() if len(nb) >= 3}
    clusters = _cluster_junc_pixels(junctions, graph) if junctions else []

    expected_for_global = _expected_count_for_context(name)
    expected_for_count = get_stroke_count(name)

    legacy = [np.array(stroke) for stroke in _extract_strokes_legacy(skeleton)]
    global_strokes = [
        np.array(stroke)
        for stroke in _extract_strokes_global(
            skeleton,
            expected_count=expected_for_global,
        )
    ]

    set_trace_context(name)
    selected = [np.array(stroke) for stroke in get_stroke_list(skeleton)]
    diag = get_last_trace_diagnostics()

    min_stroke_len = max(30, int(half_width * 2.5))
    final_raw = [stroke for stroke in selected if len(stroke) >= min_stroke_len]
    final_raw = _split_cross_component(final_raw, name)
    if expected_for_count and len(final_raw) != expected_for_count:
        final_raw = guided_merge(final_raw, name)
    final = smooth_strokes(final_raw, total_points=SAMPLE, s=SMOOTH)

    png_path = output_dir / f"diagnose_{subset}_{name}.png"
    txt_path = output_dir / f"diagnose_{subset}_{name}.txt"

    fig, axes = plt.subplots(2, 4, figsize=(18, 10))
    axes = axes.ravel()

    axes[0].imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    axes[0].set_title("Original")
    axes[0].axis("off")

    axes[1].imshow(binary, cmap="gray")
    axes[1].set_title(f"Binary fg={int(np.sum(binary > 0))}")
    axes[1].axis("off")

    axes[2].imshow(skeleton, cmap="gray")
    axes[2].set_title(f"Skeleton px={len(graph)}")
    axes[2].axis("off")

    axes[3].imshow(skeleton, cmap="gray")
    if endpoints:
        ey, ex = zip(*endpoints)
        axes[3].scatter(ex, ey, s=18, c="lime", label="endpoints")
    cmap = plt.cm.get_cmap("tab20", max(len(clusters), 1))
    for ci, cluster in enumerate(clusters):
        if not cluster:
            continue
        cy, cx = zip(*cluster)
        axes[3].scatter(cx, cy, s=14, color=cmap(ci), label=f"J{ci}")
    axes[3].set_title(f"Keypoints ep={len(endpoints)}, jpx={len(junctions)}, clusters={len(clusters)}")
    axes[3].invert_yaxis()
    axes[3].axis("off")

    _plot_strokes(
        axes[4],
        legacy,
        f"Legacy raw ({len(legacy)}, max_w={_max_winding(legacy):.2f})",
    )
    _plot_strokes(
        axes[5],
        global_strokes,
        f"Global raw ({len(global_strokes)}, max_w={_max_winding(global_strokes):.2f})",
    )
    _plot_strokes(
        axes[6],
        final,
        f"Final smoothed ({len(final)}, max_w={_max_winding(final):.2f})",
        annotate=True,
    )

    selected_summary = diag.get("selected", {})
    lines = [
        f"char={name} subset={subset}",
        f"expected={expected_for_count if expected_for_count is not None else '-'}",
        f"method={diag.get('method', '-')}",
        f"pred={selected_summary.get('count', '-')}",
        f"fallback={diag.get('fallback_reason') or 'none'}",
        f"skeleton_px={len(graph)} endpoints={len(endpoints)}",
        f"junction_px={len(junctions)} clusters={len(clusters)}",
        "",
        *_format_stats("Final", final, limit=8),
    ]
    axes[7].axis("off")
    axes[7].text(0, 1, "\n".join(lines), va="top", family="monospace", fontsize=9)
    axes[7].set_title("Metrics")

    fig.tight_layout()
    fig.savefig(png_path, dpi=160)
    plt.close(fig)

    txt_lines = [
        f"image={image_path}",
        f"char={name}",
        f"subset={subset}",
        f"expected={expected_for_count if expected_for_count is not None else ''}",
        f"method={diag.get('method', '')}",
        f"pred={selected_summary.get('count', '')}",
        f"fallback={diag.get('fallback_reason') or 'none'}",
        f"skeleton_px={len(graph)}",
        f"endpoints={len(endpoints)}",
        f"junction_px={len(junctions)}",
        f"junction_clusters={len(clusters)}",
        f"final_count={len(final)}",
        f"final_max_winding={_max_winding(final):.2f}",
        "",
        *_format_stats("Legacy", legacy),
        "",
        *_format_stats("Global", global_strokes),
        "",
        *_format_stats("Selected raw", selected),
        "",
        *_format_stats("Final", final),
    ]
    txt_path.write_text("\n".join(txt_lines) + "\n", encoding="utf-8")

    print(f"wrote {png_path}")
    print(f"wrote {txt_path}")
    print(
        f"{name}: method={diag.get('method', '-')}, "
        f"pred={selected_summary.get('count', '-')}, "
        f"final={len(final)}, max_w={_max_winding(final):.2f}, "
        f"ep={len(endpoints)}, jpx={len(junctions)}, clusters={len(clusters)}"
    )
    return png_path, txt_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render glyph diagnostics")
    parser.add_argument("image", help="Input glyph image")
    parser.add_argument(
        "--output-dir",
        default=str(SCRIPT_DIR / "output" / "diagnostics"),
        help="Directory for diagnostic PNG/TXT outputs",
    )
    args = parser.parse_args()
    diagnose(Path(args.image), Path(args.output_dir))


if __name__ == "__main__":
    main()
