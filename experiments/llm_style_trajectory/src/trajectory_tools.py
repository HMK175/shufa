"""Deterministic trajectory tools for parameterized style demos."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np


def normalize_medians(medians_xy: Sequence[np.ndarray], image_size: int = 256, margin_ratio: float = 0.08) -> list[np.ndarray]:
    xs: list[float] = []
    ys: list[float] = []
    for stroke in medians_xy:
        if len(stroke):
            xs.extend(stroke[:, 0].tolist())
            ys.extend(stroke[:, 1].tolist())
    if not xs or not ys:
        return []

    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    span = max(x1 - x0, y1 - y0, 1.0)
    margin = image_size * margin_ratio
    scale = (image_size - 2.0 * margin) / span
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0

    out: list[np.ndarray] = []
    for stroke in medians_xy:
        pts = np.asarray(stroke, dtype=float)
        mapped = np.empty_like(pts, dtype=float)
        mapped[:, 0] = image_size / 2.0 - (pts[:, 1] - cy) * scale
        mapped[:, 1] = (pts[:, 0] - cx) * scale + image_size / 2.0
        out.append(mapped)
    return out


def apply_style_transform(strokes_yx: Sequence[np.ndarray], style_params: dict[str, float], image_size: int) -> list[np.ndarray]:
    cy = image_size / 2.0
    cx = image_size / 2.0
    h_scale = float(style_params.get("horizontal_scale", 1.0))
    v_scale = float(style_params.get("vertical_scale", 1.0))
    out: list[np.ndarray] = []
    for stroke in strokes_yx:
        pts = np.asarray(stroke, dtype=float).copy()
        pts[:, 0] = cy + (pts[:, 0] - cy) * v_scale
        pts[:, 1] = cx + (pts[:, 1] - cx) * h_scale
        out.append(pts)
    return out


def stroke_path_length(stroke: np.ndarray) -> float:
    if len(stroke) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(stroke.astype(float), axis=0), axis=1).sum())


def linear_resample(stroke: np.ndarray, step: float) -> np.ndarray:
    pts = np.asarray(stroke, dtype=float)
    if len(pts) <= 1:
        return pts.copy()
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    total = float(seg.sum())
    if total <= 1e-9:
        return pts.copy()
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    count = max(len(pts), int(math.ceil(total / max(step, 1.0))) + 1)
    sample = np.linspace(0.0, total, count)
    y = np.interp(sample, arc, pts[:, 0])
    x = np.interp(sample, arc, pts[:, 1])
    out = np.column_stack([y, x])
    out[0] = pts[0]
    out[-1] = pts[-1]
    return out


def smooth_polyline(stroke: np.ndarray, smoothness: float) -> np.ndarray:
    pts = np.asarray(stroke, dtype=float)
    if len(pts) < 3 or smoothness <= 0:
        return pts.copy()
    alpha = min(max(float(smoothness), 0.0), 0.8) * 0.5
    out = pts.copy()
    for _ in range(2):
        mid = out.copy()
        mid[1:-1] = (1.0 - alpha) * out[1:-1] + alpha * 0.5 * (out[:-2] + out[2:])
        mid[0] = pts[0]
        mid[-1] = pts[-1]
        out = mid
    return out


def insert_connections(
    strokes: Sequence[np.ndarray],
    connection_strength: float,
    allow_interstroke_connections: bool = False,
) -> list[np.ndarray]:
    if not allow_interstroke_connections or connection_strength <= 0:
        return [np.asarray(stroke, dtype=float) for stroke in strokes]
    strength = min(max(float(connection_strength), 0.0), 1.0)
    out: list[np.ndarray] = []
    for idx, stroke in enumerate(strokes):
        if idx > 0 and len(out[-1]) and len(stroke):
            start = stroke[0]
            prev_end = out[-1][-1]
            connector_end = prev_end * (1.0 - strength) + start * strength
            out.append(np.vstack([prev_end, connector_end, start]))
        out.append(np.asarray(stroke, dtype=float))
    return out


def build_styled_trajectory(raw_strokes_yx: Sequence[np.ndarray], style_params: dict[str, float], image_size: int) -> list[np.ndarray]:
    styled = apply_style_transform(raw_strokes_yx, style_params, image_size)
    step = float(style_params.get("resample_step", 5.0))
    smoothness = float(style_params.get("smoothness", 0.0)) + float(style_params.get("corner_rounding", 0.0)) * 0.25
    resampled = [smooth_polyline(linear_resample(stroke, step), smoothness) for stroke in styled]
    return insert_connections(
        resampled,
        float(style_params.get("connection_strength", 0.0)),
        bool(style_params.get("allow_interstroke_connections", False)),
    )


def _flatten_strokes(strokes_yx: Sequence[np.ndarray]) -> np.ndarray:
    parts = [np.asarray(stroke, dtype=float) for stroke in strokes_yx if len(stroke)]
    if not parts:
        return np.empty((0, 2), dtype=float)
    return np.vstack(parts)


def mean_turning(strokes_yx: Sequence[np.ndarray]) -> float:
    turns: list[float] = []
    for stroke in strokes_yx:
        pts = np.asarray(stroke, dtype=float)
        if len(pts) < 3:
            continue
        delta = np.diff(pts, axis=0)
        lengths = np.linalg.norm(delta, axis=1)
        keep = lengths > 1e-9
        delta = delta[keep]
        if len(delta) < 2:
            continue
        angles = np.arctan2(delta[:, 0], delta[:, 1])
        diff = np.diff(angles)
        diff = (diff + math.pi) % (2.0 * math.pi) - math.pi
        turns.extend(np.abs(diff).tolist())
    if not turns:
        return 0.0
    return float(np.mean(turns))


def trajectory_metrics(
    strokes_yx: Sequence[np.ndarray],
    image_size: int,
    stroke_count: int,
    connection_strength: float = 0.0,
    allow_interstroke_connections: bool = False,
) -> dict[str, float | int | bool]:
    points = _flatten_strokes(strokes_yx)
    point_count = int(len(points))
    path_length = float(sum(stroke_path_length(np.asarray(stroke, dtype=float)) for stroke in strokes_yx))
    connection_count = (
        max(0, int(stroke_count) - 1)
        if allow_interstroke_connections and connection_strength > 1e-9
        else 0
    )
    pen_up_count = max(0, int(stroke_count) - 1)

    if point_count:
        y0, x0 = np.min(points, axis=0)
        y1, x1 = np.max(points, axis=0)
        bbox_h = float(y1 - y0)
        bbox_w = float(x1 - x0)
        out_of_bounds = bool(
            np.any(points[:, 0] < 0.0)
            or np.any(points[:, 1] < 0.0)
            or np.any(points[:, 0] > image_size)
            or np.any(points[:, 1] > image_size)
        )
    else:
        bbox_w = 0.0
        bbox_h = 0.0
        out_of_bounds = False

    aspect_ratio = bbox_w / bbox_h if bbox_h > 1e-9 else 0.0
    return {
        "point_count": point_count,
        "path_length": round(path_length, 3),
        "pen_up_count": pen_up_count,
        "bounding_box_width": round(bbox_w, 3),
        "bounding_box_height": round(bbox_h, 3),
        "aspect_ratio": round(aspect_ratio, 6),
        "mean_turning": round(mean_turning(strokes_yx), 6),
        "connection_count": connection_count,
        "out_of_bounds": out_of_bounds,
    }


def write_trajectory_csv(strokes_yx: Sequence[np.ndarray], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["y", "x"])
        for stroke in strokes_yx:
            for y, x in np.asarray(stroke, dtype=float):
                writer.writerow([f"{y:.3f}", f"{x:.3f}"])
            writer.writerow(["nan", "nan"])


def write_preview(raw_strokes: Sequence[np.ndarray], styled_strokes: Sequence[np.ndarray], path: Path, title: str, image_size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = Figure(figsize=(5.0, 5.0), dpi=140)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0.08, 0.08, 0.86, 0.86])
    ax.set_title(title, fontsize=10)
    ax.set_aspect("equal")
    ax.set_xlim(0, image_size)
    ax.set_ylim(image_size, 0)
    ax.grid(True, color="#eeeeee", linewidth=0.5)
    colors = ["#d62728", "#1f77b4", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf"]
    for idx, stroke in enumerate(raw_strokes):
        pts = np.asarray(stroke, dtype=float)
        if len(pts):
            ax.plot(pts[:, 1], pts[:, 0], "--", color="#999999", linewidth=1.0, alpha=0.75)
    for idx, stroke in enumerate(styled_strokes):
        pts = np.asarray(stroke, dtype=float)
        if len(pts):
            color = colors[idx % len(colors)]
            ax.plot(pts[:, 1], pts[:, 0], "-", color=color, linewidth=2.0)
            ax.scatter([pts[0, 1]], [pts[0, 0]], color=color, marker="o", s=18)
            ax.scatter([pts[-1, 1]], [pts[-1, 0]], color=color, marker="x", s=22)
            ax.text(pts[0, 1], pts[0, 0], str(idx + 1), color=color, fontsize=8)
    canvas.print_png(str(path))


def write_style_compare(
    raw_strokes: Sequence[np.ndarray],
    style_strokes: dict[str, Sequence[np.ndarray]],
    path: Path,
    image_size: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = [style for style in ["kaishu", "xingkai", "lishu"] if style in style_strokes]
    if not styles:
        return

    fig = Figure(figsize=(4.2 * len(styles), 4.4), dpi=140)
    canvas = FigureCanvas(fig)
    colors = {
        "kaishu": "#1f77b4",
        "xingkai": "#d62728",
        "lishu": "#2ca02c",
    }
    for idx, style in enumerate(styles):
        left = 0.05 + idx * (0.9 / len(styles))
        ax = fig.add_axes([left, 0.10, 0.78 / len(styles), 0.78])
        ax.set_title(style, fontsize=10)
        ax.set_aspect("equal")
        ax.set_xlim(0, image_size)
        ax.set_ylim(image_size, 0)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(True, color="#eeeeee", linewidth=0.5)

        for raw in raw_strokes:
            pts = np.asarray(raw, dtype=float)
            if len(pts):
                ax.plot(pts[:, 1], pts[:, 0], "--", color="#aaaaaa", linewidth=1.0, alpha=0.75)

        for stroke in style_strokes[style]:
            pts = np.asarray(stroke, dtype=float)
            if len(pts):
                ax.plot(pts[:, 1], pts[:, 0], "-", color=colors.get(style, "#333333"), linewidth=2.0)
                ax.scatter([pts[0, 1]], [pts[0, 0]], color=colors.get(style, "#333333"), marker="o", s=12)
                ax.scatter([pts[-1, 1]], [pts[-1, 0]], color=colors.get(style, "#333333"), marker="x", s=16)
    canvas.print_png(str(path))
