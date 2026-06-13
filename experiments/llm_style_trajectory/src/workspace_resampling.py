"""Resample robot workspace trajectories and assign segment-level speeds."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from PIL import Image, ImageDraw, ImageFont


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_BATCH = EXP_DIR / "outputs" / "batch_20260613_092733"


RESAMPLED_FIELDS = [
    "segment_id",
    "stroke_id",
    "point_id",
    "X_mm",
    "Y_mm",
    "Z_mm",
    "speed_mm_s",
    "pressure",
    "width",
    "pen_down",
    "is_connector",
    "segment_type",
    "y",
    "x",
]


SUMMARY_FIELDS = [
    "task",
    "char",
    "char_id",
    "task_dir",
    "original_point_count",
    "resampled_point_count",
    "original_max_step_mm",
    "resampled_max_step_mm",
    "original_path_length_mm",
    "resampled_path_length_mm",
    "stroke_max_step_mm",
    "connector_max_step_mm",
    "pen_up_move_max_step_mm",
    "max_speed_mm_s",
    "min_speed_mm_s",
    "estimated_duration_s",
    "segment_counts",
    "out_of_bounds",
    "z_range",
    "robot_workspace_resampled_csv",
    "workspace_resampled_preview_png",
    "workspace_resampling_report_md",
]


@dataclass(frozen=True)
class ResamplingConfig:
    stroke_max_step_mm: float = 2.0
    connector_max_step_mm: float = 2.5
    pen_up_move_max_step_mm: float = 5.0
    stroke_speed_mm_s: float = 25.0
    connector_weak_speed_mm_s: float = 40.0
    connector_normal_speed_mm_s: float = 32.0
    pen_up_move_speed_mm_s: float = 70.0
    paper_width_mm: float = 120.0
    paper_height_mm: float = 120.0
    z_min_mm: float = 0.0
    z_max_mm: float = 20.0


def _float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_csv(rows: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESAMPLED_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in RESAMPLED_FIELDS})


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


def _point(row: dict[str, Any]) -> np.ndarray:
    return np.asarray([_float(row["X_mm"]), _float(row["Y_mm"]), _float(row["Z_mm"])], dtype=float)


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    return float(np.linalg.norm(_point(b) - _point(a)))


def _segment_type_max_step(segment_type: str, config: ResamplingConfig) -> float:
    if segment_type == "connector":
        return config.connector_max_step_mm
    if segment_type == "pen_up_move":
        return config.pen_up_move_max_step_mm
    return config.stroke_max_step_mm


def _planned_speed(segment_type: str, pressure: float, config: ResamplingConfig) -> float:
    if segment_type == "connector":
        return config.connector_normal_speed_mm_s if pressure >= 0.5 else config.connector_weak_speed_mm_s
    if segment_type == "pen_up_move":
        return config.pen_up_move_speed_mm_s
    return config.stroke_speed_mm_s


def _interpolate_row(
    start: dict[str, Any],
    end: dict[str, Any],
    t: float,
    *,
    point_id: int,
    config: ResamplingConfig,
) -> dict[str, Any]:
    segment_type = str(start.get("segment_type", "stroke"))
    pressure = _float(start.get("pressure")) * (1.0 - t) + _float(end.get("pressure")) * t
    width = _float(start.get("width")) * (1.0 - t) + _float(end.get("width")) * t
    x_mm = _float(start.get("X_mm")) * (1.0 - t) + _float(end.get("X_mm")) * t
    y_mm = _float(start.get("Y_mm")) * (1.0 - t) + _float(end.get("Y_mm")) * t
    z_mm = _float(start.get("Z_mm")) * (1.0 - t) + _float(end.get("Z_mm")) * t
    return {
        "segment_id": _int(start.get("segment_id")),
        "stroke_id": _int(start.get("stroke_id")),
        "point_id": point_id,
        "X_mm": round(x_mm, 6),
        "Y_mm": round(y_mm, 6),
        "Z_mm": round(z_mm, 6),
        "speed_mm_s": round(_planned_speed(segment_type, pressure, config), 6),
        "pressure": round(pressure, 6),
        "width": round(width, 6),
        "pen_down": _int(start.get("pen_down")),
        "is_connector": _int(start.get("is_connector")),
        "segment_type": segment_type,
        "y": round(_float(start.get("y")) * (1.0 - t) + _float(end.get("y")) * t, 6),
        "x": round(_float(start.get("x")) * (1.0 - t) + _float(end.get("x")) * t, 6),
    }


def resample_workspace_rows(rows: Sequence[dict[str, Any]], config: ResamplingConfig) -> list[dict[str, Any]]:
    resampled: list[dict[str, Any]] = []
    point_id = 0
    for group in _segment_groups(rows):
        if not group:
            continue
        if len(group) == 1:
            resampled.append(_interpolate_row(group[0], group[0], 0.0, point_id=point_id, config=config))
            point_id += 1
            continue
        first = _interpolate_row(group[0], group[0], 0.0, point_id=point_id, config=config)
        resampled.append(first)
        point_id += 1
        max_step = _segment_type_max_step(str(group[0].get("segment_type", "stroke")), config)
        for start, end in zip(group, group[1:]):
            distance = _distance(start, end)
            intervals = max(1, int(math.ceil(distance / max_step))) if max_step > 0 else 1
            for idx in range(1, intervals + 1):
                t = idx / intervals
                resampled.append(_interpolate_row(start, end, t, point_id=point_id, config=config))
                point_id += 1
    return resampled


def _path_length(rows: Sequence[dict[str, Any]]) -> float:
    length = 0.0
    for group in _segment_groups(rows):
        for start, end in zip(group, group[1:]):
            length += _distance(start, end)
    return length


def _max_step(rows: Sequence[dict[str, Any]]) -> float:
    max_step = 0.0
    for group in _segment_groups(rows):
        for start, end in zip(group, group[1:]):
            max_step = max(max_step, _distance(start, end))
    return max_step


def _segment_counts(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for group in _segment_groups(rows):
        if not group:
            continue
        segment_type = str(group[0].get("segment_type", ""))
        counts[segment_type] = counts.get(segment_type, 0) + 1
    return counts


def _segment_max_steps(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    max_steps = {"stroke": 0.0, "connector": 0.0, "pen_up_move": 0.0}
    for group in _segment_groups(rows):
        if not group:
            continue
        segment_type = str(group[0].get("segment_type", "stroke"))
        local_max = 0.0
        for start, end in zip(group, group[1:]):
            local_max = max(local_max, _distance(start, end))
        max_steps[segment_type] = max(max_steps.get(segment_type, 0.0), local_max)
    return {key: round(value, 3) for key, value in max_steps.items()}


def _estimated_duration(rows: Sequence[dict[str, Any]]) -> float:
    duration = 0.0
    for group in _segment_groups(rows):
        for start, end in zip(group, group[1:]):
            speed = max(1e-9, _float(end.get("speed_mm_s")) or _float(start.get("speed_mm_s")))
            duration += _distance(start, end) / speed
    return duration


def _out_of_bounds(rows: Sequence[dict[str, Any]], config: ResamplingConfig) -> bool:
    if not rows:
        return False
    half_w = config.paper_width_mm / 2.0
    half_h = config.paper_height_mm / 2.0
    for row in rows:
        x = _float(row.get("X_mm"))
        y = _float(row.get("Y_mm"))
        z = _float(row.get("Z_mm"))
        if x < -half_w - 1e-6 or x > half_w + 1e-6:
            return True
        if y < -half_h - 1e-6 or y > half_h + 1e-6:
            return True
        if z < config.z_min_mm - 1e-6 or z > config.z_max_mm + 1e-6:
            return True
    return False


def _z_range(rows: Sequence[dict[str, Any]]) -> str:
    if not rows:
        return "0.000..0.000"
    zs = [_float(row.get("Z_mm")) for row in rows]
    return f"{min(zs):.3f}..{max(zs):.3f}"


def resampling_metrics(
    original_rows: Sequence[dict[str, Any]],
    resampled_rows: Sequence[dict[str, Any]],
    config: ResamplingConfig,
) -> dict[str, Any]:
    speeds = [_float(row.get("speed_mm_s")) for row in resampled_rows if _float(row.get("speed_mm_s")) > 0]
    segment_steps = _segment_max_steps(resampled_rows)
    return {
        "original_point_count": len(original_rows),
        "resampled_point_count": len(resampled_rows),
        "original_max_step_mm": round(_max_step(original_rows), 3),
        "resampled_max_step_mm": round(_max_step(resampled_rows), 3),
        "original_path_length_mm": round(_path_length(original_rows), 3),
        "resampled_path_length_mm": round(_path_length(resampled_rows), 3),
        "stroke_max_step_mm": segment_steps.get("stroke", 0.0),
        "connector_max_step_mm": segment_steps.get("connector", 0.0),
        "pen_up_move_max_step_mm": segment_steps.get("pen_up_move", 0.0),
        "segment_max_steps": segment_steps,
        "max_speed_mm_s": round(max(speeds), 3) if speeds else 0.0,
        "min_speed_mm_s": round(min(speeds), 3) if speeds else 0.0,
        "estimated_duration_s": round(_estimated_duration(resampled_rows), 6),
        "segment_counts": _segment_counts(resampled_rows),
        "out_of_bounds": _out_of_bounds(resampled_rows, config),
        "z_range": _z_range(resampled_rows),
    }


def _metadata_for_task(task_dir: Path) -> dict[str, str]:
    summary_path = task_dir / "summary.json"
    if summary_path.exists():
        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            char = str(data.get("char", ""))
            return {
                "task": str(data.get("task", "")),
                "char": char,
                "char_id": f"u{ord(char[0]):04x}" if char else "",
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    name = task_dir.name
    char_id = name.split("_", 1)[0] if name.startswith("u") else ""
    return {"task": "", "char": "", "char_id": char_id}


def render_resampled_preview(rows: Sequence[dict[str, Any]], path: Path, config: ResamplingConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = Figure(figsize=(4.8, 4.8), dpi=140)
    canvas = FigureCanvas(fig)
    ax = fig.add_axes([0.10, 0.10, 0.84, 0.84])
    ax.set_aspect("equal")
    half_w = config.paper_width_mm / 2.0
    half_h = config.paper_height_mm / 2.0
    margin = 8
    ax.set_xlim(-half_w - margin, half_w + margin)
    ax.set_ylim(-half_h - margin, half_h + margin)
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.grid(True, color="#eeeeee", linewidth=0.5)
    ax.plot(
        [-half_w, half_w, half_w, -half_w, -half_w],
        [-half_h, -half_h, half_h, half_h, -half_h],
        color="#444444",
        linewidth=1.0,
    )
    seen: set[str] = set()
    for group in _segment_groups(rows):
        if not group:
            continue
        points = np.asarray([[_float(row["X_mm"]), _float(row["Y_mm"])] for row in group], dtype=float)
        segment_type = str(group[0].get("segment_type", ""))
        if segment_type == "stroke":
            color, linestyle, linewidth, label = "#1f77b4", "-", 2.0, "stroke"
        elif segment_type == "connector":
            color, linestyle, linewidth, label = "#d62728", "-", 1.5, "connector"
        else:
            color, linestyle, linewidth, label = "#777777", "--", 1.0, "pen-up move"
        ax.plot(
            points[:, 0],
            points[:, 1],
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            alpha=0.9,
            label=label if label not in seen else None,
        )
        ax.scatter(points[:, 0], points[:, 1], s=3, color=color, alpha=0.45)
        seen.add(label)
    if seen:
        ax.legend(loc="lower right", fontsize=7, frameon=True)
    canvas.print_png(str(path))


def _report_text(task_dir: Path, metrics: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Workspace Resampling: {task_dir.name}",
            "",
            f"- original_point_count: `{metrics['original_point_count']}`",
            f"- resampled_point_count: `{metrics['resampled_point_count']}`",
            f"- original_max_step_mm: `{metrics['original_max_step_mm']}`",
            f"- resampled_max_step_mm: `{metrics['resampled_max_step_mm']}`",
            f"- stroke_max_step_mm: `{metrics['stroke_max_step_mm']}`",
            f"- connector_max_step_mm: `{metrics['connector_max_step_mm']}`",
            f"- pen_up_move_max_step_mm: `{metrics['pen_up_move_max_step_mm']}`",
            f"- estimated_duration_s: `{metrics['estimated_duration_s']}`",
            f"- speed_range_mm_s: `{metrics['min_speed_mm_s']}..{metrics['max_speed_mm_s']}`",
            f"- out_of_bounds: `{metrics['out_of_bounds']}`",
            f"- z_range: `{metrics['z_range']}`",
            f"- segment_counts: `{json.dumps(metrics['segment_counts'], ensure_ascii=False, sort_keys=True)}`",
            "",
        ]
    )


def process_task_dir(task_dir: Path, config: ResamplingConfig) -> dict[str, Any]:
    source_csv = task_dir / "robot_workspace_trajectory.csv"
    if not source_csv.exists():
        raise FileNotFoundError(f"missing robot_workspace_trajectory.csv: {task_dir}")
    original_rows = _read_csv(source_csv)
    resampled_rows = resample_workspace_rows(original_rows, config)
    out_csv = task_dir / "robot_workspace_trajectory_resampled.csv"
    report_md = task_dir / "workspace_resampling_report.md"
    preview_png = task_dir / "workspace_resampled_preview.png"
    _write_csv(resampled_rows, out_csv)
    render_resampled_preview(resampled_rows, preview_png, config)
    metrics = resampling_metrics(original_rows, resampled_rows, config)
    report_md.write_text(_report_text(task_dir, metrics), encoding="utf-8")
    return {
        **_metadata_for_task(task_dir),
        "task_dir": str(task_dir),
        **metrics,
        "robot_workspace_resampled_csv": str(out_csv),
        "workspace_resampled_preview_png": str(preview_png),
        "workspace_resampling_report_md": str(report_md),
    }


def _task_dirs(input_dir: Path) -> list[Path]:
    if (input_dir / "robot_workspace_trajectory.csv").exists():
        return [input_dir]
    return sorted(path for path in input_dir.iterdir() if path.is_dir() and (path / "robot_workspace_trajectory.csv").exists())


def _write_summary(rows: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: (
                        json.dumps(row.get(field, ""), ensure_ascii=False, sort_keys=True)
                        if field in {"segment_counts"}
                        else row.get(field, "")
                    )
                    for field in SUMMARY_FIELDS
                }
            )


def _write_batch_report(rows: Sequence[dict[str, Any]], path: Path) -> None:
    lines = [
        "# Workspace Resampling Report",
        "",
        f"- tasks: `{len(rows)}`",
        f"- out_of_bounds_count: `{sum(1 for row in rows if row.get('out_of_bounds'))}`",
        "",
        "| task | segment_counts | original_max_step_mm | resampled_max_step_mm | stroke_max_step_mm | connector_max_step_mm | pen_up_move_max_step_mm | estimated_duration_s |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {task} | `{counts}` | {orig} | {resampled} | {stroke} | {connector} | {pen_up} | {duration} |".format(
                task=row.get("task") or Path(str(row.get("task_dir", ""))).name,
                counts=json.dumps(row.get("segment_counts", {}), ensure_ascii=False, sort_keys=True),
                orig=row.get("original_max_step_mm", ""),
                resampled=row.get("resampled_max_step_mm", ""),
                stroke=row.get("stroke_max_step_mm", ""),
                connector=row.get("connector_max_step_mm", ""),
                pen_up=row.get("pen_up_move_max_step_mm", ""),
                duration=row.get("estimated_duration_s", ""),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _font(size: int) -> ImageFont.ImageFont:
    for font_path in [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/Deng.ttf"),
    ]:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _write_preview_compare(items: Sequence[tuple[str, Path, dict[str, Any]]], path: Path) -> None:
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    images = [Image.open(image_path).convert("RGB") for _, image_path, _ in items]
    cell_w = max(image.width for image in images)
    cell_h = max(image.height for image in images)
    label_h = 72
    out = Image.new("RGB", (cell_w * len(items), cell_h + label_h), "white")
    draw = ImageDraw.Draw(out)
    font = _font(24)
    small = _font(16)
    for idx, ((label, _, metrics), image) in enumerate(zip(items, images)):
        x = idx * cell_w + (cell_w - image.width) // 2
        x0 = idx * cell_w
        bbox = draw.textbbox((0, 0), label, font=font)
        draw.text((x0 + (cell_w - (bbox[2] - bbox[0])) // 2, 6), label, fill="#222222", font=font)
        info = f"pts {metrics.get('resampled_point_count')} / max {metrics.get('resampled_max_step_mm')}"
        ibox = draw.textbbox((0, 0), info, font=small)
        draw.text((x0 + (cell_w - (ibox[2] - ibox[0])) // 2, 38), info, fill="#555555", font=small)
        out.paste(image, (x, label_h))
    out.save(path)


def process_batch(input_dir: Path | str, config: ResamplingConfig) -> dict[str, Any]:
    batch_dir = Path(input_dir)
    dirs = _task_dirs(batch_dir)
    rows = [process_task_dir(task_dir, config) for task_dir in dirs]
    summary_csv = batch_dir / "workspace_resampling_summary.csv"
    report_md = batch_dir / "workspace_resampling_report.md"
    _write_summary(rows, summary_csv)
    _write_batch_report(rows, report_md)

    by_char_id: dict[str, list[tuple[str, Path, dict[str, Any]]]] = {}
    for row in rows:
        char_id = str(row.get("char_id") or "")
        if not char_id:
            continue
        label = ""
        summary_path = Path(str(row["task_dir"])) / "summary.json"
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                modifiers = summary.get("style_modifiers", {}) if isinstance(summary.get("style_modifiers"), dict) else {}
                label = str(modifiers.get("connection_preference") or summary.get("style") or "")
            except json.JSONDecodeError:
                label = ""
        if not label:
            label = Path(str(row["task_dir"])).name
        by_char_id.setdefault(char_id, []).append((label, Path(str(row["workspace_resampled_preview_png"])), row))

    ablation_images: dict[str, str] = {}
    for char_id, items in by_char_id.items():
        if not items:
            continue
        out_path = batch_dir / f"workspace_resampling_ablation_{char_id}.png"
        _write_preview_compare(items, out_path)
        ablation_images[char_id] = str(out_path)

    return {
        "batch_dir": str(batch_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "ablation_images": ablation_images,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resample robot workspace trajectories and assign speeds")
    parser.add_argument("--input", default=str(DEFAULT_BATCH), help="Task dir or batch dir containing robot_workspace_trajectory.csv files")
    parser.add_argument("--stroke-max-step-mm", type=float, default=2.0)
    parser.add_argument("--connector-max-step-mm", type=float, default=2.5)
    parser.add_argument("--pen-up-move-max-step-mm", type=float, default=5.0)
    args = parser.parse_args()
    config = ResamplingConfig(
        stroke_max_step_mm=args.stroke_max_step_mm,
        connector_max_step_mm=args.connector_max_step_mm,
        pen_up_move_max_step_mm=args.pen_up_move_max_step_mm,
    )
    result = process_batch(Path(args.input), config)
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
