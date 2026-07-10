"""Font-driven style gap analysis for local style-profile diagnostics.

This module renders local fonts and compares static contour metrics against
the current MakeMeAHanzi + style-profile trajectory diagnostics. It does not
call APIs, CoppeliaSim, robot SDKs, IK, or real robot commands.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_CONFIG = EXP_DIR / "configs" / "font_style_gap_chars.json"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
STYLE_ORDER = ["kaishu", "xingkai", "lishu"]

SUMMARY_FIELDS = [
    "char",
    "style",
    "font_available",
    "rendered_ok",
    "font_path",
    "font_image_path",
    "font_bbox_width",
    "font_bbox_height",
    "font_aspect_ratio",
    "font_black_pixel_ratio",
    "font_connected_component_count",
    "font_largest_component_ratio",
    "font_horizontal_projection_spread",
    "font_vertical_projection_spread",
    "font_stroke_width_mean",
    "font_stroke_width_std",
    "trajectory_aspect_ratio",
    "trajectory_bbox_width",
    "trajectory_bbox_height",
    "trajectory_connection_count",
    "trajectory_connector_draw_length",
    "trajectory_mean_width",
    "trajectory_workspace_path_length_mm",
    "aspect_ratio_gap",
    "abs_aspect_ratio_gap",
    "width_height_gap",
    "lishu_flatness_gap",
    "xingkai_connectedness_gap",
    "notes",
]

STYLE_MEAN_FIELDS = [
    "style",
    "sample_count",
    "mean_font_aspect_ratio",
    "mean_trajectory_aspect_ratio",
    "mean_abs_aspect_ratio_gap",
    "mean_font_connected_component_count",
    "mean_trajectory_connection_count",
    "mean_font_stroke_width",
    "mean_trajectory_mean_width",
]

CHAR_REPORT_FIELDS = [
    "char",
    "font_aspect_spread",
    "trajectory_aspect_spread",
    "style_separation_gap",
    "font_connectedness_spread",
    "trajectory_connection_spread",
    "notes",
]

FAILURE_FIELDS = ["char", "style", "reason", "font_path", "notes"]


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _resolve_path(path_text: str, base_dir: Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _font_candidates(style_sources: dict[str, Any], style: str, config_dir: Path) -> list[Path]:
    spec = style_sources.get(style, {})
    return [_resolve_path(str(item), config_dir) for item in spec.get("font_paths", [])]


def _first_existing_font(style_sources: dict[str, Any], style: str, config_dir: Path) -> Path | None:
    for path in _font_candidates(style_sources, style, config_dir):
        if path.exists():
            return path
    return None


def render_char_with_font(char: str, font_path: Path, image_size: int = 256) -> np.ndarray:
    font_size = max(8, int(image_size * 0.78))
    font = ImageFont.truetype(str(font_path), font_size)
    image = Image.new("L", (image_size, image_size), 255)
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), char, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (image_size - text_w) / 2.0 - bbox[0]
    y = (image_size - text_h) / 2.0 - bbox[1]
    draw.text((x, y), char, font=font, fill=0)
    arr = np.asarray(image)
    return np.where(arr < 200, 255, 0).astype(np.uint8)


def _projection_spread(mask: np.ndarray, axis: int) -> float:
    projection = mask.sum(axis=axis).astype(float)
    total = float(projection.sum())
    if total <= 1e-9:
        return 0.0
    coords = np.arange(len(projection), dtype=float)
    mean = float((coords * projection).sum() / total)
    variance = float((((coords - mean) ** 2) * projection).sum() / total)
    return math.sqrt(max(variance, 0.0))


def compute_font_image_metrics(binary: np.ndarray) -> dict[str, Any]:
    img = np.asarray(binary)
    if img.ndim == 3:
        img = img[:, :, 0]
    mask = img > 0
    if not np.any(mask):
        return {
            "rendered_ok": False,
            "font_bbox_width": 0,
            "font_bbox_height": 0,
            "font_aspect_ratio": 0.0,
            "font_black_pixel_ratio": 0.0,
            "font_connected_component_count": 0,
            "font_largest_component_ratio": 0.0,
            "font_horizontal_projection_spread": 0.0,
            "font_vertical_projection_spread": 0.0,
            "font_stroke_width_mean": 0.0,
            "font_stroke_width_std": 0.0,
        }

    ys, xs = np.nonzero(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    bbox_width = x1 - x0 + 1
    bbox_height = y1 - y0 + 1
    labels_count, labels = cv2.connectedComponents(mask.astype(np.uint8), connectivity=8)
    component_areas = [int((labels == label).sum()) for label in range(1, labels_count)]
    black_pixels = int(mask.sum())
    largest_ratio = (max(component_areas) / black_pixels) if component_areas and black_pixels else 0.0
    dist = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
    widths = 2.0 * dist[dist > 0]
    return {
        "rendered_ok": True,
        "font_bbox_width": int(bbox_width),
        "font_bbox_height": int(bbox_height),
        "font_aspect_ratio": round(bbox_width / bbox_height if bbox_height else 0.0, 6),
        "font_black_pixel_ratio": round(float(mask.mean()), 6),
        "font_connected_component_count": int(max(0, labels_count - 1)),
        "font_largest_component_ratio": round(float(largest_ratio), 6),
        "font_horizontal_projection_spread": round(_projection_spread(mask, axis=0), 6),
        "font_vertical_projection_spread": round(_projection_spread(mask, axis=1), 6),
        "font_stroke_width_mean": round(float(widths.mean()), 6) if len(widths) else 0.0,
        "font_stroke_width_std": round(float(widths.std()), 6) if len(widths) else 0.0,
    }


def render_font_sample(char: str, font_path: Path | None, image_size: int, output_path: Path) -> dict[str, Any]:
    if font_path is None or not Path(font_path).exists():
        return {
            "font_available": False,
            "rendered_ok": False,
            "font_path": str(font_path or ""),
            "font_image_path": "",
            "notes": "missing_font",
            **compute_font_image_metrics(np.zeros((image_size, image_size), dtype=np.uint8)),
        }
    try:
        binary = render_char_with_font(char, Path(font_path), image_size=image_size)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(255 - binary).save(output_path)
        return {
            "font_available": True,
            "font_path": str(font_path),
            "font_image_path": str(output_path),
            "notes": "",
            **compute_font_image_metrics(binary),
        }
    except Exception as exc:  # pragma: no cover - defensive around font engines
        return {
            "font_available": True,
            "rendered_ok": False,
            "font_path": str(font_path),
            "font_image_path": "",
            "notes": f"render_failed: {exc}",
            **compute_font_image_metrics(np.zeros((image_size, image_size), dtype=np.uint8)),
        }


def _trajectory_index(summary_csv: Path) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in _read_csv(summary_csv):
        if str(row.get("success", "")).lower() not in {"true", "1", "yes"}:
            continue
        key = (row.get("char", ""), row.get("style", ""))
        if key[0] and key[1]:
            out[key] = row
    return out


def _trajectory_values(row: dict[str, str] | None) -> dict[str, float]:
    row = row or {}
    return {
        "trajectory_aspect_ratio": _safe_float(row.get("aspect_ratio")),
        "trajectory_bbox_width": _safe_float(row.get("bbox_width")),
        "trajectory_bbox_height": _safe_float(row.get("bbox_height")),
        "trajectory_connection_count": _safe_float(row.get("connection_count")),
        "trajectory_connector_draw_length": _safe_float(row.get("connector_draw_length")),
        "trajectory_mean_width": _safe_float(row.get("mean_width")),
        "trajectory_workspace_path_length_mm": _safe_float(row.get("workspace_path_length_mm")),
    }


def _summary_row(char: str, style: str, font_metrics: dict[str, Any], trajectory: dict[str, float]) -> dict[str, Any]:
    aspect_gap = trajectory["trajectory_aspect_ratio"] - _safe_float(font_metrics.get("font_aspect_ratio"))
    width_height_gap = (trajectory["trajectory_bbox_width"] - _safe_float(font_metrics.get("font_bbox_width"))) - (
        trajectory["trajectory_bbox_height"] - _safe_float(font_metrics.get("font_bbox_height"))
    )
    lishu_gap = aspect_gap if style == "lishu" else 0.0
    connectedness_gap = (
        trajectory["trajectory_connection_count"] - _safe_float(font_metrics.get("font_connected_component_count"))
        if style == "xingkai"
        else 0.0
    )
    notes = str(font_metrics.get("notes", ""))
    if not trajectory["trajectory_aspect_ratio"]:
        notes = (notes + "; " if notes else "") + "missing_trajectory_metrics"
    return {
        "char": char,
        "style": style,
        **font_metrics,
        **trajectory,
        "aspect_ratio_gap": round(aspect_gap, 6),
        "abs_aspect_ratio_gap": round(abs(aspect_gap), 6),
        "width_height_gap": round(width_height_gap, 6),
        "lishu_flatness_gap": round(lishu_gap, 6),
        "xingkai_connectedness_gap": round(connectedness_gap, 6),
        "notes": notes,
    }


def _mean(rows: Sequence[dict[str, Any]], key: str) -> float:
    vals = [_safe_float(row.get(key)) for row in rows if row.get(key) not in ("", None)]
    return round(float(np.mean(vals)), 6) if vals else 0.0


def _style_means(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("rendered_ok") in {True, "True", "true"}:
            grouped[str(row.get("style"))].append(row)
    out: list[dict[str, Any]] = []
    for style in STYLE_ORDER:
        group = grouped.get(style, [])
        if not group:
            continue
        out.append(
            {
                "style": style,
                "sample_count": len(group),
                "mean_font_aspect_ratio": _mean(group, "font_aspect_ratio"),
                "mean_trajectory_aspect_ratio": _mean(group, "trajectory_aspect_ratio"),
                "mean_abs_aspect_ratio_gap": _mean(group, "abs_aspect_ratio_gap"),
                "mean_font_connected_component_count": _mean(group, "font_connected_component_count"),
                "mean_trajectory_connection_count": _mean(group, "trajectory_connection_count"),
                "mean_font_stroke_width": _mean(group, "font_stroke_width_mean"),
                "mean_trajectory_mean_width": _mean(group, "trajectory_mean_width"),
            }
        )
    return out


def _char_report(rows: Sequence[dict[str, Any]], chars: Sequence[str]) -> list[dict[str, Any]]:
    by_char: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("rendered_ok") in {True, "True", "true"}:
            by_char[str(row.get("char"))].append(row)
    out: list[dict[str, Any]] = []
    for char in chars:
        group = by_char.get(char, [])
        if not group:
            continue
        font_aspects = [_safe_float(row.get("font_aspect_ratio")) for row in group]
        traj_aspects = [_safe_float(row.get("trajectory_aspect_ratio")) for row in group]
        font_components = [_safe_float(row.get("font_connected_component_count")) for row in group]
        traj_connections = [_safe_float(row.get("trajectory_connection_count")) for row in group]
        font_spread = max(font_aspects) - min(font_aspects) if font_aspects else 0.0
        traj_spread = max(traj_aspects) - min(traj_aspects) if traj_aspects else 0.0
        out.append(
            {
                "char": char,
                "font_aspect_spread": round(font_spread, 6),
                "trajectory_aspect_spread": round(traj_spread, 6),
                "style_separation_gap": round(font_spread - traj_spread, 6),
                "font_connectedness_spread": round(max(font_components) - min(font_components), 6) if font_components else 0.0,
                "trajectory_connection_spread": round(max(traj_connections) - min(traj_connections), 6) if traj_connections else 0.0,
                "notes": "font styles separate more than trajectory" if font_spread > traj_spread else "",
            }
        )
    return out


def _failures(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for row in rows:
        if row.get("rendered_ok") in {True, "True", "true"}:
            continue
        failures.append(
            {
                "char": row.get("char", ""),
                "style": row.get("style", ""),
                "reason": "missing_font" if not row.get("font_available") else "render_failed",
                "font_path": row.get("font_path", ""),
                "notes": row.get("notes", ""),
            }
        )
    return failures


def _load_config(config_path: Path) -> dict[str, Any]:
    data = _load_json(config_path)
    return {
        "chars": [str(item) for item in data.get("chars", [])],
        "styles": [str(item) for item in data.get("styles", STYLE_ORDER)],
        "font_sources": Path(str(data.get("font_sources", EXP_DIR / "configs" / "style_sources.json"))),
        "trajectory_diagnostics_dir": Path(
            str(data.get("trajectory_diagnostics_dir", EXP_DIR / "outputs" / "style_diagnostics_20260617_200746"))
        ),
    }


def _write_font_grid(rows: Sequence[dict[str, Any]], chars: Sequence[str], styles: Sequence[str], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    max_chars = min(len(chars), 18)
    fig, axes = plt.subplots(max_chars, len(styles), figsize=(2.0 * len(styles), 1.8 * max_chars), dpi=120)
    if max_chars == 1:
        axes = np.asarray([axes])
    for row_idx, char in enumerate(chars[:max_chars]):
        for col_idx, style in enumerate(styles):
            ax = axes[row_idx, col_idx]
            item = next((row for row in rows if row.get("char") == char and row.get("style") == style), None)
            ax.axis("off")
            ax.set_title(f"u{ord(char):04x}-{style}", fontsize=7)
            if item and item.get("font_image_path") and Path(str(item["font_image_path"])).exists():
                img = Image.open(str(item["font_image_path"]))
                ax.imshow(img, cmap="gray")
            else:
                ax.text(0.5, 0.5, "missing", ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _bar_plot(labels: list[str], values: list[float], out_path: Path, title: str, ylabel: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(max(5.5, 0.4 * len(labels)), 3.4), dpi=140)
    ax.bar(labels, values, color="#4c78a8")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _write_figures(rows: Sequence[dict[str, Any]], style_means: Sequence[dict[str, Any]], char_rows: Sequence[dict[str, Any]], chars: Sequence[str], styles: Sequence[str], figures_dir: Path) -> None:
    _write_font_grid(rows, chars, styles, figures_dir / "font_style_grid.png")
    labels = [str(row["style"]) for row in style_means]
    _bar_plot(
        labels,
        [_safe_float(row.get("mean_font_aspect_ratio")) for row in style_means],
        figures_dir / "font_vs_trajectory_aspect_ratio.png",
        "Mean font aspect ratio by style",
        "font aspect ratio",
    )
    _bar_plot(
        [str(row["char"]) for row in char_rows],
        [_safe_float(row.get("style_separation_gap")) for row in char_rows],
        figures_dir / "style_separation_gap.png",
        "Font-vs-trajectory style separation gap",
        "aspect spread gap",
    )
    lishu_rows = [row for row in rows if row.get("style") == "lishu"]
    _bar_plot(
        [f"u{ord(str(row['char'])):04x}" for row in lishu_rows],
        [_safe_float(row.get("lishu_flatness_gap")) for row in lishu_rows],
        figures_dir / "lishu_flatness_gap.png",
        "Lishu flatness gap",
        "trajectory aspect - font aspect",
    )
    xing_rows = [row for row in rows if row.get("style") == "xingkai"]
    _bar_plot(
        [f"u{ord(str(row['char'])):04x}" for row in xing_rows],
        [_safe_float(row.get("xingkai_connectedness_gap")) for row in xing_rows],
        figures_dir / "xingkai_connectedness_gap.png",
        "Xingkai connectedness weak gap",
        "trajectory connections - font components",
    )


def _write_report(
    path: Path,
    *,
    config: dict[str, Any],
    output_dir: Path,
    summary_rows: Sequence[dict[str, Any]],
    style_means: Sequence[dict[str, Any]],
    char_rows: Sequence[dict[str, Any]],
    failures: Sequence[dict[str, Any]],
) -> None:
    total = len(summary_rows)
    success = total - len(failures)
    mean_by_style = {str(row["style"]): row for row in style_means}
    kaishu = mean_by_style.get("kaishu", {})
    xingkai = mean_by_style.get("xingkai", {})
    lishu = mean_by_style.get("lishu", {})
    lines = [
        "# Font-driven style gap analysis / 字体轮廓驱动的风格差距诊断",
        "",
        "## 本轮目的",
        "",
        "本轮停止细枝末节调参，先分析真实字体轮廓与当前参数化轨迹之间的差距。",
        "本轮不调参数，不替换全局默认，不生成最终新轨迹。",
        "",
        "## 输入与输出",
        "",
        f"- output_dir: `{output_dir}`",
        f"- font_sources: `{config['font_sources']}`",
        f"- trajectory_diagnostics_dir: `{config['trajectory_diagnostics_dir']}`",
        f"- chars: `{len(config['chars'])}`",
        f"- styles: `{', '.join(config['styles'])}`",
        "",
        "## 样本统计",
        "",
        f"- total: `{total}`",
        f"- rendered_success: `{success}`",
        f"- failures: `{len(failures)}`",
        "",
        "## 三风格字体侧均值",
        "",
        "| style | samples | mean_font_aspect_ratio | mean_trajectory_aspect_ratio | mean_abs_aspect_ratio_gap | mean_font_components | mean_trajectory_connections | mean_font_stroke_width | mean_trajectory_mean_width |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in style_means:
        lines.append(
            "| {style} | {sample_count} | {mean_font_aspect_ratio} | {mean_trajectory_aspect_ratio} | {mean_abs_aspect_ratio_gap} | {mean_font_connected_component_count} | {mean_trajectory_connection_count} | {mean_font_stroke_width} | {mean_trajectory_mean_width} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
        "## 字体 vs 当前轨迹的主要 gap",
        "",
        "- lishu：重点看 `font_aspect_ratio` 与当前 `trajectory_aspect_ratio` 的差距，判断当前是否只是全局压扁/拉宽。",
        "- xingkai：字体图像的 connected component 只能弱对应连通性，不能直接等价于真实连笔；它用于提示当前 connector prior 是否过于人工。",
        "- kaishu / xingkai / lishu：比较字体三风格的 aspect spread 与轨迹三风格的 aspect spread，定位哪些字的字体差异大但轨迹差异小。",
        "",
        "### 主要发现",
        "",
        f"- lishu 平均字体 aspect ratio `{lishu.get('mean_font_aspect_ratio', '')}`，当前轨迹 `{lishu.get('mean_trajectory_aspect_ratio', '')}`；均值接近，但这不能证明已经学到隶书结构，只说明全局宽扁比例接近。",
        f"- xingkai 平均字体 connected component `{xingkai.get('mean_font_connected_component_count', '')}`，当前轨迹 connection_count `{xingkai.get('mean_trajectory_connection_count', '')}`；当前 connector 规则比字体静态连通性更激进，且二者只是弱对应。",
        f"- kaishu 平均字体 aspect ratio `{kaishu.get('mean_font_aspect_ratio', '')}`，当前轨迹 `{kaishu.get('mean_trajectory_aspect_ratio', '')}`；楷书整体比例 gap 最小。",
        "- style gap 的重点不是继续微调 connector，而是把横纵比例、笔画宽度分布、投影分布和连接先验从字体/图像统计中系统估计出来。",
        "",
        "## 参数升级建议",
            "",
            "- 可从字体统计估计：`horizontal_scale / vertical_scale`、stroke width distribution、component-level proportions、connectedness / connector prior、projection distribution。",
            "- 仍不能从静态字体直接估计：真实速度、真实抬笔高度、真实机器人动态控制。",
            "",
            "## 失败样本",
            "",
        ]
    )
    if failures:
        lines.extend(["| char | style | reason | notes |", "|---|---|---|---|"])
        for row in failures:
            lines.append(f"| {row['char']} | {row['style']} | {row['reason']} | {row['notes']} |")
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 字体轮廓不等于真实书写轨迹。",
            "- 字体静态图无法直接给出真实书写时序。",
            "- 本轮不调参数，不进入 CoppeliaSim / AUBO i5 / IK / SDK / 机器人控制。",
            "- 仍需要人工看图校验，尤其是字体网格图和 gap 图。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(path: Path, *, output_dir: Path) -> None:
    lines = [
        "# Font Style Gap Analysis Index",
        "",
        f"- source_output_dir: `{output_dir}`",
        "- scope: font contour metrics vs current trajectory diagnostics; no parameter tuning, no API, no robot interface.",
        "",
        "| File | Content |",
        "|---|---|",
        "| `font_style_gap_report.md` | 字体轮廓差距诊断报告 |",
        "| `font_style_gap_style_means.csv` | 三风格均值表 |",
        "| `font_style_grid.png` | 真实字体三风格网格 |",
        "| `font_vs_trajectory_aspect_ratio.png` | 字体 aspect ratio 对比图 |",
        "| `lishu_flatness_gap.png` | 隶书宽扁差距图 |",
        "| `xingkai_connectedness_gap.png` | 行楷连通性弱对应差距图 |",
        "| `style_separation_gap.png` | 字体/轨迹风格分离度差距图 |",
        "",
        "本轮只是 gap analysis，不生成最终新轨迹。字体轮廓不等于真实书写轨迹，仍需人工看图校验。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_font_style_gap_analysis(
    *,
    config_path: Path = DEFAULT_CONFIG,
    output_dir: Path | None = None,
    image_size: int = 256,
    copy_to_paper: bool = True,
    paper_dir: Path = DEFAULT_PAPER_DIR,
) -> dict[str, Any]:
    config_path = Path(config_path)
    config = _load_config(config_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"font_style_gap_analysis_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = out_dir / "figures"
    rendered_dir = out_dir / "rendered_fonts"
    source_path = _resolve_path(str(config["font_sources"]), ROOT)
    style_sources = _load_json(source_path)
    traj_summary = _resolve_path(str(config["trajectory_diagnostics_dir"]), ROOT) / "style_diagnostic_summary.csv"
    traj_index = _trajectory_index(traj_summary)

    summary_rows: list[dict[str, Any]] = []
    for char in config["chars"]:
        for style in config["styles"]:
            font_path = _first_existing_font(style_sources, style, source_path.parent)
            image_path = rendered_dir / style / f"u{ord(char):04x}.png"
            font_metrics = render_font_sample(char, font_path, image_size, image_path)
            trajectory = _trajectory_values(traj_index.get((char, style)))
            summary_rows.append(_summary_row(char, style, font_metrics, trajectory))

    style_means = _style_means(summary_rows)
    char_rows = _char_report(summary_rows, config["chars"])
    failures = _failures(summary_rows)

    summary_csv = out_dir / "font_style_gap_summary.csv"
    style_means_csv = out_dir / "font_style_gap_style_means.csv"
    char_report_csv = out_dir / "font_style_gap_char_report.csv"
    failures_csv = out_dir / "font_style_gap_failures.csv"
    report_md = out_dir / "font_style_gap_report.md"
    _write_csv(summary_csv, summary_rows, SUMMARY_FIELDS)
    _write_csv(style_means_csv, style_means, STYLE_MEAN_FIELDS)
    _write_csv(char_report_csv, char_rows, CHAR_REPORT_FIELDS)
    _write_csv(failures_csv, failures, FAILURE_FIELDS)
    _write_figures(summary_rows, style_means, char_rows, config["chars"], config["styles"], figures_dir)
    _write_report(
        report_md,
        config=config,
        output_dir=out_dir,
        summary_rows=summary_rows,
        style_means=style_means,
        char_rows=char_rows,
        failures=failures,
    )

    paper_index = ""
    if copy_to_paper:
        paper_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report_md, paper_dir / "font_style_gap_report.md")
        shutil.copy2(style_means_csv, paper_dir / "font_style_gap_style_means.csv")
        for name in [
            "font_style_grid.png",
            "font_vs_trajectory_aspect_ratio.png",
            "lishu_flatness_gap.png",
            "xingkai_connectedness_gap.png",
            "style_separation_gap.png",
        ]:
            src = figures_dir / name
            if src.exists():
                shutil.copy2(src, paper_dir / name)
        index_path = paper_dir / "font_style_gap_analysis_index.md"
        _write_paper_index(index_path, output_dir=out_dir)
        paper_index = str(index_path)

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "style_means_csv": str(style_means_csv),
        "char_report_csv": str(char_report_csv),
        "failures_csv": str(failures_csv),
        "report_md": str(report_md),
        "figures_dir": str(figures_dir),
        "total": len(summary_rows),
        "success_count": len(summary_rows) - len(failures),
        "failure_count": len(failures),
        "paper_index": paper_index,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run font-driven style gap analysis.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--no-paper-copy", action="store_true")
    args = parser.parse_args()
    result = run_font_style_gap_analysis(
        config_path=args.config,
        output_dir=args.out_dir,
        image_size=args.image_size,
        copy_to_paper=not args.no_paper_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
