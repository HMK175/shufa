"""Multi-character style-profile diagnostic experiment.

This module stays in the deterministic local pipeline: mock planner, style
profiles, trajectory/execution tools, workspace mapping, and workspace
resampling. It does not call APIs, CoppeliaSim, AUBO SDKs, IK, or robot
commands.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from PIL import Image, ImageDraw, ImageFont

from knowledge import MakeMeAHanziKnowledge
from run_demo import (
    DEFAULT_BRUSH_PROFILES,
    DEFAULT_GRAPHICS,
    DEFAULT_OUTPUT,
    DEFAULT_PROFILES,
    run_task,
)
from style_profile_compare import safe_char_id
from workspace_mapping import WorkspaceConfig, process_task_dir as process_workspace_task
from workspace_resampling import ResamplingConfig, process_task_dir as process_resampling_task


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = EXP_DIR / "configs" / "style_diagnostic_chars.json"
STYLE_ORDER = ["kaishu", "xingkai", "lishu"]
STYLE_DISPLAY = {
    "kaishu": "楷书",
    "xingkai": "行楷",
    "lishu": "隶书",
}

SUMMARY_FIELDS = [
    "char",
    "style",
    "task",
    "success",
    "failure_reason",
    "output_dir",
    "stroke_count",
    "path_length",
    "mean_turning",
    "total_turning_angle",
    "max_turning_angle",
    "aspect_ratio",
    "bbox_width",
    "bbox_height",
    "connection_count",
    "connector_draw_length",
    "pen_up_move_length",
    "mean_width",
    "mean_pressure",
    "connector_mean_width",
    "connector_mean_pressure",
    "workspace_path_length_mm",
    "max_step_mm",
    "max_xy_step_mm",
    "max_z_step_mm",
    "resampled_point_count",
    "resampled_max_step_mm",
    "out_of_bounds",
    "motion_continuity_recommended",
    "retiming_required",
    "trajectory_csv",
    "execution_trajectory_csv",
    "robot_workspace_csv",
    "robot_workspace_resampled_csv",
    "execution_render_png",
    "workspace_preview_png",
    "workspace_resampled_preview_png",
    "summary_json",
]

FAILURE_FIELDS = [
    "char",
    "style",
    "task",
    "success",
    "failure_reason",
]

STYLE_MEAN_FIELDS = [
    "style",
    "sample_count",
    "avg_aspect_ratio",
    "avg_path_length",
    "avg_connection_count",
    "avg_connector_draw_length",
    "avg_pen_up_move_length",
    "avg_mean_width",
    "avg_mean_pressure",
    "avg_workspace_path_length_mm",
    "avg_resampled_point_count",
    "max_out_of_bounds_count",
]

CHAR_MEAN_FIELDS = [
    "char",
    "sample_count",
    "avg_aspect_ratio",
    "avg_path_length",
    "avg_connection_count",
    "avg_connector_draw_length",
    "avg_pen_up_move_length",
    "avg_mean_width",
    "avg_mean_pressure",
    "avg_workspace_path_length_mm",
    "avg_resampled_point_count",
    "max_out_of_bounds_count",
]


def load_diagnostic_config(path: Path | str = DEFAULT_CONFIG) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        "chars": [str(item) for item in data.get("chars", [])],
        "styles": [str(item) for item in data.get("styles", STYLE_ORDER)],
        "planner_mode": str(data.get("planner_mode", "mock")),
    }


def _float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _task_text(char: str, style: str) -> str:
    return f"写一个{STYLE_DISPLAY.get(style, style)}风格的{char}"


def _check_char_available(knowledge: MakeMeAHanziKnowledge, char: str) -> bool:
    try:
        knowledge.get_glyph(char)
        return True
    except KeyError:
        return False


def _max_xy_z_steps(resampled_csv: Path) -> tuple[float, float]:
    rows = _read_csv(resampled_csv)
    max_xy = 0.0
    max_z = 0.0
    for prev, cur in zip(rows, rows[1:]):
        dx = _float(cur.get("X_mm")) - _float(prev.get("X_mm"))
        dy = _float(cur.get("Y_mm")) - _float(prev.get("Y_mm"))
        dz = abs(_float(cur.get("Z_mm")) - _float(prev.get("Z_mm")))
        max_xy = max(max_xy, math.sqrt(dx * dx + dy * dy))
        max_z = max(max_z, dz)
    return round(max_xy, 3), round(max_z, 3)


def _failure_row(char: str, style: str, reason: str) -> dict[str, Any]:
    return {
        "char": char,
        "style": style,
        "task": _task_text(char, style),
        "success": False,
        "failure_reason": reason,
    }


def _success_row(
    *,
    char: str,
    style: str,
    task: str,
    result: dict[str, str],
    workspace: dict[str, Any],
    resampling: dict[str, Any],
) -> dict[str, Any]:
    summary = json.loads(Path(result["summary_json"]).read_text(encoding="utf-8"))
    max_xy, max_z = _max_xy_z_steps(Path(str(resampling["robot_workspace_resampled_csv"])))
    return {
        "char": char,
        "style": style,
        "task": task,
        "success": True,
        "failure_reason": "",
        "output_dir": result["output_dir"],
        "stroke_count": summary.get("stroke_count", ""),
        "path_length": summary.get("path_length", ""),
        "mean_turning": summary.get("mean_turning", ""),
        "total_turning_angle": summary.get("total_turning_angle", ""),
        "max_turning_angle": summary.get("max_turning_angle", ""),
        "aspect_ratio": summary.get("aspect_ratio", ""),
        "bbox_width": summary.get("bounding_box_width", ""),
        "bbox_height": summary.get("bounding_box_height", ""),
        "connection_count": summary.get("connection_count", ""),
        "connector_draw_length": summary.get("connector_draw_length", ""),
        "pen_up_move_length": summary.get("pen_up_move_length", ""),
        "mean_width": summary.get("mean_width", ""),
        "mean_pressure": summary.get("mean_pressure", ""),
        "connector_mean_width": summary.get("connector_mean_width", ""),
        "connector_mean_pressure": summary.get("connector_mean_pressure", ""),
        "workspace_path_length_mm": workspace.get("workspace_path_length_mm", ""),
        "max_step_mm": workspace.get("max_step_mm", ""),
        "max_xy_step_mm": max_xy,
        "max_z_step_mm": max_z,
        "resampled_point_count": resampling.get("resampled_point_count", ""),
        "resampled_max_step_mm": resampling.get("resampled_max_step_mm", ""),
        "out_of_bounds": bool(workspace.get("out_of_bounds")) or bool(resampling.get("out_of_bounds")),
        "motion_continuity_recommended": "not_run",
        "retiming_required": "not_run",
        "trajectory_csv": result.get("trajectory_csv", ""),
        "execution_trajectory_csv": result.get("execution_trajectory_csv", ""),
        "robot_workspace_csv": workspace.get("robot_workspace_csv", ""),
        "robot_workspace_resampled_csv": resampling.get("robot_workspace_resampled_csv", ""),
        "execution_render_png": result.get("execution_render_png", ""),
        "workspace_preview_png": workspace.get("workspace_preview_png", ""),
        "workspace_resampled_preview_png": resampling.get("workspace_resampled_preview_png", ""),
        "summary_json": result.get("summary_json", ""),
    }


def _write_csv_rows(rows: Sequence[dict[str, Any]], path: Path, fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _mean_rows(rows: Sequence[dict[str, Any]], group_field: str, output_field: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(group_field, ""))].append(row)
    output: list[dict[str, Any]] = []
    for group, group_rows in sorted(groups.items()):
        count = len(group_rows)
        output.append(
            {
                output_field: group,
                "sample_count": count,
                "avg_aspect_ratio": round(sum(_float(r.get("aspect_ratio")) for r in group_rows) / count, 6),
                "avg_path_length": round(sum(_float(r.get("path_length")) for r in group_rows) / count, 3),
                "avg_connection_count": round(sum(_float(r.get("connection_count")) for r in group_rows) / count, 3),
                "avg_connector_draw_length": round(sum(_float(r.get("connector_draw_length")) for r in group_rows) / count, 3),
                "avg_pen_up_move_length": round(sum(_float(r.get("pen_up_move_length")) for r in group_rows) / count, 3),
                "avg_mean_width": round(sum(_float(r.get("mean_width")) for r in group_rows) / count, 6),
                "avg_mean_pressure": round(sum(_float(r.get("mean_pressure")) for r in group_rows) / count, 6),
                "avg_workspace_path_length_mm": round(sum(_float(r.get("workspace_path_length_mm")) for r in group_rows) / count, 3),
                "avg_resampled_point_count": round(sum(_float(r.get("resampled_point_count")) for r in group_rows) / count, 3),
                "max_out_of_bounds_count": sum(1 for r in group_rows if str(r.get("out_of_bounds")) == "True" or r.get("out_of_bounds") is True),
            }
        )
    return output


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


def _write_grid(rows: Sequence[dict[str, Any]], out_path: Path, *, max_chars: int = 12) -> None:
    by_char: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_char[str(row["char"])][str(row["style"])] = row
    chars = list(by_char.keys())[:max_chars]
    cells: list[tuple[str, Path]] = []
    for char in chars:
        for style in STYLE_ORDER:
            row = by_char[char].get(style)
            if row and row.get("execution_render_png"):
                cells.append((style, Path(str(row["execution_render_png"]))))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not cells:
        Image.new("RGB", (320, 220), "white").save(out_path)
        return
    images = [(label, Image.open(path).convert("RGB")) for label, path in cells]
    cell_w, cell_h = 260, 260
    label_h = 34
    left_w = 58
    columns = 3
    out = Image.new("RGB", (left_w + columns * cell_w, len(chars) * (cell_h + label_h)), "white")
    draw = ImageDraw.Draw(out)
    label_font = _font(18)
    side_font = _font(22)
    idx = 0
    for row_idx, char in enumerate(chars):
        y0 = row_idx * (cell_h + label_h)
        draw.text((10, y0 + label_h + cell_h // 2 - 14), char, fill="#222222", font=side_font)
        for col_idx, style in enumerate(STYLE_ORDER):
            row = by_char[char].get(style)
            x0 = left_w + col_idx * cell_w
            label = style
            bbox = draw.textbbox((0, 0), label, font=label_font)
            draw.text((x0 + (cell_w - bbox[2] + bbox[0]) // 2, y0 + 6), label, fill="#222222", font=label_font)
            if not row:
                continue
            image = Image.open(str(row["execution_render_png"])).convert("RGB").resize((cell_w, cell_h), Image.Resampling.LANCZOS)
            out.paste(image, (x0, y0 + label_h))
            idx += 1
    out.save(out_path)


def _write_metric_bars(style_means: Sequence[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    metrics = [
        ("avg_aspect_ratio", "aspect"),
        ("avg_path_length", "path"),
        ("avg_connection_count", "conn"),
        ("avg_mean_width", "width"),
        ("avg_workspace_path_length_mm", "workspace"),
    ]
    styles = [str(row["style"]) for row in style_means]
    if not styles:
        Image.new("RGB", (640, 360), "white").save(out_path)
        return
    fig = Figure(figsize=(10, 5), dpi=140)
    canvas = FigureCanvas(fig)
    axes = fig.subplots(1, len(metrics))
    for ax, (field, title) in zip(axes, metrics):
        values = [_float(row.get(field)) for row in style_means]
        ax.bar(styles, values, color=["#4c78a8", "#f58518", "#54a24b"][: len(styles)])
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=35, labelsize=7)
        ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    canvas.print_png(str(out_path))


def _unstable_cases(rows: Sequence[dict[str, Any]]) -> list[str]:
    messages: list[str] = []
    by_char: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_char[str(row["char"])].append(row)
    for char, char_rows in by_char.items():
        aspects = [_float(row.get("aspect_ratio")) for row in char_rows]
        conns = [_float(row.get("connection_count")) for row in char_rows]
        if aspects and max(aspects) - min(aspects) < 0.05:
            messages.append(f"{char}: aspect_ratio style spread < 0.05")
        if conns and max(conns) - min(conns) < 1 and any(row.get("style") == "xingkai" for row in char_rows):
            messages.append(f"{char}: connection_count style spread is weak")
    return messages[:20]


def _write_report(
    *,
    output_dir: Path,
    rows: Sequence[dict[str, Any]],
    failures: Sequence[dict[str, Any]],
    style_means: Sequence[dict[str, Any]],
    char_means: Sequence[dict[str, Any]],
    total: int,
    missing_char_count: int,
    path: Path,
) -> None:
    success_count = len(rows)
    failure_count = len(failures)
    lines = [
        "# 多字样本风格区分度与参数诊断实验",
        "",
        "## 实验目的",
        "",
        "扩充多字样本，诊断当前 `kaishu` / `xingkai` / `lishu` 参数化 style profile 与受控 modifier 在更多结构汉字上的稳定性和可区分性。",
        "",
        "## 输出目录",
        "",
        f"`{output_dir}`",
        "",
        "## 总览",
        "",
        f"- total_samples: `{total}`",
        f"- success_count: `{success_count}`",
        f"- failure_count: `{failure_count}`",
        f"- missing_char_count: `{missing_char_count}`",
        "",
        "## 三风格平均指标",
        "",
        "| style | samples | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in style_means:
        lines.append(
            "| {style} | {count} | {aspect} | {path_len} | {conn} | {connector} | {width} | {workspace} | {bounds} |".format(
                style=row["style"],
                count=row["sample_count"],
                aspect=row["avg_aspect_ratio"],
                path_len=row["avg_path_length"],
                conn=row["avg_connection_count"],
                connector=row["avg_connector_draw_length"],
                width=row["avg_mean_width"],
                workspace=row["avg_workspace_path_length_mm"],
                bounds=row["max_out_of_bounds_count"],
            )
        )
    lines.extend(
        [
            "",
            "## 诊断结论",
            "",
            "- `lishu` 是否更宽扁主要看 `aspect_ratio / bbox_width / bbox_height`；若平均 `aspect_ratio` 明显高于 kaishu/xingkai，则当前宽扁参数仍有效。",
            "- `xingkai` 是否更连贯主要看 `connection_count / connector_draw_length`；若这些指标高于 kaishu/lishu，则默认弱连接逻辑仍稳定。",
            "- `kaishu` 的保守性主要看 `connection_count` 低和 connector 指标接近 0。",
            "",
            "## 失败与异常案例",
            "",
        ]
    )
    if failures:
        lines.extend(["| char | style | failure_reason |", "|---|---|---|"])
        for row in failures:
            lines.append(f"| {row.get('char')} | {row.get('style')} | {row.get('failure_reason')} |")
    else:
        lines.append("- 无失败样本。")
    unstable = _unstable_cases(rows)
    lines.extend(["", "## 风格差异不明显提示", ""])
    if unstable:
        lines.extend(f"- {item}" for item in unstable)
    else:
        lines.append("- 未发现简单阈值下的明显不稳定提示。")
    lines.extend(
        [
            "",
            "## 参数诊断建议",
            "",
            "- 当前较有效参数：`horizontal_scale / vertical_scale`、`allow_interstroke_connections`、`connection_strength`、execution 层 `width / pressure`。",
            "- 当前较粗参数：全字统一缩放和平滑，难以表达部件级、笔画级差异。",
            "- 下一步应优先从字体/图像统计中重新估计：笔画级宽度分布、部件级横纵比例、起收笔宽度变化、转折圆滑度和风格相关 connector 规则。",
            "",
            "## 边界说明",
            "",
            "这不是最终风格学习结果。当前 style profile 仍是参数化 profile + 部分字体统计 + prior；本轮目的是诊断稳定性和失败点，不追求最终书写效果。没有调用 API、CoppeliaSim、AUBO SDK、真实 IK 或任何机器人控制命令。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_style_diagnostics(
    *,
    config_path: Path | str = DEFAULT_CONFIG,
    output_dir: Path | str | None = None,
    graphics_path: Path | str = DEFAULT_GRAPHICS,
    style_profiles_path: Path | str = DEFAULT_PROFILES,
    brush_profiles_path: Path | str = DEFAULT_BRUSH_PROFILES,
    image_size: int = 256,
) -> dict[str, Any]:
    config = load_diagnostic_config(config_path)
    chars = list(config["chars"])
    styles = list(config["styles"])
    planner_mode = str(config.get("planner_mode", "mock"))
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"style_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    knowledge = MakeMeAHanziKnowledge(graphics_path)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for char in chars:
        available = _check_char_available(knowledge, char)
        for style in styles:
            task = _task_text(char, style)
            if style not in STYLE_ORDER:
                failures.append(_failure_row(char, style, "unsupported_style"))
                continue
            if not available:
                failures.append(_failure_row(char, style, "missing_char"))
                continue
            try:
                result = run_task(
                    task_text=task,
                    output_root=out_dir,
                    graphics_path=graphics_path,
                    style_profiles_path=style_profiles_path,
                    image_size=image_size,
                    planner_mode=planner_mode,
                    fallback_to_mock=False,
                    brush_profiles_path=brush_profiles_path,
                )
                task_dir = Path(result["output_dir"])
                workspace = process_workspace_task(task_dir, WorkspaceConfig(image_size=image_size))
                resampling = process_resampling_task(task_dir, ResamplingConfig())
                rows.append(_success_row(char=char, style=style, task=task, result=result, workspace=workspace, resampling=resampling))
            except Exception as exc:  # noqa: BLE001 - diagnostics should record per-sample failures.
                failures.append(_failure_row(char, style, f"{type(exc).__name__}: {exc}"))

    summary_csv = out_dir / "style_diagnostic_summary.csv"
    style_means_csv = out_dir / "style_diagnostic_style_means.csv"
    char_means_csv = out_dir / "style_diagnostic_char_means.csv"
    failures_csv = out_dir / "style_diagnostic_failures.csv"
    report_md = out_dir / "style_diagnostic_report.md"
    grid_png = out_dir / "style_diagnostic_grid.png"
    metric_bars_png = out_dir / "style_metric_bars.png"

    style_means = _mean_rows(rows, "style", "style")
    char_means = _mean_rows(rows, "char", "char")
    _write_csv_rows(rows, summary_csv, SUMMARY_FIELDS)
    _write_csv_rows(style_means, style_means_csv, STYLE_MEAN_FIELDS)
    _write_csv_rows(char_means, char_means_csv, CHAR_MEAN_FIELDS)
    _write_csv_rows(failures, failures_csv, FAILURE_FIELDS)
    _write_grid(rows, grid_png)
    _write_metric_bars(style_means, metric_bars_png)
    missing_char_count = sum(1 for row in failures if row.get("failure_reason") == "missing_char")
    _write_report(
        output_dir=out_dir,
        rows=rows,
        failures=failures,
        style_means=style_means,
        char_means=char_means,
        total=len(chars) * len(styles),
        missing_char_count=missing_char_count,
        path=report_md,
    )

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "style_means_csv": str(style_means_csv),
        "char_means_csv": str(char_means_csv),
        "failures_csv": str(failures_csv),
        "report_md": str(report_md),
        "grid_png": str(grid_png),
        "metric_bars_png": str(metric_bars_png),
        "total": len(chars) * len(styles),
        "success_count": len(rows),
        "failure_count": len(failures),
        "missing_char_count": missing_char_count,
        "style_means": style_means,
        "char_means": char_means,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run multi-character style diagnostics")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--graphics", default=str(DEFAULT_GRAPHICS))
    parser.add_argument("--style-profiles", default=str(DEFAULT_PROFILES))
    parser.add_argument("--brush-profiles", default=str(DEFAULT_BRUSH_PROFILES))
    parser.add_argument("--image-size", type=int, default=256)
    args = parser.parse_args()
    result = run_style_diagnostics(
        config_path=args.config,
        output_dir=args.out_dir,
        graphics_path=args.graphics,
        style_profiles_path=args.style_profiles,
        brush_profiles_path=args.brush_profiles,
        image_size=args.image_size,
    )
    print(json.dumps({k: v for k, v in result.items() if k not in {"failures"}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
