"""Generate ordered trajectories from makemeahanzi structured stroke data.

This is an independent pipeline for the structured-data route:
graphics.txt -> per-stroke medians -> optional smoothing -> CSV/preview.
It does not call or modify the original image pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
import numpy as np

from import_makemeahanzi import svg_path_to_mpl
from trajectory import smooth_strokes


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_GRAPHICS = SCRIPT_DIR / "data" / "makemeahanzi" / "graphics.txt"
DEFAULT_OUT_DIR = SCRIPT_DIR / "output" / "makemeahanzi_traj"


@dataclass
class GlyphData:
    char: str
    char_id: str
    strokes: List[str]
    medians: List[np.ndarray]


@dataclass
class GlyphResult:
    char: str
    char_id: str
    stroke_count: int
    total_points: int
    smoothed_points: int
    path_length: float
    output_csv: Path
    output_img: Path
    smooth_method: str


def _safe_char_id(char: str) -> str:
    if char and char.isascii() and re.match(r"^[A-Za-z0-9_-]+$", char):
        return char
    if len(char) == 1:
        return f"u{ord(char):04x}"
    return "u" + "_".join(f"{ord(ch):04x}" for ch in char)


def _parse_chars(text: str) -> List[str]:
    seen = set()
    chars: List[str] = []
    for ch in text:
        if ch.isspace() or ch == ",":
            continue
        if ch not in seen:
            chars.append(ch)
            seen.add(ch)
    return chars


def _load_chars_file(path: Path) -> List[str]:
    return _parse_chars(path.read_text(encoding="utf-8"))


def _iter_graphics(path: Path) -> Iterable[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"skip invalid JSON line {line_no}: {exc}")


def _as_median_array(median: object) -> np.ndarray:
    pts = np.asarray(median, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2:
        return np.empty((0, 2), dtype=float)
    return pts


def load_glyphs(graphics: Path, chars: Sequence[str]) -> Tuple[List[GlyphData], List[str]]:
    wanted = set(chars)
    found: Dict[str, GlyphData] = {}

    for item in _iter_graphics(graphics):
        char = item.get("character")
        if not isinstance(char, str) or char not in wanted or char in found:
            continue
        strokes_raw = item.get("strokes") or []
        medians_raw = item.get("medians") or []
        if not isinstance(strokes_raw, list) or not isinstance(medians_raw, list):
            continue
        strokes = [str(path_text) for path_text in strokes_raw]
        medians = [_as_median_array(median) for median in medians_raw]
        found[char] = GlyphData(
            char=char,
            char_id=_safe_char_id(char),
            strokes=strokes,
            medians=medians,
        )
        if len(found) == len(wanted):
            break

    glyphs = [found[ch] for ch in chars if ch in found]
    missing = [ch for ch in chars if ch not in found]
    return glyphs, missing


def _path_extents(paths: Sequence[MplPath], medians: Sequence[np.ndarray]) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for path in paths:
        if len(path.vertices):
            vertices = np.asarray(path.vertices, dtype=float)
            xs.extend(vertices[:, 0].tolist())
            ys.extend(vertices[:, 1].tolist())
    for median in medians:
        if len(median):
            xs.extend(median[:, 0].tolist())
            ys.extend(median[:, 1].tolist())

    if not xs or not ys:
        return 0.0, 1024.0, 0.0, 1024.0
    return min(xs), max(xs), min(ys), max(ys)


def _make_transform(
    paths: Sequence[MplPath],
    medians: Sequence[np.ndarray],
    image_size: int,
    margin_ratio: float = 0.08,
):
    x0, x1, y0, y1 = _path_extents(paths, medians)
    width = max(x1 - x0, 1.0)
    height = max(y1 - y0, 1.0)
    span = max(width, height)
    margin = image_size * margin_ratio
    scale = (image_size - 2.0 * margin) / span
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0

    def transform_points(points_xy: np.ndarray) -> np.ndarray:
        pts = np.asarray(points_xy, dtype=float)
        if pts.size == 0:
            return np.empty((0, 2), dtype=float)
        out = np.empty_like(pts, dtype=float)
        out[:, 0] = (pts[:, 0] - cx) * scale + image_size / 2.0
        out[:, 1] = image_size / 2.0 - (pts[:, 1] - cy) * scale
        return out

    return transform_points


def _transform_path(path: MplPath, transform_points) -> MplPath:
    vertices = np.asarray(path.vertices, dtype=float)
    if len(vertices) == 0:
        return path
    return MplPath(transform_points(vertices), path.codes)


def _medians_to_image_strokes(glyph: GlyphData, image_size: int) -> Tuple[List[MplPath], List[np.ndarray]]:
    paths = [svg_path_to_mpl(path_text) for path_text in glyph.strokes]
    transform_points = _make_transform(paths, glyph.medians, image_size)
    image_paths = [_transform_path(path, transform_points) for path in paths]
    image_strokes = []
    for median in glyph.medians:
        pts_xy = transform_points(median)
        image_strokes.append(pts_xy[:, [1, 0]])  # y, x for this project
    return image_paths, image_strokes


def _stroke_path_length(stroke: np.ndarray) -> float:
    if len(stroke) < 2:
        return 0.0
    diffs = np.diff(stroke.astype(float), axis=0)
    return float(np.linalg.norm(diffs, axis=1).sum())


def _total_path_length(strokes: Sequence[np.ndarray]) -> float:
    return sum(_stroke_path_length(stroke) for stroke in strokes)


def _linear_resample_stroke(stroke: np.ndarray, target_points: int) -> np.ndarray:
    """Resample one polyline by arc length without changing its shape."""
    pts = np.asarray(stroke, dtype=float)
    if len(pts) <= 1:
        return pts.copy()

    target_points = max(2, int(target_points))
    diffs = np.diff(pts, axis=0)
    seg_lengths = np.linalg.norm(diffs, axis=1)
    total_length = float(seg_lengths.sum())
    if total_length <= 1e-9:
        return np.repeat(pts[:1], target_points, axis=0)

    keep = np.concatenate([[True], seg_lengths > 1e-9])
    pts = pts[keep]
    if len(pts) <= 1:
        return np.repeat(pts[:1], target_points, axis=0)

    seg_lengths = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg_lengths)])
    sample_arc = np.linspace(0.0, arc[-1], target_points)
    y = np.interp(sample_arc, arc, pts[:, 0])
    x = np.interp(sample_arc, arc, pts[:, 1])
    out = np.column_stack([y, x])
    out[0] = pts[0]
    out[-1] = pts[-1]
    return out


def _target_points_for_linear(stroke: np.ndarray) -> int:
    """Choose a modest density from path length while preserving raw endpoints."""
    if len(stroke) <= 1:
        return len(stroke)
    length = _stroke_path_length(stroke)
    by_length = int(math.ceil(length / 4.0)) + 1
    by_raw = len(stroke) * 2
    return max(len(stroke), min(max(by_length, by_raw), 160))


def linear_resample_strokes(strokes: Sequence[np.ndarray]) -> List[np.ndarray]:
    return [_linear_resample_stroke(stroke, _target_points_for_linear(stroke)) for stroke in strokes]


def _write_strokes_csv(strokes: Sequence[np.ndarray], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["y", "x"])
        for stroke in strokes:
            for y, x in stroke:
                writer.writerow([f"{float(y):.3f}", f"{float(x):.3f}"])
            writer.writerow(["nan", "nan"])


def _map_workspace_strokes(
    strokes: Sequence[np.ndarray],
    image_size: int,
    workspace_map: Tuple[float, float, float, float],
) -> List[np.ndarray]:
    x_min, x_max, y_min, y_max = workspace_map
    mapped: List[np.ndarray] = []
    for stroke in strokes:
        if len(stroke) == 0:
            mapped.append(stroke.copy())
            continue
        out = np.empty_like(stroke, dtype=float)
        out[:, 0] = y_min + (stroke[:, 0] / image_size) * (y_max - y_min)
        out[:, 1] = x_min + (stroke[:, 1] / image_size) * (x_max - x_min)
        mapped.append(out)
    return mapped


def _parse_workspace_map(value: Optional[str]) -> Optional[Tuple[float, float, float, float]]:
    if not value:
        return None
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        raise ValueError("--workspace-map expects x_min,x_max,y_min,y_max")
    return tuple(float(p) for p in parts)  # type: ignore[return-value]


def render_glyph(paths: Sequence[MplPath], out_path: Path, image_size: int, active_index: Optional[int] = None) -> None:
    fig = Figure(figsize=(image_size / 100.0, image_size / 100.0), dpi=100)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("white")
    for idx, path in enumerate(paths):
        color = "black" if active_index is None or idx == active_index else "#d0d0d0"
        ax.add_patch(PathPatch(path, facecolor=color, edgecolor=color, lw=0.8))
    ax.set_xlim(0, image_size)
    ax.set_ylim(image_size, 0)
    ax.set_aspect("equal")
    ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(str(out_path))


def render_trajectory(
    paths: Sequence[MplPath],
    medians: Sequence[np.ndarray],
    final_strokes: Sequence[np.ndarray],
    out_path: Path,
    image_size: int,
    smooth_method: str,
) -> None:
    fig = Figure(figsize=(6.0, 6.0), dpi=140)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0.04, 0.04, 0.92, 0.92])
    ax.set_facecolor("white")

    for path in paths:
        ax.add_patch(PathPatch(path, facecolor="#eeeeee", edgecolor="#c8c8c8", lw=0.6, zorder=1))

    colors = matplotlib.colormaps["tab20"].colors
    for idx, median in enumerate(medians):
        color = colors[idx % len(colors)]
        if len(median):
            ax.plot(median[:, 1], median[:, 0], "--", color=color, lw=1.0, alpha=0.65, zorder=3)
        if idx < len(final_strokes) and len(final_strokes[idx]):
            stroke = final_strokes[idx]
            ax.plot(stroke[:, 1], stroke[:, 0], "-", color=color, lw=2.0, zorder=4)
            ax.scatter(stroke[0, 1], stroke[0, 0], s=26, marker="o", color=color, edgecolor="black", zorder=5)
            ax.scatter(stroke[-1, 1], stroke[-1, 0], s=32, marker="x", color=color, zorder=5)
            label_y, label_x = stroke[0]
        elif len(median):
            label_y, label_x = median[0]
        else:
            continue
        ax.text(label_x, label_y, str(idx + 1), fontsize=9, weight="bold", color="black", zorder=6)

    ax.set_xlim(0, image_size)
    ax.set_ylim(image_size, 0)
    ax.set_aspect("equal")
    ax.set_title(f"smooth_method={smooth_method}", fontsize=11)
    ax.axis("off")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.print_png(str(out_path))


def process_glyph(
    glyph: GlyphData,
    out_dir: Path,
    image_size: int,
    smooth_method: str,
    workspace_map: Optional[Tuple[float, float, float, float]],
) -> GlyphResult:
    image_paths, median_strokes = _medians_to_image_strokes(glyph, image_size)
    stroke_count = min(len(glyph.strokes), len(glyph.medians))
    median_strokes = median_strokes[:stroke_count]
    image_paths = image_paths[: len(glyph.strokes)]

    char_id = glyph.char_id
    median_csv = out_dir / f"{char_id}_median.csv"
    smoothed_csv = out_dir / f"{char_id}_smoothed.csv"
    trajectory_csv = out_dir / f"{char_id}_trajectory.csv"
    glyph_png = out_dir / f"{char_id}_glyph.png"
    trajectory_png = out_dir / f"{char_id}_trajectory.png"

    _write_strokes_csv(median_strokes, median_csv)

    if smooth_method == "none":
        final_strokes = [stroke.copy() for stroke in median_strokes]
    elif smooth_method == "linear":
        final_strokes = linear_resample_strokes(median_strokes)
    elif smooth_method == "bspline":
        target_points = max(sum(len(s) for s in median_strokes) * 8, stroke_count * 32, 1)
        final_strokes = smooth_strokes(list(median_strokes), total_points=target_points, s=1.0)
    else:
        raise ValueError(f"unknown smooth_method: {smooth_method}")

    if smooth_method != "none":
        _write_strokes_csv(final_strokes, smoothed_csv)

    _write_strokes_csv(final_strokes, trajectory_csv)

    if workspace_map is not None:
        workspace_strokes = _map_workspace_strokes(final_strokes, image_size, workspace_map)
        _write_strokes_csv(workspace_strokes, out_dir / f"{char_id}_workspace.csv")

    render_glyph(image_paths, glyph_png, image_size)
    for idx in range(len(image_paths)):
        render_glyph(image_paths, out_dir / f"{char_id}_stroke_{idx + 1:02d}.png", image_size, active_index=idx)
    render_trajectory(image_paths, median_strokes, final_strokes, trajectory_png, image_size, smooth_method)

    return GlyphResult(
        char=glyph.char,
        char_id=char_id,
        stroke_count=stroke_count,
        total_points=sum(len(stroke) for stroke in median_strokes),
        smoothed_points=sum(len(stroke) for stroke in final_strokes),
        path_length=_total_path_length(final_strokes),
        output_csv=trajectory_csv,
        output_img=trajectory_png,
        smooth_method=smooth_method,
    )


def write_summary(results: Sequence[GlyphResult], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "char",
                "stroke_count",
                "total_points",
                "smoothed_points",
                "path_length",
                "output_csv",
                "output_img",
                "smooth_method",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "char": result.char,
                    "stroke_count": result.stroke_count,
                    "total_points": result.total_points,
                    "smoothed_points": result.smoothed_points,
                    "path_length": f"{result.path_length:.3f}",
                    "output_csv": str(result.output_csv),
                    "output_img": str(result.output_img),
                    "smooth_method": result.smooth_method,
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate trajectories from makemeahanzi graphics.txt")
    parser.add_argument("--graphics", default=str(DEFAULT_GRAPHICS), help="Path to makemeahanzi graphics.txt")
    parser.add_argument("--char", default=None, help="Single Chinese character to process")
    parser.add_argument("--chars-file", default=None, help="UTF-8 text file containing characters to process")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument(
        "--smooth",
        action="store_true",
        help="Compatibility flag; equivalent to --smooth-method linear unless --smooth-method is set.",
    )
    parser.add_argument(
        "--smooth-method",
        choices=["none", "linear", "bspline"],
        default=None,
        help="Trajectory refinement method. Default: linear arc-length resampling.",
    )
    parser.add_argument(
        "--workspace-map",
        default=None,
        help="Optional x_min,x_max,y_min,y_max mapping from image pixels to robot workspace",
    )
    args = parser.parse_args()

    graphics = Path(args.graphics)
    out_dir = Path(args.out_dir)
    if not graphics.exists():
        print(f"graphics.txt not found: {graphics}")
        return 2

    chars: List[str] = []
    if args.char:
        chars.extend(_parse_chars(args.char))
    if args.chars_file:
        chars.extend(_load_chars_file(Path(args.chars_file)))
    chars = list(dict.fromkeys(chars))
    if not chars:
        print("No character specified. Use --char or --chars-file.")
        return 2

    workspace_map = _parse_workspace_map(args.workspace_map)
    smooth_method = args.smooth_method or "linear"
    if args.smooth and args.smooth_method is None:
        smooth_method = "linear"
    out_dir.mkdir(parents=True, exist_ok=True)

    glyphs, missing = load_glyphs(graphics, chars)
    if missing:
        print(f"missing chars in graphics.txt: {''.join(missing)}")
    if not glyphs:
        print("No matching glyphs found.")
        return 1

    results = []
    for glyph in glyphs:
        try:
            result = process_glyph(glyph, out_dir, args.image_size, smooth_method, workspace_map)
            results.append(result)
            print(
                f"{glyph.char} ({glyph.char_id}): strokes={result.stroke_count}, "
                f"points={result.total_points}, smoothed={result.smoothed_points}, "
                f"path_length={result.path_length:.1f}, smooth_method={smooth_method}"
            )
        except Exception as exc:
            print(f"failed {glyph.char} ({glyph.char_id}): {exc}")

    summary_path = out_dir / "summary.csv"
    write_summary(results, summary_path)
    print(f"wrote summary: {summary_path}")
    print(f"processed={len(results)}, missing={len(missing)}")
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
