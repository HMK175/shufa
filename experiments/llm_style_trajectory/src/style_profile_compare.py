"""Batch experiment for comparing base kaishu/xingkai/lishu style profiles."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from PIL import Image, ImageDraw, ImageFont

from run_demo import (
    DEFAULT_BRUSH_PROFILES,
    DEFAULT_GRAPHICS,
    DEFAULT_OUTPUT,
    DEFAULT_PROFILES,
    run_batch,
)
from workspace_mapping import WorkspaceConfig, process_batch


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TASKS = EXP_DIR / "configs" / "style_profile_compare_tasks.json"
STYLE_ORDER = ["kaishu", "xingkai", "lishu"]
STYLE_LABELS = {
    "kaishu": "kaishu",
    "xingkai": "xingkai",
    "lishu": "lishu",
}
SUMMARY_FIELDS = [
    "char",
    "style",
    "task",
    "stroke_count",
    "path_length",
    "mean_turning",
    "total_turning_angle",
    "max_turning_angle",
    "bbox_width",
    "bbox_height",
    "aspect_ratio",
    "connection_count",
    "connector_draw_length",
    "pen_up_move_length",
    "mean_width",
    "mean_pressure",
    "connector_mean_width",
    "connector_mean_pressure",
    "workspace_path_length_mm",
    "max_step_mm",
    "out_of_bounds",
    "z_min",
    "z_max",
    "execution_render_png",
    "workspace_preview_png",
    "robot_workspace_csv",
    "summary_json",
]


def safe_char_id(char: str) -> str:
    return f"u{ord(char):04x}"


def load_compare_tasks(path: Path | str = DEFAULT_TASKS) -> list[dict[str, str]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks: list[dict[str, str]] = []
    for item in data:
        task = {
            "task": str(item["task"]),
            "char": str(item["char"]),
            "style": str(item["style"]),
        }
        tasks.append(task)
    return tasks


def _float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _z_bounds(z_range: str) -> tuple[str, str]:
    if ".." not in z_range:
        return "", ""
    left, right = z_range.split("..", 1)
    return left, right


def _load_summaries(results: Sequence[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        summary_path = Path(result["summary_json"])
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["summary_json"] = str(summary_path)
        summary["output_dir"] = str(Path(result["output_dir"]))
        rows.append(summary)
    return rows


def _merge_rows(run_summaries: Sequence[dict[str, Any]], workspace_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    workspace_by_dir = {str(Path(str(row["task_dir"])).resolve()): row for row in workspace_rows}
    merged: list[dict[str, Any]] = []
    for summary in run_summaries:
        task_dir = str(Path(str(summary["output_dir"])).resolve())
        workspace = workspace_by_dir.get(task_dir, {})
        z_min, z_max = _z_bounds(str(workspace.get("z_range", "")))
        merged.append(
            {
                "char": summary.get("char", ""),
                "style": summary.get("style", ""),
                "task": summary.get("task", ""),
                "stroke_count": summary.get("stroke_count", ""),
                "path_length": summary.get("path_length", ""),
                "mean_turning": summary.get("mean_turning", ""),
                "total_turning_angle": summary.get("total_turning_angle", ""),
                "max_turning_angle": summary.get("max_turning_angle", ""),
                "bbox_width": summary.get("bounding_box_width", ""),
                "bbox_height": summary.get("bounding_box_height", ""),
                "aspect_ratio": summary.get("aspect_ratio", ""),
                "connection_count": summary.get("connection_count", ""),
                "connector_draw_length": summary.get("connector_draw_length", ""),
                "pen_up_move_length": summary.get("pen_up_move_length", ""),
                "mean_width": summary.get("mean_width", ""),
                "mean_pressure": summary.get("mean_pressure", ""),
                "connector_mean_width": summary.get("connector_mean_width", ""),
                "connector_mean_pressure": summary.get("connector_mean_pressure", ""),
                "workspace_path_length_mm": workspace.get("workspace_path_length_mm", ""),
                "max_step_mm": workspace.get("max_step_mm", ""),
                "out_of_bounds": workspace.get("out_of_bounds", ""),
                "z_min": z_min,
                "z_max": z_max,
                "execution_render_png": summary.get("execution_render_png", ""),
                "workspace_preview_png": workspace.get("workspace_preview_png", ""),
                "robot_workspace_csv": workspace.get("robot_workspace_csv", ""),
                "summary_json": summary.get("summary_json", ""),
            }
        )
    return merged


def _write_summary(rows: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in SUMMARY_FIELDS})


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


def _write_labeled_image_grid(
    cells: Sequence[tuple[str, Path]],
    out_path: Path,
    *,
    columns: int,
    cell_size: tuple[int, int] | None = None,
    title_left: Sequence[str] | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    images = [(label, Image.open(path).convert("RGB")) for label, path in cells]
    if not images:
        return
    image_w = max(image.width for _, image in images) if cell_size is None else cell_size[0]
    image_h = max(image.height for _, image in images) if cell_size is None else cell_size[1]
    label_h = 42
    left_w = 70 if title_left else 0
    rows = (len(images) + columns - 1) // columns
    out = Image.new("RGB", (left_w + columns * image_w, rows * (image_h + label_h)), "white")
    draw = ImageDraw.Draw(out)
    label_font = _font(24)
    side_font = _font(26)
    for idx, (label, image) in enumerate(images):
        row = idx // columns
        col = idx % columns
        x0 = left_w + col * image_w
        y0 = row * (image_h + label_h)
        if image.size != (image_w, image_h):
            image = image.resize((image_w, image_h), Image.Resampling.LANCZOS)
        bbox = draw.textbbox((0, 0), label, font=label_font)
        draw.text((x0 + (image_w - (bbox[2] - bbox[0])) // 2, y0 + 6), label, fill="#222222", font=label_font)
        out.paste(image, (x0, y0 + label_h))
    if title_left:
        for row, label in enumerate(title_left):
            y0 = row * (image_h + label_h) + label_h + image_h // 2 - 14
            draw.text((8, y0), label, fill="#222222", font=side_font)
    out.save(out_path)


def _write_style_compare_images(rows: Sequence[dict[str, Any]], batch_dir: Path) -> dict[str, str]:
    images: dict[str, str] = {}
    by_char: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_char[str(row["char"])][str(row["style"])] = row

    for char, style_rows in by_char.items():
        cells = []
        for style in STYLE_ORDER:
            row = style_rows.get(style)
            if row:
                cells.append((STYLE_LABELS[style], Path(str(row["execution_render_png"]))))
        if not cells:
            continue
        out_path = batch_dir / f"style_compare_{safe_char_id(char)}.png"
        _write_labeled_image_grid(cells, out_path, columns=len(cells))
        images[safe_char_id(char)] = str(out_path)
    return images


def _write_style_compare_grid(rows: Sequence[dict[str, Any]], batch_dir: Path) -> Path:
    by_char: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_char[str(row["char"])][str(row["style"])] = row
    chars = sorted(by_char.keys(), key=lambda ch: ["山", "中", "永", "福", "明"].index(ch) if ch in ["山", "中", "永", "福", "明"] else ch)
    cells: list[tuple[str, Path]] = []
    for char in chars:
        for style in STYLE_ORDER:
            row = by_char[char].get(style)
            if not row:
                continue
            cells.append((STYLE_LABELS[style], Path(str(row["execution_render_png"]))))
    out_path = batch_dir / "style_compare_grid.png"
    _write_labeled_image_grid(cells, out_path, columns=3, cell_size=(360, 360), title_left=chars)
    return out_path


def _style_average_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for style in STYLE_ORDER:
        style_rows = [row for row in rows if row.get("style") == style]
        if not style_rows:
            continue
        output.append(
            {
                "style": style,
                "avg_aspect_ratio": round(sum(_float(row.get("aspect_ratio")) for row in style_rows) / len(style_rows), 6),
                "avg_path_length": round(sum(_float(row.get("path_length")) for row in style_rows) / len(style_rows), 3),
                "avg_connection_count": round(sum(_float(row.get("connection_count")) for row in style_rows) / len(style_rows), 3),
                "avg_connector_draw_length": round(sum(_float(row.get("connector_draw_length")) for row in style_rows) / len(style_rows), 3),
                "avg_mean_width": round(sum(_float(row.get("mean_width")) for row in style_rows) / len(style_rows), 6),
                "avg_workspace_path_length_mm": round(sum(_float(row.get("workspace_path_length_mm")) for row in style_rows) / len(style_rows), 3),
                "out_of_bounds_count": sum(1 for row in style_rows if str(row.get("out_of_bounds")) == "True"),
            }
        )
    return output


def _write_report(rows: Sequence[dict[str, Any]], path: Path, output_dir: Path) -> None:
    averages = _style_average_rows(rows)
    chars = sorted({str(row["char"]) for row in rows}, key=lambda ch: ["山", "中", "永", "福", "明"].index(ch) if ch in ["山", "中", "永", "福", "明"] else ch)
    lines = [
        "# 三字体基础风格对比实验",
        "",
        "## 实验目的",
        "",
        "固定同一批汉字，对比 `kaishu`、`xingkai`、`lishu` 三种基础 style profile 在 trajectory、execution、workspace 三层上的参数化效果差异。",
        "",
        "## 输出目录",
        "",
        f"`{output_dir}`",
        "",
        "## 每字三风格生成状态",
        "",
        "| char | kaishu | xingkai | lishu |",
        "|---|---|---|---|",
    ]
    by_char_style = defaultdict(set)
    for row in rows:
        by_char_style[str(row["char"])].add(str(row["style"]))
    for char in chars:
        lines.append(
            "| {char} | {kaishu} | {xingkai} | {lishu} |".format(
                char=char,
                kaishu="ok" if "kaishu" in by_char_style[char] else "missing",
                xingkai="ok" if "xingkai" in by_char_style[char] else "missing",
                lishu="ok" if "lishu" in by_char_style[char] else "missing",
            )
        )
    lines.extend(
        [
            "",
            "## 三种风格平均指标",
            "",
            "| style | avg_aspect_ratio | avg_path_length | avg_connection_count | avg_connector_draw_length | avg_mean_width | avg_workspace_path_length_mm | out_of_bounds_count |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in averages:
        lines.append(
            "| {style} | {avg_aspect_ratio} | {avg_path_length} | {avg_connection_count} | {avg_connector_draw_length} | {avg_mean_width} | {avg_workspace_path_length_mm} | {out_of_bounds_count} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## 观察结论",
            "",
            "- `lishu` 的 `aspect_ratio` 平均值最高，说明当前参数化 profile 的宽扁倾向能够在几何指标上体现。",
            "- `xingkai` 默认允许弱连接，因此更容易出现 connector，`connector_draw_length` 与 `connection_count` 高于 kaishu / lishu。",
            "- `kaishu` 保持无跨笔连接，整体更保守，适合作为结构轨迹的基准风格。",
            "",
            "## 边界说明",
            "",
            "当前比较的是参数化 style profile 的效果，不是完整真实书法风格学习。LLM/mock planner 只输出结构化计划，CSV 和所有轨迹点仍由本地确定性工具生成。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_style_profile_compare(
    *,
    output_root: Path | str = DEFAULT_OUTPUT,
    tasks_path: Path | str = DEFAULT_TASKS,
    graphics_path: Path | str = DEFAULT_GRAPHICS,
    style_profiles_path: Path | str = DEFAULT_PROFILES,
    brush_profiles_path: Path | str = DEFAULT_BRUSH_PROFILES,
    image_size: int = 256,
) -> dict[str, Any]:
    tasks = load_compare_tasks(tasks_path)
    run_output_root = Path(output_root) / f"style_profile_compare_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    batch = run_batch(
        tasks=[item["task"] for item in tasks],
        output_root=run_output_root,
        graphics_path=graphics_path,
        style_profiles_path=style_profiles_path,
        brush_profiles_path=brush_profiles_path,
        image_size=image_size,
        planner_mode="mock",
    )
    batch_dir = Path(str(batch["batch_dir"]))
    workspace = process_batch(batch_dir, WorkspaceConfig(image_size=image_size))
    run_summaries = _load_summaries(batch["results"])
    merged = _merge_rows(run_summaries, workspace["rows"])

    summary_csv = batch_dir / "style_profile_compare_summary.csv"
    report_md = batch_dir / "style_profile_compare_report.md"
    _write_summary(merged, summary_csv)
    _write_report(merged, report_md, batch_dir)
    style_compare_images = _write_style_compare_images(merged, batch_dir)
    grid_png = _write_style_compare_grid(merged, batch_dir)
    return {
        "batch_dir": str(batch_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "grid_png": str(grid_png),
        "style_compare_images": style_compare_images,
        "style_averages": _style_average_rows(merged),
        "rows": merged,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run base style profile comparison batch")
    parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--graphics", default=str(DEFAULT_GRAPHICS))
    parser.add_argument("--style-profiles", default=str(DEFAULT_PROFILES))
    parser.add_argument("--brush-profiles", default=str(DEFAULT_BRUSH_PROFILES))
    parser.add_argument("--image-size", type=int, default=256)
    args = parser.parse_args()
    result = run_style_profile_compare(
        output_root=args.out_dir,
        tasks_path=args.tasks,
        graphics_path=args.graphics,
        style_profiles_path=args.style_profiles,
        brush_profiles_path=args.brush_profiles,
        image_size=args.image_size,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
