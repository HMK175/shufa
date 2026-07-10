"""2D virtual writing execution layer for styled trajectories."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from execution_refinement import refine_execution_rows
from trajectory_tools import apply_style_transform, linear_resample, smooth_polyline, stroke_path_length


EXECUTION_FIELDS = [
    "segment_id",
    "stroke_id",
    "point_id",
    "y",
    "x",
    "z",
    "speed",
    "pressure",
    "width",
    "pen_down",
    "is_connector",
    "segment_type",
    "connection_preference",
]


def _base_strokes(raw_strokes_yx: Sequence[np.ndarray], style_params: dict[str, Any], image_size: int) -> list[np.ndarray]:
    styled = apply_style_transform(raw_strokes_yx, style_params, image_size)
    step = float(style_params.get("resample_step", 5.0))
    smoothness = float(style_params.get("smoothness", 0.0)) + float(style_params.get("corner_rounding", 0.0)) * 0.25
    return [smooth_polyline(linear_resample(stroke, step), smoothness) for stroke in styled]


def _connector_state(connection_preference: str, connection_strength: float, base_width: float, speed_scale: float) -> dict[str, float]:
    strength = min(max(float(connection_strength), 0.0), 1.0)
    if connection_preference == "normal":
        pressure = min(0.75, 0.55 + 0.40 * strength)
        width_factor = min(0.80, 0.55 + 0.55 * strength)
        speed_factor = max(1.0, 1.22 - 0.45 * strength)
    else:
        pressure = min(0.45, 0.25 + 0.50 * strength)
        width_factor = min(0.55, 0.35 + 0.55 * strength)
        speed_factor = max(1.1, 1.45 - 0.55 * strength)
    return {
        "pressure": pressure,
        "width": max(1.0, base_width * width_factor),
        "speed": speed_scale * speed_factor,
    }


def _append_segment(
    rows: list[dict[str, Any]],
    points: np.ndarray,
    *,
    segment_id: int,
    stroke_id: int,
    point_id_start: int,
    z: float,
    speed: float,
    pressure: float,
    width: float,
    pen_down: int,
    is_connector: int,
    segment_type: str,
    connection_preference: str,
) -> int:
    point_id = point_id_start
    for y, x in np.asarray(points, dtype=float):
        rows.append(
            {
                "segment_id": segment_id,
                "stroke_id": stroke_id,
                "point_id": point_id,
                "y": float(y),
                "x": float(x),
                "z": float(z),
                "speed": float(speed),
                "pressure": float(pressure),
                "width": float(width),
                "pen_down": int(pen_down),
                "is_connector": int(is_connector),
                "segment_type": segment_type,
                "connection_preference": connection_preference,
            }
        )
        point_id += 1
    return point_id


def build_execution_trajectory(
    raw_strokes_yx: Sequence[np.ndarray],
    style_params: dict[str, Any],
    brush_params: dict[str, Any],
    style_modifiers: dict[str, str] | None,
    image_size: int,
    *,
    style: str = "",
    connector_rule: dict[str, Any] | None = None,
    stroke_width_profile: dict[str, Any] | None = None,
    connector_shape: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    base = _base_strokes(raw_strokes_yx, style_params, image_size)
    rows: list[dict[str, Any]] = []
    segment_id = 0
    point_id = 0
    speed_scale = float(style_params.get("speed_scale", 1.0))
    pen_up_height = float(style_params.get("pen_up_height", 8.0))
    base_width = float(brush_params.get("base_width", 8.0))
    connection_preference = str((style_modifiers or {}).get("connection_preference", "weak"))
    allow_connections = bool(style_params.get("allow_interstroke_connections", False))
    connection_strength = float(style_params.get("connection_strength", 0.0))
    should_connect = allow_connections and connection_strength > 1e-9 and connection_preference != "none"

    for idx, stroke in enumerate(base):
        pts = np.asarray(stroke, dtype=float)
        if len(pts) == 0:
            continue
        stroke_id = idx + 1
        if idx > 0 and len(base[idx - 1]):
            prev_end = np.asarray(base[idx - 1][-1], dtype=float)
            start = pts[0]
            segment_id += 1
            if should_connect:
                state = _connector_state(connection_preference, connection_strength, base_width, speed_scale)
                point_id = _append_segment(
                    rows,
                    np.vstack([prev_end, start]),
                    segment_id=segment_id,
                    stroke_id=stroke_id,
                    point_id_start=point_id,
                    z=0.0,
                    speed=state["speed"],
                    pressure=state["pressure"],
                    width=state["width"],
                    pen_down=1,
                    is_connector=1,
                    segment_type="connector",
                    connection_preference=connection_preference,
                )
            else:
                point_id = _append_segment(
                    rows,
                    np.vstack([prev_end, start]),
                    segment_id=segment_id,
                    stroke_id=stroke_id,
                    point_id_start=point_id,
                    z=pen_up_height,
                    speed=speed_scale * 1.6,
                    pressure=0.0,
                    width=0.0,
                    pen_down=0,
                    is_connector=0,
                    segment_type="pen_up_move",
                    connection_preference=connection_preference,
                )

        segment_id += 1
        point_id = _append_segment(
            rows,
            pts,
            segment_id=segment_id,
            stroke_id=stroke_id,
            point_id_start=point_id,
            z=0.0,
            speed=speed_scale,
            pressure=1.0,
            width=base_width,
            pen_down=1,
            is_connector=0,
            segment_type="stroke",
            connection_preference=connection_preference,
        )
    if connector_rule is not None or stroke_width_profile is not None or connector_shape is not None:
        rows = refine_execution_rows(
            rows,
            style=style,
            style_modifiers=style_modifiers,
            connector_rule=connector_rule,
            stroke_width_profile=stroke_width_profile,
            connector_shape=connector_shape,
            pen_up_height=pen_up_height,
        )
    return rows


def write_execution_csv(rows: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXECUTION_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: (
                        f"{float(row[field]):.3f}"
                        if field in {"y", "x", "z", "speed", "pressure", "width"}
                        else row[field]
                    )
                    for field in EXECUTION_FIELDS
                }
            )


def _segment_groups(rows: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current_id: Any = None
    for row in rows:
        segment_id = row.get("segment_id")
        if segment_id != current_id:
            groups.append([])
            current_id = segment_id
        groups[-1].append(row)
    return groups


def _points_from_group(group: Sequence[dict[str, Any]]) -> np.ndarray:
    return np.asarray([[float(row["y"]), float(row["x"])] for row in group], dtype=float)


def execution_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    lengths = {
        "stroke": 0.0,
        "connector": 0.0,
        "pen_up_move": 0.0,
    }
    draw_weight = 0.0
    pressure_weight = 0.0
    width_weight = 0.0
    connector_weight = 0.0
    connector_pressure_weight = 0.0
    connector_width_weight = 0.0

    for group in _segment_groups(rows):
        if not group:
            continue
        segment_type = str(group[0]["segment_type"])
        points = _points_from_group(group)
        length = stroke_path_length(points)
        lengths[segment_type] = lengths.get(segment_type, 0.0) + length
        pressure = float(group[0]["pressure"])
        width = float(group[0]["width"])
        pen_down = int(group[0]["pen_down"])
        if pen_down:
            draw_weight += length
            pressure_weight += pressure * length
            width_weight += width * length
        if segment_type == "connector":
            connector_weight += length
            connector_pressure_weight += pressure * length
            connector_width_weight += width * length

    return {
        "stroke_draw_length": round(lengths.get("stroke", 0.0), 3),
        "connector_draw_length": round(lengths.get("connector", 0.0), 3),
        "pen_up_move_length": round(lengths.get("pen_up_move", 0.0), 3),
        "mean_pressure": round(pressure_weight / draw_weight, 6) if draw_weight > 1e-9 else 0.0,
        "mean_width": round(width_weight / draw_weight, 6) if draw_weight > 1e-9 else 0.0,
        "connector_mean_pressure": round(connector_pressure_weight / connector_weight, 6) if connector_weight > 1e-9 else 0.0,
        "connector_mean_width": round(connector_width_weight / connector_weight, 6) if connector_weight > 1e-9 else 0.0,
    }


def render_execution(rows: Sequence[dict[str, Any]], path: Path, image_size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = Figure(figsize=(4.2, 4.2), dpi=140)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0.03, 0.03, 0.94, 0.94])
    ax.set_aspect("equal")
    ax.set_xlim(0, image_size)
    ax.set_ylim(image_size, 0)
    ax.axis("off")
    for group in _segment_groups(rows):
        if not group or int(group[0]["pen_down"]) == 0:
            continue
        pts = _points_from_group(group)
        if len(pts) == 0:
            continue
        pressure = float(group[0]["pressure"])
        width = max(0.5, float(group[0]["width"]) * 0.55)
        alpha = max(0.18, min(1.0, pressure))
        ax.plot(pts[:, 1], pts[:, 0], color="#111111", linewidth=width, alpha=alpha, solid_capstyle="round")
    canvas.print_png(str(path))


def render_execution_debug(rows: Sequence[dict[str, Any]], path: Path, image_size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = Figure(figsize=(4.6, 4.6), dpi=140)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0.06, 0.06, 0.88, 0.88])
    ax.set_aspect("equal")
    ax.set_xlim(0, image_size)
    ax.set_ylim(image_size, 0)
    ax.grid(True, color="#eeeeee", linewidth=0.5)
    ax.set_title("Execution debug", fontsize=10, pad=8)
    legend_seen: set[str] = set()
    for group in _segment_groups(rows):
        if not group:
            continue
        pts = _points_from_group(group)
        segment_type = str(group[0]["segment_type"])
        pref = str(group[0].get("connection_preference", ""))
        if segment_type == "stroke":
            color, alpha, linewidth, linestyle = "#1f77b4", 0.95, 2.0, "-"
            label = "stroke"
        elif segment_type == "connector":
            color = "#d62728" if pref == "normal" else "#ff7f0e"
            alpha = 0.9 if pref == "normal" else 0.55
            linewidth = 2.0 if pref == "normal" else 1.25
            linestyle = "-"
            label = f"{pref or 'weak'} connector"
        else:
            color, alpha, linewidth, linestyle = "#777777", 0.55, 1.0, "--"
            label = "pen-up move"
        if len(pts):
            draw_label = label if label not in legend_seen else None
            ax.plot(
                pts[:, 1],
                pts[:, 0],
                color=color,
                linewidth=linewidth,
                alpha=alpha,
                linestyle=linestyle,
                label=draw_label,
            )
            legend_seen.add(label)
    if legend_seen:
        ax.legend(loc="lower right", fontsize=7, frameon=True, framealpha=0.88)
    canvas.print_png(str(path))


def write_execution_compare(items: Sequence[tuple[str, Path]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not items:
        return
    images = [Image.open(image_path).convert("RGB") for _, image_path in items]
    cell_w = max(image.width for image in images)
    cell_h = max(image.height for image in images)
    label_h = 70
    out = Image.new("RGB", (cell_w * len(items), cell_h + label_h), "white")
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 42)
    except OSError:
        font = ImageFont.load_default()
    for idx, ((label, _), image) in enumerate(zip(items, images)):
        x = idx * cell_w + (cell_w - image.width) // 2
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text((idx * cell_w + (cell_w - text_w) // 2, 12), label, fill="#222222", font=font)
        out.paste(image, (x, label_h))
    out.save(path)
