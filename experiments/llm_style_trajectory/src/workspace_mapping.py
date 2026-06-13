"""Map 2D execution trajectories into a robot paper workspace."""

from __future__ import annotations

import argparse
import csv
import json
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


WORKSPACE_FIELDS = [
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
    "segment_counts",
    "workspace_path_length_mm",
    "stroke_draw_length_mm",
    "connector_draw_length_mm",
    "pen_up_move_length_mm",
    "max_step_mm",
    "large_jump",
    "out_of_bounds",
    "z_range",
    "pen_up_state_ok",
    "stroke_z_ok",
    "pen_up_z_ok",
    "robot_workspace_csv",
    "workspace_preview_png",
    "workspace_report_md",
]


@dataclass(frozen=True)
class WorkspaceConfig:
    image_size: int = 256
    paper_width_mm: float = 120.0
    paper_height_mm: float = 120.0
    pen_up_height_mm: float = 8.0
    connector_z_lift_mm: float = 0.0
    base_speed_mm_s: float = 30.0
    max_jump_threshold_mm: float = 15.0
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


def image_to_workspace(y: float, x: float, config: WorkspaceConfig) -> tuple[float, float]:
    x_mm = (x / config.image_size - 0.5) * config.paper_width_mm
    y_mm = (0.5 - y / config.image_size) * config.paper_height_mm
    return x_mm, y_mm


def _mapped_z(row: dict[str, Any], config: WorkspaceConfig) -> float:
    segment_type = str(row.get("segment_type", ""))
    pen_down = _int(row.get("pen_down"))
    if pen_down == 0 or segment_type == "pen_up_move":
        return float(config.pen_up_height_mm)
    if segment_type == "connector":
        return float(config.connector_z_lift_mm)
    return 0.0


def map_execution_rows(rows: Sequence[dict[str, Any]], config: WorkspaceConfig) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    for row in rows:
        y = _float(row.get("y"))
        x = _float(row.get("x"))
        x_mm, y_mm = image_to_workspace(y, x, config)
        speed = _float(row.get("speed")) or 1.0
        mapped.append(
            {
                "segment_id": _int(row.get("segment_id")),
                "stroke_id": _int(row.get("stroke_id")),
                "point_id": _int(row.get("point_id")),
                "X_mm": round(x_mm, 6),
                "Y_mm": round(y_mm, 6),
                "Z_mm": round(_mapped_z(row, config), 6),
                "speed_mm_s": round(config.base_speed_mm_s * speed, 6),
                "pressure": round(_float(row.get("pressure")), 6),
                "width": round(_float(row.get("width")), 6),
                "pen_down": _int(row.get("pen_down")),
                "is_connector": _int(row.get("is_connector")),
                "segment_type": str(row.get("segment_type", "")),
                "y": round(y, 6),
                "x": round(x, 6),
            }
        )
    return mapped


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_workspace_csv(rows: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=WORKSPACE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in WORKSPACE_FIELDS})


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


def _points_xyz(group: Sequence[dict[str, Any]]) -> np.ndarray:
    return np.asarray(
        [[_float(row["X_mm"]), _float(row["Y_mm"]), _float(row["Z_mm"])] for row in group],
        dtype=float,
    )


def _path_length(points: np.ndarray) -> float:
    if len(points) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())


def validate_workspace_rows(rows: Sequence[dict[str, Any]], config: WorkspaceConfig) -> dict[str, Any]:
    if not rows:
        return {
            "segment_counts": {},
            "workspace_path_length_mm": 0.0,
            "stroke_draw_length_mm": 0.0,
            "connector_draw_length_mm": 0.0,
            "pen_up_move_length_mm": 0.0,
            "max_step_mm": 0.0,
            "large_jump": False,
            "out_of_bounds": False,
            "z_range": "0.000..0.000",
            "pen_up_state_ok": True,
            "stroke_z_ok": True,
            "pen_up_z_ok": True,
        }

    half_w = config.paper_width_mm / 2.0
    half_h = config.paper_height_mm / 2.0
    xs = np.asarray([_float(row["X_mm"]) for row in rows], dtype=float)
    ys = np.asarray([_float(row["Y_mm"]) for row in rows], dtype=float)
    zs = np.asarray([_float(row["Z_mm"]) for row in rows], dtype=float)
    out_of_bounds = bool(
        (xs < -half_w - 1e-6).any()
        or (xs > half_w + 1e-6).any()
        or (ys < -half_h - 1e-6).any()
        or (ys > half_h + 1e-6).any()
        or (zs < config.z_min_mm - 1e-6).any()
        or (zs > config.z_max_mm + 1e-6).any()
    )

    segment_counts: dict[str, int] = {}
    lengths = {"stroke": 0.0, "connector": 0.0, "pen_up_move": 0.0}
    max_step = 0.0
    for group in _segment_groups(rows):
        if not group:
            continue
        segment_type = str(group[0].get("segment_type", ""))
        segment_counts[segment_type] = segment_counts.get(segment_type, 0) + 1
        points = _points_xyz(group)
        if len(points) >= 2:
            steps = np.linalg.norm(np.diff(points, axis=0), axis=1)
            max_step = max(max_step, float(steps.max(initial=0.0)))
        lengths[segment_type] = lengths.get(segment_type, 0.0) + _path_length(points)

    pen_up_rows = [row for row in rows if _int(row.get("pen_down")) == 0 or row.get("segment_type") == "pen_up_move"]
    stroke_rows = [row for row in rows if row.get("segment_type") == "stroke"]
    pen_up_state_ok = all(abs(_float(row.get("pressure"))) < 1e-9 and abs(_float(row.get("width"))) < 1e-9 for row in pen_up_rows)
    stroke_z_ok = all(abs(_float(row.get("Z_mm"))) < 1e-9 for row in stroke_rows)
    pen_up_z_ok = all(abs(_float(row.get("Z_mm")) - config.pen_up_height_mm) < 1e-6 for row in pen_up_rows)

    return {
        "segment_counts": segment_counts,
        "workspace_path_length_mm": round(sum(lengths.values()), 3),
        "stroke_draw_length_mm": round(lengths.get("stroke", 0.0), 3),
        "connector_draw_length_mm": round(lengths.get("connector", 0.0), 3),
        "pen_up_move_length_mm": round(lengths.get("pen_up_move", 0.0), 3),
        "max_step_mm": round(max_step, 3),
        "large_jump": bool(max_step > config.max_jump_threshold_mm),
        "out_of_bounds": out_of_bounds,
        "z_range": f"{float(zs.min()):.3f}..{float(zs.max()):.3f}",
        "pen_up_state_ok": bool(pen_up_state_ok),
        "stroke_z_ok": bool(stroke_z_ok),
        "pen_up_z_ok": bool(pen_up_z_ok),
    }


def _metadata_for_task(task_dir: Path) -> dict[str, str]:
    summary_path = task_dir / "summary.json"
    if summary_path.exists():
        try:
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            return {
                "task": str(data.get("task", "")),
                "char": str(data.get("char", "")),
                "char_id": f"u{ord(str(data.get('char', ''))[0]):04x}" if data.get("char") else "",
            }
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    name = task_dir.name
    char_id = name.split("_", 1)[0] if name.startswith("u") else ""
    return {"task": "", "char": "", "char_id": char_id}


def _report_lines(task_dir: Path, metrics: dict[str, Any], config: WorkspaceConfig) -> list[str]:
    return [
        f"# Workspace Validation: {task_dir.name}",
        "",
        "## Config",
        "",
        f"- image_size: `{config.image_size}`",
        f"- paper_width_mm: `{config.paper_width_mm}`",
        f"- paper_height_mm: `{config.paper_height_mm}`",
        f"- pen_up_height_mm: `{config.pen_up_height_mm}`",
        f"- base_speed_mm_s: `{config.base_speed_mm_s}`",
        "",
        "## Checks",
        "",
        f"- out_of_bounds: `{metrics['out_of_bounds']}`",
        f"- z_range: `{metrics['z_range']}`",
        f"- max_step_mm: `{metrics['max_step_mm']}`",
        f"- large_jump: `{metrics['large_jump']}`",
        f"- pen_up_state_ok: `{metrics['pen_up_state_ok']}`",
        f"- stroke_z_ok: `{metrics['stroke_z_ok']}`",
        f"- pen_up_z_ok: `{metrics['pen_up_z_ok']}`",
        f"- segment_counts: `{json.dumps(metrics['segment_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- workspace_path_length_mm: `{metrics['workspace_path_length_mm']}`",
        f"- pen_up_move_length_mm: `{metrics['pen_up_move_length_mm']}`",
        "",
    ]


def write_workspace_report(task_dir: Path, metrics: dict[str, Any], path: Path, config: WorkspaceConfig) -> None:
    path.write_text("\n".join(_report_lines(task_dir, metrics, config)), encoding="utf-8")


def render_workspace_preview(rows: Sequence[dict[str, Any]], path: Path, config: WorkspaceConfig) -> None:
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
        seen.add(label)
    if seen:
        ax.legend(loc="lower right", fontsize=7, frameon=True)
    canvas.print_png(str(path))


def process_task_dir(task_dir: Path, config: WorkspaceConfig) -> dict[str, Any]:
    execution_csv = task_dir / "execution_trajectory.csv"
    if not execution_csv.exists():
        raise FileNotFoundError(f"missing execution_trajectory.csv: {task_dir}")
    execution_rows = _read_csv(execution_csv)
    workspace_rows = map_execution_rows(execution_rows, config)
    workspace_csv = task_dir / "robot_workspace_trajectory.csv"
    report_md = task_dir / "workspace_validation_report.md"
    preview_png = task_dir / "workspace_path_preview.png"
    _write_workspace_csv(workspace_rows, workspace_csv)
    metrics = validate_workspace_rows(workspace_rows, config)
    write_workspace_report(task_dir, metrics, report_md, config)
    render_workspace_preview(workspace_rows, preview_png, config)
    metadata = _metadata_for_task(task_dir)
    return {
        **metadata,
        "task_dir": str(task_dir),
        **metrics,
        "robot_workspace_csv": str(workspace_csv),
        "workspace_preview_png": str(preview_png),
        "workspace_report_md": str(report_md),
    }


def _task_dirs(input_dir: Path) -> list[Path]:
    if (input_dir / "execution_trajectory.csv").exists():
        return [input_dir]
    return sorted(path for path in input_dir.iterdir() if path.is_dir() and (path / "execution_trajectory.csv").exists())


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
                        if field == "segment_counts"
                        else row.get(field, "")
                    )
                    for field in SUMMARY_FIELDS
                }
            )


def _write_batch_report(rows: Sequence[dict[str, Any]], path: Path, config: WorkspaceConfig) -> None:
    total = len(rows)
    out_count = sum(1 for row in rows if row.get("out_of_bounds"))
    jump_count = sum(1 for row in rows if row.get("large_jump"))
    lines = [
        "# Workspace Mapping Report",
        "",
        f"- tasks: `{total}`",
        f"- out_of_bounds_count: `{out_count}`",
        f"- large_jump_count: `{jump_count}`",
        f"- paper_size_mm: `{config.paper_width_mm} x {config.paper_height_mm}`",
        f"- pen_up_height_mm: `{config.pen_up_height_mm}`",
        "",
        "| task | char | segment_counts | workspace_path_length_mm | max_step_mm | out_of_bounds | z_range | pen_up_move_length_mm |",
        "|---|---|---|---:|---:|---|---|---:|",
    ]
    for row in rows:
        lines.append(
            "| {task} | {char} | `{counts}` | {length} | {max_step} | {out} | {z_range} | {pen_up} |".format(
                task=row.get("task") or Path(str(row.get("task_dir", ""))).name,
                char=row.get("char", ""),
                counts=json.dumps(row.get("segment_counts", {}), ensure_ascii=False, sort_keys=True),
                length=row.get("workspace_path_length_mm", ""),
                max_step=row.get("max_step_mm", ""),
                out=row.get("out_of_bounds", ""),
                z_range=row.get("z_range", ""),
                pen_up=row.get("pen_up_move_length_mm", ""),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_preview_compare(items: Sequence[tuple[str, Path]], path: Path) -> None:
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    images = [Image.open(image_path).convert("RGB") for _, image_path in items]
    cell_w = max(image.width for image in images)
    cell_h = max(image.height for image in images)
    label_h = 54
    out = Image.new("RGB", (cell_w * len(items), cell_h + label_h), "white")
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        font = ImageFont.load_default()
    for idx, ((label, _), image) in enumerate(zip(items, images)):
        x = idx * cell_w + (cell_w - image.width) // 2
        bbox = draw.textbbox((0, 0), label, font=font)
        draw.text((idx * cell_w + (cell_w - (bbox[2] - bbox[0])) // 2, 8), label, fill="#222222", font=font)
        out.paste(image, (x, label_h))
    out.save(path)


def process_batch(input_dir: Path | str, config: WorkspaceConfig) -> dict[str, Any]:
    batch_dir = Path(input_dir)
    dirs = _task_dirs(batch_dir)
    rows = [process_task_dir(task_dir, config) for task_dir in dirs]
    summary_csv = batch_dir / "workspace_mapping_summary.csv"
    report_md = batch_dir / "workspace_mapping_report.md"
    _write_summary(rows, summary_csv)
    _write_batch_report(rows, report_md, config)

    by_char_id: dict[str, list[tuple[str, Path]]] = {}
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
        by_char_id.setdefault(char_id, []).append((label, Path(str(row["workspace_preview_png"]))))

    ablation_images: dict[str, str] = {}
    for char_id, items in by_char_id.items():
        if len(items) < 1:
            continue
        out_path = batch_dir / f"workspace_ablation_{char_id}.png"
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
    parser = argparse.ArgumentParser(description="Map execution trajectories into a robot paper workspace")
    parser.add_argument("--input", default=str(DEFAULT_BATCH), help="Task dir or batch dir containing execution_trajectory.csv files")
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--paper-width-mm", type=float, default=120.0)
    parser.add_argument("--paper-height-mm", type=float, default=120.0)
    parser.add_argument("--pen-up-height-mm", type=float, default=8.0)
    parser.add_argument("--connector-z-lift-mm", type=float, default=0.0)
    parser.add_argument("--base-speed-mm-s", type=float, default=30.0)
    parser.add_argument("--max-jump-threshold-mm", type=float, default=15.0)
    args = parser.parse_args()
    config = WorkspaceConfig(
        image_size=args.image_size,
        paper_width_mm=args.paper_width_mm,
        paper_height_mm=args.paper_height_mm,
        pen_up_height_mm=args.pen_up_height_mm,
        connector_z_lift_mm=args.connector_z_lift_mm,
        base_speed_mm_s=args.base_speed_mm_s,
        max_jump_threshold_mm=args.max_jump_threshold_mm,
    )
    result = process_batch(Path(args.input), config)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
