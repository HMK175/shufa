"""Redraw key B-route visuals with Chinese labels and stronger difference cues.

This module only reads existing trial outputs and redraws presentation figures.
It does not modify any trajectory generation algorithm, parameters, default
pipeline behavior, or robot-related artifacts.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches
from mpl_toolkits.axes_grid1.inset_locator import inset_axes, mark_inset

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from constraint_bounded_adaptation_h1_lite import _bbox, _flatten, _load_median
from font_outline_basis_feasibility import first_existing_font, render_char_with_font
from hybrid_section_refinement_v1 import assign_sections_to_points, build_hybrid_sections
from median_font_adaptation_v2 import DEFAULT_STYLE_SOURCES


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_OUTPUT_ROOT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"

SOURCE_H1_LITE_CONTRAST = (
    EXP_DIR / "outputs" / "h1_lite_style_contrast_20260619_234043"
)
SOURCE_H1_LITE_BASE = (
    EXP_DIR / "outputs" / "constraint_bounded_adaptation_h1_lite_20260619_231903"
)
SOURCE_FENG_RISK = (
    EXP_DIR / "outputs" / "h1_lite_feng_lishu_risk_trial_20260620_212829"
)
SOURCE_HYBRID_SECTION = (
    EXP_DIR / "outputs" / "hybrid_section_refinement_20260620_215513"
)

LABEL_MAP = {
    "original median": "原始中位轨迹",
    "conservative": "保守版",
    "balanced": "平衡版",
    "known positive reference": "已知正例参考",
    "font sections (top_mid_bottom_fallback)": "字体分区（上/中/下回退）",
    "median + section labels": "中位轨迹 + 分区标签",
    "top_band": "上区",
    "mid_band": "中区",
    "bottom_band": "下区",
}

MANIFEST_FIELDS = [
    "artifact_name",
    "source_artifact",
    "output_path",
    "status",
    "difference_overlay",
    "inset_zoom",
    "notes",
]


def _configure_matplotlib_cn() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False


def _char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else ""


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_trial_csv(path: Path) -> list[np.ndarray]:
    strokes: list[list[list[float]]] = []
    current: list[list[float]] = []
    current_stroke_id: str | None = None
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            is_break = str(row.get("is_break", "0")).strip() == "1"
            y_raw = str(row.get("y", "")).strip()
            x_raw = str(row.get("x", "")).strip()
            stroke_id = str(row.get("stroke_id", "")).strip() or current_stroke_id
            if current_stroke_id is None:
                current_stroke_id = stroke_id
            if is_break or y_raw.lower() == "nan" or x_raw.lower() == "nan":
                if current:
                    strokes.append(current)
                    current = []
                current_stroke_id = None
                continue
            if stroke_id != current_stroke_id and current:
                strokes.append(current)
                current = []
            current_stroke_id = stroke_id
            current.append([float(y_raw), float(x_raw)])
    if current:
        strokes.append(current)
    return [np.asarray(stroke, dtype=float) for stroke in strokes if stroke]


def _load_style_sources(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _render_font_mask(char: str, style: str, image_size: int = 256) -> np.ndarray:
    style_sources = _load_style_sources(DEFAULT_STYLE_SOURCES)
    font_path = first_existing_font(style_sources, style, DEFAULT_STYLE_SOURCES.parent)
    if font_path is None:
        return np.zeros((image_size, image_size), dtype=bool)
    return render_char_with_font(char, font_path, image_size=image_size)


def _axis_setup(ax: Any, title: str, xlim: tuple[float, float] = (0, 256), ylim: tuple[float, float] = (256, 0)) -> None:
    ax.set_title(title, fontsize=10)
    ax.set_aspect("equal")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(True, color="#ececec", linewidth=0.4)


def _plot_strokes(ax: Any, strokes: Sequence[np.ndarray], color: str, linewidth: float = 2.0, alpha: float = 1.0, zorder: int = 2) -> None:
    for stroke in strokes:
        pts = np.asarray(stroke, dtype=float)
        if len(pts) == 0:
            continue
        if len(pts) == 1:
            ax.scatter(pts[:, 1], pts[:, 0], s=10, color=color, alpha=alpha, zorder=zorder)
            continue
        ax.plot(pts[:, 1], pts[:, 0], color=color, linewidth=linewidth, alpha=alpha, zorder=zorder)


def _plot_overlay(
    ax: Any,
    original: Sequence[np.ndarray],
    adapted: Sequence[np.ndarray],
    adapted_color: str,
    title: str,
    displacement_stride: int = 3,
) -> None:
    _axis_setup(ax, title)
    _plot_strokes(ax, original, color="#9a9a9a", linewidth=1.8, alpha=0.9, zorder=1)
    _plot_strokes(ax, adapted, color=adapted_color, linewidth=2.2, alpha=0.95, zorder=3)
    for src_stroke, dst_stroke in zip(original, adapted):
        src = np.asarray(src_stroke, dtype=float)
        dst = np.asarray(dst_stroke, dtype=float)
        limit = min(len(src), len(dst))
        for idx in range(0, limit, max(displacement_stride, 1)):
            ax.plot(
                [src[idx, 1], dst[idx, 1]],
                [src[idx, 0], dst[idx, 0]],
                color=adapted_color,
                linewidth=0.7,
                alpha=0.35,
                zorder=2,
            )


def _zoom_bounds(strokes: Sequence[np.ndarray], mode: str) -> tuple[float, float, float, float]:
    pts = _flatten(strokes)
    box = _bbox(pts)
    if mode == "shan_lower":
        x0 = box["x_min"] - 6
        x1 = box["x_max"] + 6
        y0 = box["y_min"] + 0.45 * box["height"]
        y1 = box["y_max"] + 4
        return (x0, x1, y1, y0)
    if mode == "feng_lower":
        x_pad = max(6.0, box["width"] * 0.04)
        x0 = box["x_min"] - x_pad
        x1 = box["x_max"] + x_pad
        y0 = box["y_min"] + 0.36 * box["height"]
        y1 = box["y_max"] + 5
        return (x0, x1, y1, y0)
    return (box["x_min"], box["x_max"], box["y_max"], box["y_min"])


def _add_zoom_inset(
    ax: Any,
    original: Sequence[np.ndarray],
    overlays: Sequence[tuple[Sequence[np.ndarray], str]],
    mode: str,
    inset_title: str,
) -> None:
    x0, x1, y_bottom, y_top = _zoom_bounds(original, mode)
    rect = patches.Rectangle(
        (x0, y_top),
        x1 - x0,
        y_bottom - y_top,
        fill=False,
        edgecolor="#666666",
        linestyle="--",
        linewidth=0.8,
        alpha=0.85,
    )
    ax.add_patch(rect)
    ins = inset_axes(ax, width="40%", height="40%", loc="lower left", borderpad=1.0)
    _axis_setup(ins, inset_title, xlim=(x0, x1), ylim=(y_bottom, y_top))
    _plot_strokes(ins, original, color="#9a9a9a", linewidth=1.3, alpha=0.95, zorder=1)
    for strokes, color in overlays:
        _plot_strokes(ins, strokes, color=color, linewidth=1.6, alpha=0.96, zorder=3)
    mark_inset(ax, ins, loc1=2, loc2=4, fc="none", ec="#888888", lw=0.7)


def _plot_mask(ax: Any, mask: np.ndarray, title: str) -> None:
    ax.set_title(title, fontsize=10)
    ax.imshow(np.where(mask, 0.82, 1.0), cmap="gray", vmin=0, vmax=1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])


def _plot_section_mask(ax: Any, mask: np.ndarray, sections: Sequence[dict[str, Any]], title: str) -> None:
    _plot_mask(ax, mask, title)
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    for idx, section in enumerate(sections):
        box = section["bbox"]
        color = colors[idx % len(colors)]
        ax.add_patch(
            patches.Rectangle(
                (box["x_min"], box["y_min"]),
                max(box["x_max"] - box["x_min"], 1.0),
                max(box["y_max"] - box["y_min"], 1.0),
                fill=False,
                edgecolor=color,
                linewidth=1.1,
            )
        )
        label = LABEL_MAP.get(str(section["name"]), str(section["name"]))
        ax.text(box["x_min"] + 2, box["y_min"] + 10, label, color=color, fontsize=8)


def _plot_section_labels(ax: Any, strokes: Sequence[np.ndarray], labels: Sequence[Sequence[str]], title: str) -> None:
    _axis_setup(ax, title)
    colors = {
        "top_band": "#1f77b4",
        "mid_band": "#ff7f0e",
        "bottom_band": "#2ca02c",
        "component_1": "#1f77b4",
        "component_2": "#ff7f0e",
        "component_3": "#2ca02c",
        "component_4": "#d62728",
    }
    for stroke, stroke_labels in zip(strokes, labels):
        pts = np.asarray(stroke, dtype=float)
        ax.plot(pts[:, 1], pts[:, 0], color="#999999", linewidth=1.3, alpha=0.75)
        for (y, x), label in zip(pts, stroke_labels):
            ax.scatter(x, y, s=14, color=colors.get(label, "#666666"), alpha=0.9)
    used = list(dict.fromkeys(label for stroke_labels in labels for label in stroke_labels))
    for idx, label in enumerate(used[:3]):
        ax.text(
            4,
            12 + idx * 10,
            LABEL_MAP.get(label, label),
            fontsize=8,
            color=colors.get(label, "#444444"),
            ha="left",
            va="top",
        )


@dataclass
class RedrawArtifact:
    artifact_name: str
    source_artifact: str
    output_path: str
    status: str
    difference_overlay: bool
    inset_zoom: bool
    notes: str


def _draw_h1_lite_shan_contrast(output_path: Path) -> dict[str, Any]:
    kaishu_dir = SOURCE_H1_LITE_CONTRAST / "u5c71_kaishu"
    lishu_dir = SOURCE_H1_LITE_BASE / "u5c71_lishu"
    median = _load_median("山", image_size=256)
    kaishu_cons = _read_trial_csv(kaishu_dir / "h1_lite_conservative.csv")
    kaishu_bal = _read_trial_csv(kaishu_dir / "h1_lite_balanced.csv")
    lishu_cons = _read_trial_csv(lishu_dir / "h1_lite_conservative.csv")
    lishu_bal = _read_trial_csv(lishu_dir / "h1_lite_balanced.csv")
    gap = _read_json(SOURCE_H1_LITE_CONTRAST / "contrast" / "h1_lite_u5c71_style_gap_summary.json")

    fig, axes = plt.subplots(2, 4, figsize=(15.6, 7.6), dpi=180)
    _axis_setup(axes[0, 0], "山 / 楷书：原始中位轨迹")
    _plot_strokes(axes[0, 0], median, color="#4d4d4d", linewidth=2.1)
    _plot_overlay(axes[0, 1], median, kaishu_cons, "#1f77b4", "山 / 楷书：保守版（叠加）")
    _plot_overlay(axes[0, 2], median, kaishu_bal, "#2b83ba", "山 / 楷书：平衡版（叠加）")
    _add_zoom_inset(axes[0, 2], median, [(kaishu_bal, "#2b83ba")], "shan_lower", "下半部放大")
    _axis_setup(axes[0, 3], "楷书 / 隶书：平衡版对照")
    _plot_strokes(axes[0, 3], kaishu_bal, color="#2b83ba", linewidth=2.1)
    _plot_strokes(axes[0, 3], lishu_bal, color="#d95f02", linewidth=2.1)
    axes[0, 3].text(6, 14, "蓝：楷书平衡版", color="#2b83ba", fontsize=8, ha="left", va="top")
    axes[0, 3].text(6, 24, "橙：隶书平衡版", color="#d95f02", fontsize=8, ha="left", va="top")

    _axis_setup(axes[1, 0], "山 / 隶书：原始中位轨迹")
    _plot_strokes(axes[1, 0], median, color="#4d4d4d", linewidth=2.1)
    _plot_overlay(axes[1, 1], median, lishu_cons, "#ff7f0e", "山 / 隶书：保守版（叠加）")
    _plot_overlay(axes[1, 2], median, lishu_bal, "#d95f02", "山 / 隶书：平衡版（叠加）")
    _add_zoom_inset(axes[1, 2], median, [(lishu_bal, "#d95f02")], "shan_lower", "底横放大")
    x0, x1, y_bottom, y_top = _zoom_bounds(median, "shan_lower")
    _axis_setup(axes[1, 3], "底部差异放大")
    axes[1, 3].set_xlim(x0, x1)
    axes[1, 3].set_ylim(y_bottom, y_top)
    _plot_strokes(axes[1, 3], median, color="#9a9a9a", linewidth=1.4)
    _plot_strokes(axes[1, 3], kaishu_bal, color="#2b83ba", linewidth=1.8)
    _plot_strokes(axes[1, 3], lishu_bal, color="#d95f02", linewidth=1.8)
    axes[1, 3].text(
        x0 + 2,
        y_top + 6,
        f"balanced 后 bbox_aspect gap={gap['kaishu_lishu_style_gap_after_balanced']['bbox_aspect_gap']:.3f}\n"
        f"lower_half_width gap={gap['kaishu_lishu_style_gap_after_balanced']['lower_half_width_gap']:.3f}",
        fontsize=8,
        ha="left",
        va="top",
        color="#333333",
    )

    fig.suptitle("H1-lite 风格对照：山 / 楷书 vs 隶书", fontsize=13)
    fig.subplots_adjust(left=0.03, right=0.99, bottom=0.05, top=0.88, wspace=0.16, hspace=0.10)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    return {
        "style_gap_before": gap["kaishu_lishu_style_gap_before"],
        "style_gap_after_balanced": gap["kaishu_lishu_style_gap_after_balanced"],
    }


def _draw_h1_lite_feng_risk(output_path: Path) -> dict[str, Any]:
    risk_dir = SOURCE_FENG_RISK / "u98ce_lishu"
    reference_dir = SOURCE_H1_LITE_BASE / "u5c71_lishu"
    median = _load_median("风", image_size=256)
    conservative = _read_trial_csv(risk_dir / "h1_lite_conservative.csv")
    balanced = _read_trial_csv(risk_dir / "h1_lite_balanced.csv")
    reference_bal = _read_trial_csv(reference_dir / "h1_lite_balanced.csv")
    summary = _read_json(risk_dir / "h1_lite_summary.json")

    fig, axes = plt.subplots(1, 5, figsize=(17.2, 4.2), dpi=180)
    _axis_setup(axes[0], "风 / 隶书：原始中位轨迹")
    _plot_strokes(axes[0], median, color="#4d4d4d", linewidth=2.0)
    _plot_overlay(axes[1], median, conservative, "#d95f02", "风 / 隶书：保守版（叠加）")
    _add_zoom_inset(axes[1], median, [(conservative, "#d95f02")], "feng_lower", "下半部放大")
    _plot_overlay(axes[2], median, balanced, "#c51b7d", "风 / 隶书：平衡版（叠加）")
    _add_zoom_inset(axes[2], median, [(balanced, "#c51b7d")], "feng_lower", "左右展开放大")
    _axis_setup(axes[3], "已知正例参考：山 / 隶书")
    _plot_strokes(axes[3], reference_bal, color="#2ca25f", linewidth=2.1)
    _axis_setup(axes[4], "风 / 隶书：局部对照放大")
    x0, x1, y_bottom, y_top = _zoom_bounds(median, "feng_lower")
    axes[4].set_xlim(x0, x1)
    axes[4].set_ylim(y_bottom, y_top)
    _plot_strokes(axes[4], median, color="#9a9a9a", linewidth=1.4)
    _plot_strokes(axes[4], conservative, color="#d95f02", linewidth=1.7)
    _plot_strokes(axes[4], balanced, color="#c51b7d", linewidth=1.9)
    axes[4].text(
        x0 + 3,
        y_top + 6,
        f"bbox_aspect: {summary['bbox_aspect_median']:.3f} -> {summary['bbox_aspect_conservative']:.3f} / {summary['bbox_aspect_balanced']:.3f}\n"
        f"lower_half_width: {summary['lower_half_width_median']:.1f} -> {summary['lower_half_width_conservative']:.1f} / {summary['lower_half_width_balanced']:.1f}",
        fontsize=7.7,
        ha="left",
        va="top",
        color="#333333",
    )

    fig.suptitle("H1-lite 风/隶书风险试验", fontsize=13)
    fig.subplots_adjust(left=0.03, right=0.99, bottom=0.08, top=0.85, wspace=0.14)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    return {
        "bbox_aspect_balanced": summary["bbox_aspect_balanced"],
        "lower_half_width_balanced": summary["lower_half_width_balanced"],
        "max_shift_balanced": summary["max_point_shift_px"]["balanced"],
    }


def _draw_hybrid_section_compare(output_path: Path) -> dict[str, Any]:
    sample_dir = SOURCE_HYBRID_SECTION / "u98ce_lishu"
    median = _load_median("风", image_size=256)
    conservative = _read_trial_csv(sample_dir / "hybrid_section_conservative.csv")
    balanced = _read_trial_csv(sample_dir / "hybrid_section_balanced.csv")
    summary = _read_json(sample_dir / "hybrid_section_summary.json")
    mask = _render_font_mask("风", "lishu", image_size=256)
    section_info = build_hybrid_sections(mask, max_sections=4)
    sections = section_info["sections"]
    labels = assign_sections_to_points(median, sections)

    fig, axes = plt.subplots(1, 5, figsize=(17.4, 4.2), dpi=180)
    _axis_setup(axes[0], "原始中位轨迹")
    _plot_strokes(axes[0], median, color="#4d4d4d", linewidth=2.0)
    _plot_section_mask(axes[1], mask, sections, "字体分区（上/中/下回退）")
    _plot_section_labels(axes[2], median, labels, "中位轨迹 + 分区标签")
    _plot_overlay(axes[3], median, conservative, "#d95f02", "分区约束：保守版（叠加）")
    _add_zoom_inset(axes[3], median, [(conservative, "#d95f02")], "feng_lower", "下半部放大")
    _plot_overlay(axes[4], median, balanced, "#7b3294", "分区约束：平衡版（叠加）")
    _add_zoom_inset(axes[4], median, [(balanced, "#7b3294")], "feng_lower", "左右展开放大")
    axes[4].text(
        4,
        16,
        f"分区来源：上/中/下回退\n"
        f"分区标签：{','.join(LABEL_MAP.get(name, name) for name in summary['section_names'])}",
        fontsize=7.6,
        ha="left",
        va="top",
        color="#333333",
    )
    fig.suptitle("风/隶书分区约束精修 v1", fontsize=13)
    fig.subplots_adjust(left=0.03, right=0.99, bottom=0.08, top=0.85, wspace=0.14)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path)
    plt.close(fig)
    return {
        "section_count": summary["section_count"],
        "section_names": summary["section_names"],
        "section_source": summary["section_source"],
        "bbox_aspect_balanced": summary["bbox_aspect_balanced"],
    }


def _write_report(path: Path, output_dir: Path, figure_notes: Sequence[dict[str, Any]]) -> None:
    lines = [
        "# B-route 关键图中文化与差异辅助重绘",
        "",
        "本轮只重绘图的表达方式，不改算法、不调参数、不接默认 pipeline。",
        "",
        "## 中文标题与标签替换",
        "",
        "- `original median` -> `原始中位轨迹`",
        "- `conservative` -> `保守版`",
        "- `balanced` -> `平衡版`",
        "- `known positive reference` -> `已知正例参考`",
        "- `font sections (top_mid_bottom_fallback)` -> `字体分区（上/中/下回退）`",
        "- `median + section labels` -> `中位轨迹 + 分区标签`",
        "- `top_band / mid_band / bottom_band` -> `上区 / 中区 / 下区`",
        "",
        "## 差异辅助",
        "",
        "- 三张图都增加了“原始灰色轨迹 + 调整后彩色轨迹”的叠加层。",
        "- 在位移较明显的点上增加了淡色连线，帮助人工看到 `原始 -> 调整后` 的方向。",
        "- `山` 增加了底部区域放大；`风` 增加了下半部和左右展开区域放大。",
        "- `hybrid section` 图额外补了字体分区和中位轨迹分区标签，方便判断 section fallback 是否真的在起作用。",
        "",
        "## 图级判断",
        "",
        "| 图 | 变化表达 | 当前人工复检建议 |",
        "|---|---|---|",
    ]
    for item in figure_notes:
        lines.append(
            f"| `{item['artifact_name']}` | {item['difference_note']} | {item['review_note']} |"
        )
    lines.extend(
        [
            "",
            "## 诚实说明",
            "",
            "- `山/kaishu vs 山/lishu` 的差异经过对照叠加和底部放大后更容易看，但差异仍然很弱，不能把这张图写成“风格差异非常明显”。",
            "- `风/lishu` 的 conservative / balanced 现在更容易看出下半部和左右展开差异，但两者总体仍然接近，这张图仍需要人工反复比对。",
            "- `hybrid_section_compare_cn` 现在最适合做人工判断，因为它把 section 分区、原始轨迹、保守版和平衡版放在同一页里，能更直观看到“分区约束是否真的带来局部变化”。",
            "",
            "## 边界",
            "",
            "- visual_redraw_only_not_used_by_default",
            "- 不生成新 trajectory / execution / workspace / robot 文件",
            "- 不改默认 pipeline，不改 style/profile，不改 trial 数据本身",
            "",
            f"- output_dir: `{output_dir}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(path: Path, output_dir: Path, artifacts: Sequence[RedrawArtifact], summary_json: Path) -> None:
    lines = [
        "# B-route 中文图与差异辅助索引",
        "",
        f"- source_output_dir: `{output_dir}`",
        f"- summary_json: `{summary_json}`",
        "- status: visual_redraw_only_not_used_by_default",
        "- boundary: presentation-only redraw, no algorithm change, no default pipeline integration.",
        "",
        "| 文件 | 说明 |",
        "|---|---|",
    ]
    for item in artifacts:
        lines.append(f"| `{Path(item.output_path).name}` | {item.notes} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _update_text_file_append(path: Path, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    if content.strip() in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    text += "\n" + content.strip() + "\n"
    path.write_text(text, encoding="utf-8")


def run_redraw_b_route_visuals_cn(
    output_dir: Path | str | None = None,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    _configure_matplotlib_cn()
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT_ROOT / f"b_route_visuals_cn_{timestamp}"
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    shan_png = out_dir / "h1_lite_u5c71_kaishu_lishu_contrast_cn.png"
    feng_png = out_dir / "h1_lite_u98ce_lishu_risk_contrast_cn.png"
    hybrid_png = out_dir / "hybrid_section_compare_cn.png"

    shan_meta = _draw_h1_lite_shan_contrast(shan_png)
    feng_meta = _draw_h1_lite_feng_risk(feng_png)
    hybrid_meta = _draw_hybrid_section_compare(hybrid_png)

    artifacts = [
        RedrawArtifact(
            artifact_name=shan_png.name,
            source_artifact=str(SOURCE_H1_LITE_CONTRAST / "contrast" / "h1_lite_u5c71_kaishu_lishu_contrast.png"),
            output_path=str(shan_png),
            status="visual_redraw_only_not_used_by_default",
            difference_overlay=True,
            inset_zoom=True,
            notes="山/kaishu vs 山/lishu 的同字风格对照，新增底部放大和叠加差异。",
        ),
        RedrawArtifact(
            artifact_name=feng_png.name,
            source_artifact=str(SOURCE_FENG_RISK / "contrast" / "h1_lite_u98ce_lishu_risk_contrast.png"),
            output_path=str(feng_png),
            status="visual_redraw_only_not_used_by_default",
            difference_overlay=True,
            inset_zoom=True,
            notes="风/lishu 风险试验，新增 conservative / balanced 与局部展开放大。",
        ),
        RedrawArtifact(
            artifact_name=hybrid_png.name,
            source_artifact=str(SOURCE_HYBRID_SECTION / "u98ce_lishu" / "hybrid_section_compare.png"),
            output_path=str(hybrid_png),
            status="visual_redraw_only_not_used_by_default",
            difference_overlay=True,
            inset_zoom=True,
            notes="风/lishu hybrid section 图，补了中文分区标签与局部放大。",
        ),
    ]

    report_md = out_dir / "b_route_visuals_cn_report.md"
    manifest_csv = out_dir / "b_route_visuals_cn_manifest.csv"
    summary_json = out_dir / "b_route_visuals_cn_summary.json"

    figure_notes = [
        {
            "artifact_name": shan_png.name,
            "difference_note": (
                f"balanced 后山字的 style gap 增至 bbox_aspect={shan_meta['style_gap_after_balanced']['bbox_aspect_gap']:.3f}，"
                f"lower_half_width={shan_meta['style_gap_after_balanced']['lower_half_width_gap']:.3f}"
            ),
            "review_note": "现在能看出隶书更宽底，但整体差异仍偏弱。"
        },
        {
            "artifact_name": feng_png.name,
            "difference_note": (
                f"balanced 后 bbox_aspect={feng_meta['bbox_aspect_balanced']:.3f}，"
                f"lower_half_width={feng_meta['lower_half_width_balanced']:.3f}"
            ),
            "review_note": "保守版与平衡版仍接近，是三张图里最弱的一张。"
        },
        {
            "artifact_name": hybrid_png.name,
            "difference_note": (
                f"section_source={hybrid_meta['section_source']}，"
                f"balanced aspect={hybrid_meta['bbox_aspect_balanced']:.3f}"
            ),
            "review_note": "现在最适合人工判断 section 约束是否真的生效。"
        },
    ]

    _write_report(report_md, out_dir, figure_notes)
    _write_csv(
        manifest_csv,
        [
            {
                "artifact_name": item.artifact_name,
                "source_artifact": item.source_artifact,
                "output_path": item.output_path,
                "status": item.status,
                "difference_overlay": item.difference_overlay,
                "inset_zoom": item.inset_zoom,
                "notes": item.notes,
            }
            for item in artifacts
        ],
        MANIFEST_FIELDS,
    )

    summary_payload = {
        "status": "visual_redraw_only_not_used_by_default",
        "figure_count": 3,
        "output_dir": str(out_dir),
        "label_map": LABEL_MAP,
        "artifacts": [item.__dict__ for item in artifacts],
        "visually_subtle_artifacts": [
            shan_png.name,
            feng_png.name,
        ],
        "best_manual_review_artifact": hybrid_png.name,
    }
    summary_json.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    paper_index = ""
    if copy_to_paper:
        DEFAULT_PAPER_DIR.mkdir(parents=True, exist_ok=True)
        for file_path in [shan_png, feng_png, hybrid_png, report_md, manifest_csv, summary_json]:
            shutil.copy2(file_path, DEFAULT_PAPER_DIR / file_path.name)
        index_path = DEFAULT_PAPER_DIR / "b_route_visuals_cn_index.md"
        _write_paper_index(index_path, out_dir, artifacts, summary_json)
        paper_index = str(index_path)

        paper_index_append = """
## B-route 中文图与差异辅助

源目录：

```text
experiments/llm_style_trajectory/outputs/b_route_visuals_cn_*/
```

固定资料：

| 文件 | 内容 |
|---|---|
| `b_route_visuals_cn_index.md` | 中文重绘入口 |
| `h1_lite_u5c71_kaishu_lishu_contrast_cn.png` | 山/楷书 vs 山/隶书中文对照 |
| `h1_lite_u98ce_lishu_risk_contrast_cn.png` | 风/隶书风险试验中文图 |
| `hybrid_section_compare_cn.png` | 风/隶书 section refinement 中文图 |
| `b_route_visuals_cn_report.md` | 哪张图差异仍弱、哪张更适合人工判断 |
"""
        _update_text_file_append(DEFAULT_PAPER_DIR / "paper_experiment_index.md", paper_index_append)

    if copy_to_paper:
        stage_append = """
# 2026-06-21 B-route 关键图中文化 + 差异辅助重绘

本轮不做新实验，只对三张关键 B-route 图做中文化和差异辅助表达增强：

- `h1_lite_u5c71_kaishu_lishu_contrast_cn.png`
- `h1_lite_u98ce_lishu_risk_contrast_cn.png`
- `hybrid_section_compare_cn.png`

重绘内容包括：中文标题、中文 panel 标签、原始灰色轨迹与调整后彩色轨迹叠加、位移细连线、以及 `山` 底部 / `风` 下半部的局部放大。

诊断：`山/kaishu vs 山/lishu` 现在更容易看出宽底差异，但整体差异仍偏弱；`风/lishu` 的 conservative / balanced 仍然接近，是最需要诚实提示“差异不大”的一张；`hybrid_section_compare_cn` 现在最适合做人工判断，因为 section 分区、原始轨迹和两档 refinement 被放在同一页里。

边界：本轮是 presentation-only redraw，不改算法、不调参数、不接默认 pipeline，不生成 execution/workspace/robot 文件。
"""
        _update_text_file_append(ROOT / "LLM_STYLE_TRAJECTORY_STAGE_SUMMARY.md", stage_append)

        experiment_append = """
- 2026-06-21：完成 B-route 三张关键图的中文化与差异辅助重绘，只重绘表达，不改算法。结论：`山/kaishu vs 山/lishu` 仍属弱差异；`风/lishu` conservative vs balanced 最接近；`hybrid_section_compare_cn` 最适合人工复检。
"""
        _update_text_file_append(ROOT / "EXPERIMENT_RECORD.md", experiment_append)
        _update_text_file_append(ROOT / "PROJECT_LOG.md", experiment_append)

    return {
        "output_dir": str(out_dir),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "summary_json": str(summary_json),
        "paper_index": paper_index,
    }


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args(argv)
    result = run_redraw_b_route_visuals_cn(output_dir=args.out_dir, copy_to_paper=not args.no_copy_to_paper)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
