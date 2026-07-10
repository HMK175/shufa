from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - plotting dependency fallback
    plt = None


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_VISUAL_AUDIT_DIR = (
    ROOT
    / "experiments"
    / "llm_style_trajectory"
    / "outputs"
    / "style_visual_audit_20260617_224321"
)
DEFAULT_DIAGNOSTIC_DIR = (
    ROOT
    / "experiments"
    / "llm_style_trajectory"
    / "outputs"
    / "style_diagnostics_20260617_200746"
)
DEFAULT_PAPER_DIR = ROOT / "experiments" / "llm_style_trajectory" / "outputs" / "paper_figures"

STYLES = ("kaishu", "lishu", "xingkai")
CONNECTOR_CHARS = ("国", "德", "福")
SIDE_BY_SIDE_CHARS = ("人", "中", "和")
LISHU_DEFORMATION_CHARS = ("人", "好", "风")

CASE_FIELDS = [
    "char",
    "style",
    "case_type",
    "source_output_dir",
    "generated_figure",
    "connection_count",
    "connector_draw_length",
    "connector_mean_width",
    "connector_mean_pressure",
    "mean_width",
    "aspect_ratio",
    "diagnostic_focus",
    "needs_user_review",
]

MANIFEST_FIELDS = [
    "char",
    "style",
    "figure_type",
    "source_output_dir",
    "source_image",
    "generated_figure",
    "selected_case_copy",
    "warning",
]

NUMERIC_FIELDS = {
    "y",
    "x",
    "z",
    "speed",
    "pressure",
    "width",
    "pen_down",
    "is_connector",
    "segment_id",
    "stroke_id",
    "point_id",
}


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _to_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _sample_char_from_output_dir(output_dir: str) -> str:
    name = Path(output_dir).name
    match = re.match(r"u([0-9a-fA-F]{4,6})_", name)
    if match:
        try:
            return chr(int(match.group(1), 16))
        except ValueError:
            return ""
    return ""


def _normal_char(row: dict[str, str]) -> str:
    return _sample_char_from_output_dir(row.get("output_dir", "")) or row.get("char", "")


def _sample_key(row: dict[str, str]) -> tuple[str, str]:
    return _normal_char(row), row.get("style", "")


def _row_output_dir(row: dict[str, str]) -> Path:
    return Path(row.get("output_dir", ""))


def _execution_path(row: dict[str, str]) -> Path:
    explicit = row.get("execution_trajectory_csv", "")
    if explicit:
        return Path(explicit)
    return _row_output_dir(row) / "execution_trajectory.csv"


def _source_image(row: dict[str, str]) -> Path | None:
    for field in ("execution_render_png", "image_path", "preview_png", "workspace_preview_png"):
        value = row.get(field, "")
        if value and Path(value).exists():
            return Path(value)
    output_dir = _row_output_dir(row)
    for name in ("execution_render.png", "execution_debug.png", "preview.png"):
        path = output_dir / name
        if path.exists():
            return path
    return None


def _read_execution_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            parsed: dict[str, object] = {}
            for key, value in row.items():
                parsed[key] = _to_float(value) if key in NUMERIC_FIELDS else value
            rows.append(parsed)
    return rows


def _group_segments(rows: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    if not rows:
        return []
    grouped: list[list[dict[str, object]]] = []
    current: list[dict[str, object]] = []
    current_id: object = None
    for row in rows:
        segment_id = row.get("segment_id")
        if current and segment_id != current_id:
            grouped.append(current)
            current = []
        current.append(row)
        current_id = segment_id
    if current:
        grouped.append(current)
    return grouped


def _segment_type(segment: list[dict[str, object]]) -> str:
    for row in segment:
        value = str(row.get("segment_type", ""))
        if value:
            return value
    return "stroke"


def _mean(values: Iterable[float]) -> float:
    collected = list(values)
    return sum(collected) / len(collected) if collected else 0.0


def _execution_stats(rows: list[dict[str, object]]) -> dict[str, float]:
    connector_rows = [row for row in rows if str(row.get("segment_type")) == "connector"]
    stroke_rows = [row for row in rows if str(row.get("segment_type")) == "stroke"]
    return {
        "connector_mean_width": _mean(_to_float(row.get("width")) for row in connector_rows),
        "connector_mean_pressure": _mean(_to_float(row.get("pressure")) for row in connector_rows),
        "stroke_mean_width": _mean(_to_float(row.get("width")) for row in stroke_rows),
        "stroke_mean_pressure": _mean(_to_float(row.get("pressure")) for row in stroke_rows),
    }


def _ensure_plotting_available(out_path: Path, title: str) -> bool:
    if plt is not None:
        return True
    out_path.write_text(f"Plotting unavailable: {title}", encoding="utf-8")
    return False


def _setup_axis(ax, title: str) -> None:
    ax.set_title(title, fontsize=9)
    ax.set_xlim(0, 256)
    ax.set_ylim(256, 0)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, linewidth=0.25, alpha=0.25)
    ax.set_xticks([])
    ax.set_yticks([])


def _draw_segments(ax, rows: list[dict[str, object]], width_mode: bool = False) -> None:
    for segment in _group_segments(rows):
        xs = [_to_float(row.get("x")) for row in segment]
        ys = [_to_float(row.get("y")) for row in segment]
        if len(xs) < 2:
            continue
        seg_type = _segment_type(segment)
        if seg_type == "connector":
            color = "#e66101"
            linestyle = "-"
            alpha = max(0.35, min(0.85, _mean(_to_float(row.get("pressure")) for row in segment)))
            linewidth = (
                max(1.0, _mean(_to_float(row.get("width")) for row in segment) * 0.45)
                if width_mode
                else 2.2
            )
            zorder = 4
        elif seg_type == "pen_up_move":
            color = "#8c8c8c"
            linestyle = "--"
            alpha = 0.55
            linewidth = 1.4
            zorder = 2
        else:
            color = "#1f78b4" if width_mode else "#111111"
            linestyle = "-"
            alpha = 0.85
            linewidth = (
                max(1.0, _mean(_to_float(row.get("width")) for row in segment) * 0.35)
                if width_mode
                else 1.6
            )
            zorder = 3
        ax.plot(xs, ys, color=color, linestyle=linestyle, linewidth=linewidth, alpha=alpha, zorder=zorder)
        if seg_type == "connector":
            ax.scatter([xs[0], xs[-1]], [ys[0], ys[-1]], s=14, c=["#33a02c", "#b2df8a"], zorder=6)


def _write_segment_legend(path: Path) -> None:
    if not _ensure_plotting_available(path, "segment legend"):
        return
    fig, ax = plt.subplots(figsize=(6.2, 3.2), dpi=150)
    ax.axis("off")
    y_values = [0.75, 0.55, 0.35]
    labels = [
        ("stroke", "#1f78b4", "-", "normal pen-down stroke"),
        ("connector", "#e66101", "-", "inter-stroke connector: width/pressure encode weak vs normal"),
        ("pen_up_move", "#8c8c8c", "--", "pen-up travel; gray dashed and not drawn as ink"),
    ]
    for y, (name, color, linestyle, note) in zip(y_values, labels):
        ax.plot([0.08, 0.34], [y, y], color=color, linestyle=linestyle, linewidth=4)
        ax.text(0.38, y, f"{name}: {note}", va="center", fontsize=9)
    ax.text(
        0.08,
        0.12,
        "Earlier selected images used grayscale/ink rendering; gray lines can mix connector/transition cues.\n"
        "This diagnostic separates stroke, connector, and pen-up move explicitly.",
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_connector_overlay(row: dict[str, str], out_path: Path, warnings: list[str]) -> bool:
    rows = _read_execution_rows(_execution_path(row))
    if not rows:
        warnings.append(f"missing execution trajectory for {row.get('output_dir', '')}")
        return False
    if not _ensure_plotting_available(out_path, "connector overlay"):
        return True
    char = _normal_char(row)
    style = row.get("style", "")
    fig, ax = plt.subplots(figsize=(4.2, 4.2), dpi=160)
    _setup_axis(ax, f"u{ord(char):04x} {style}: connector overlay" if char else f"{style}: connector overlay")
    _draw_segments(ax, rows, width_mode=False)
    stats = _execution_stats(rows)
    text = (
        f"connection_count={row.get('connection_count', '')}\n"
        f"connector_draw_length={row.get('connector_draw_length', '')}\n"
        f"connector_width={row.get('connector_mean_width') or stats['connector_mean_width']:.3g}\n"
        f"connector_pressure={row.get('connector_mean_pressure') or stats['connector_mean_pressure']:.3g}"
    )
    ax.text(0.02, 0.02, text, transform=ax.transAxes, fontsize=7, va="bottom", ha="left")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return True


def _plot_width_diagnostic(row: dict[str, str], out_path: Path, warnings: list[str]) -> bool:
    rows = _read_execution_rows(_execution_path(row))
    if not rows:
        warnings.append(f"missing execution trajectory for brush diagnostic: {row.get('output_dir', '')}")
        return False
    if not _ensure_plotting_available(out_path, "brush width diagnostic"):
        return True
    stats = _execution_stats(rows)
    fig, axes = plt.subplots(1, 2, figsize=(8.2, 3.8), dpi=150)
    _setup_axis(axes[0], "execution width / pressure overlay")
    _draw_segments(axes[0], rows, width_mode=True)
    labels = ["stroke width", "connector width", "stroke pressure", "connector pressure"]
    values = [
        stats["stroke_mean_width"],
        stats["connector_mean_width"],
        stats["stroke_mean_pressure"],
        stats["connector_mean_pressure"],
    ]
    axes[1].bar(labels, values, color=["#1f78b4", "#e66101", "#6baed6", "#fdae6b"])
    axes[1].set_title("mean width / pressure")
    axes[1].tick_params(axis="x", rotation=25, labelsize=7)
    axes[1].grid(axis="y", linewidth=0.3, alpha=0.3)
    axes[1].text(
        0.02,
        0.95,
        "If a fixed ink render looks uniform,\ncheck width/pressure here.",
        transform=axes[1].transAxes,
        fontsize=8,
        va="top",
    )
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return True


def _plot_style_side_by_side(
    char: str,
    rows_by_key: dict[tuple[str, str], dict[str, str]],
    out_path: Path,
    warnings: list[str],
) -> bool:
    available = [rows_by_key.get((char, style)) for style in STYLES]
    if not any(available):
        warnings.append(f"missing side-by-side rows for {char}")
        return False
    if not _ensure_plotting_available(out_path, "style side by side"):
        return True
    fig, axes = plt.subplots(2, 3, figsize=(9, 5.8), dpi=150)
    for col, style in enumerate(STYLES):
        row = rows_by_key.get((char, style))
        for ax in axes[:, col]:
            ax.axis("off")
        if not row:
            axes[0, col].set_title(f"{style}: missing")
            continue
        rows = _read_execution_rows(_execution_path(row))
        if not rows:
            warnings.append(f"missing execution trajectory for {char}-{style}")
            axes[0, col].set_title(f"{style}: missing execution")
            continue
        label = f"u{ord(char):04x}" if char else "sample"
        _setup_axis(axes[0, col], f"{label} {style}: centerline")
        _draw_segments(axes[0, col], rows, width_mode=False)
        _setup_axis(axes[1, col], f"{label} {style}: width + connector")
        _draw_segments(axes[1, col], rows, width_mode=True)
        axes[1, col].text(
            0.02,
            0.02,
            f"aspect={row.get('aspect_ratio', '')}\nconn={row.get('connection_count', '')}",
            transform=axes[1, col].transAxes,
            fontsize=7,
            va="bottom",
        )
    fig.suptitle(f"u{ord(char):04x}: centerline vs execution/connector view", fontsize=11)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return True


def _plot_lishu_deformation(
    char: str,
    rows_by_key: dict[tuple[str, str], dict[str, str]],
    out_path: Path,
    warnings: list[str],
) -> bool:
    kaishu = rows_by_key.get((char, "kaishu"))
    lishu = rows_by_key.get((char, "lishu"))
    if not kaishu or not lishu:
        warnings.append(f"missing kaishu/lishu pair for deformation diagnostic: {char}")
        return False
    if not _ensure_plotting_available(out_path, "lishu deformation"):
        return True
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.8), dpi=150)
    for ax, row, style in zip(axes, (kaishu, lishu), ("kaishu", "lishu")):
        rows = _read_execution_rows(_execution_path(row))
        _setup_axis(ax, f"u{ord(char):04x} {style}")
        _draw_segments(ax, rows, width_mode=True)
        xs = [_to_float(item.get("x")) for item in rows]
        ys = [_to_float(item.get("y")) for item in rows]
        if xs and ys:
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            rect = plt.Rectangle(
                (min_x, min_y),
                max_x - min_x,
                max_y - min_y,
                fill=False,
                linestyle="--",
                edgecolor="#d62728",
                linewidth=1.0,
            )
            ax.add_patch(rect)
        ax.text(
            0.02,
            0.02,
            f"bbox={row.get('bbox_width', '')} x {row.get('bbox_height', '')}\n"
            f"aspect={row.get('aspect_ratio', '')}",
            transform=ax.transAxes,
            fontsize=7,
            va="bottom",
        )
    fig.suptitle("Lishu deformation check: global width/height scaling vs stroke-level style", fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    return True


def _case_row(
    row: dict[str, str],
    case_type: str,
    figure: Path | None,
    focus: str,
    rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    stats = _execution_stats(rows or [])
    return {
        "char": _normal_char(row),
        "style": row.get("style", ""),
        "case_type": case_type,
        "source_output_dir": row.get("output_dir", ""),
        "generated_figure": str(figure or ""),
        "connection_count": row.get("connection_count", ""),
        "connector_draw_length": row.get("connector_draw_length", ""),
        "connector_mean_width": row.get("connector_mean_width") or stats["connector_mean_width"],
        "connector_mean_pressure": row.get("connector_mean_pressure") or stats["connector_mean_pressure"],
        "mean_width": row.get("mean_width", ""),
        "aspect_ratio": row.get("aspect_ratio", ""),
        "diagnostic_focus": focus,
        "needs_user_review": "true",
    }


def _manifest_row(
    row: dict[str, str],
    figure_type: str,
    figure: Path | None,
    selected_copy: Path | None,
    warning: str = "",
) -> dict[str, object]:
    return {
        "char": _normal_char(row),
        "style": row.get("style", ""),
        "figure_type": figure_type,
        "source_output_dir": row.get("output_dir", ""),
        "source_image": str(_source_image(row) or ""),
        "generated_figure": str(figure or ""),
        "selected_case_copy": str(selected_copy or ""),
        "warning": warning,
    }


def _copy_selected(figure: Path | None, selected_dir: Path) -> Path | None:
    if not figure or not figure.exists():
        return None
    selected_dir.mkdir(parents=True, exist_ok=True)
    dest = selected_dir / figure.name
    shutil.copy2(figure, dest)
    return dest


def _candidate_rows(visual_audit_dir: Path) -> list[dict[str, str]]:
    candidates = _read_csv(visual_audit_dir / "visual_audit_candidates.csv")
    return [row for row in candidates if row.get("style")]


def _diagnostic_rows(diagnostic_dir: Path) -> list[dict[str, str]]:
    rows = _read_csv(diagnostic_dir / "style_diagnostic_summary.csv")
    return [row for row in rows if _to_bool(row.get("success", "True"))]


def _find_row(
    rows_by_key: dict[tuple[str, str], dict[str, str]],
    candidates: list[dict[str, str]],
    char: str,
    style: str,
    case_type: str | None = None,
) -> dict[str, str] | None:
    for row in candidates:
        if _normal_char(row) == char and row.get("style") == style:
            if case_type is None or row.get("case_type") == case_type:
                return row
    return rows_by_key.get((char, style))


def _write_report(
    path: Path,
    visual_audit_dir: Path,
    diagnostic_dir: Path,
    output_dir: Path,
    cases: list[dict[str, object]],
    warnings: list[str],
) -> None:
    case_counts = Counter(str(row.get("case_type", "")) for row in cases)
    lines = [
        "# Connector / Brush Visual Diagnostics",
        "",
        "## Purpose",
        "",
        "本轮从上一轮 visual audit 进入更细的 connector / brush 可视化诊断。"
        "目标是把 stroke、connector、pen_up_move、width、pressure 拆开看清楚，为人工看图提供依据。",
        "",
        "边界：本轮不调参数、不改 planner、不扩大样本、不调用 API、不连接 CoppeliaSim 或 AUBO i5。"
        "不能只看指标，本报告只准备图包和诊断线索，最终视觉判断仍需人工校验。",
        "",
        "## Inputs",
        "",
        f"- visual_audit_dir: `{visual_audit_dir}`",
        f"- diagnostic_dir: `{diagnostic_dir}`",
        f"- output_dir: `{output_dir}`",
        "",
        "## What The Figures Show",
        "",
        "- `segment_legend.png`: 说明 stroke / connector / pen_up_move 的颜色和线型。",
        "- `connector_overlay_*`: 用红/橙色突出 xingkai connector，灰色虚线只表示 pen-up move。",
        "- `style_side_by_side_*`: 对同一字展示 centerline、execution width、connector 高亮视图。",
        "- `lishu_deformation_*`: 对比 kaishu 与 lishu 的 bbox / aspect，检查是否主要是整体拉宽压扁。",
        "- `brush_width_diagnostic_*`: 对比 stroke 与 connector 的 width / pressure，检查普通渲染是否隐藏差异。",
        "",
        "## Answers To Current Visual Questions",
        "",
        "1. 灰线是什么？在旧的 selected_images 中，灰线/浅线可能来自渲染透明度、connector 过渡或 pen-up/transition 可视化混在一起；新图中灰色虚线只表示 `pen_up_move`，红/橙色才表示 connector。",
        "2. 为什么宽度看起来都一样？之前的固定渲染更偏最终墨迹预览，connector 的低 pressure / 小 width 可能被抗锯齿、透明度和整体缩放吞掉；本图包单独画 width/pressure 才能看到执行层差异。",
        "3. 为什么 lishu 像横向拉伸？当前 lishu 的可见差异主要来自 horizontal/vertical scale 和笔宽，stroke-level 的蚕头燕尾、波磔等隶书特征还不足，所以需要人工确认是否只是全局变形。",
        "4. xingkai connector 是否太多？指标显示部分复杂字 connector_draw_length 较长，本轮重点给出 `国/德/福` overlay；是否过多、是否自然必须看图判断。",
        "5. 为什么需要新可视化？因为中心线和固定墨迹图无法明确区分 connector、pen-up move、width 和 pressure。调参前先把执行层证据分离，避免只凭数值误判。",
        "",
        "## Case Counts",
        "",
        "| case_type | count |",
        "|---|---:|",
    ]
    for case_type, count in sorted(case_counts.items()):
        lines.append(f"| `{case_type}` | {count} |")
    lines.extend(
        [
            "",
            "## Generated Cases",
            "",
            "| char | style | case_type | figure | focus |",
            "|---|---|---|---|---|",
        ]
    )
    for row in cases:
        lines.append(
            f"| {row.get('char', '')} | {row.get('style', '')} | `{row.get('case_type', '')}` | "
            f"`{row.get('generated_figure', '')}` | {row.get('diagnostic_focus', '')} |"
        )
    lines.extend(
        [
            "",
            "## Manual Review Guidance",
            "",
            "请优先人工看图：",
            "- `国/德/福` 的 xingkai connector 是否过长、过直或穿越部件。",
            "- `人/好/风` 的 lishu 是否只是横向拉宽、纵向压缩，而缺少真实隶书笔画特征。",
            "- `人/中/和` 的三风格是否肉眼能区分，还是只在指标上有差异。",
            "- brush width diagnostic 中 connector 是否确实比 stroke 更细、更低压。",
            "",
            "本轮不调参数。等用户人工看图反馈后，再决定是否调整 style profile、modifier 或 brush mapping。",
        ]
    )
    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            lines.append(f"- {warning}")
    path.write_text("\n".join(lines), encoding="utf-8")


def _copy_to_paper_figures(result: dict[str, object], paper_dir: Path = DEFAULT_PAPER_DIR) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    outputs = result["outputs"]  # type: ignore[index]
    for key in ("report_md", "cases_csv"):
        source = Path(outputs[key])  # type: ignore[index]
        if source.exists():
            shutil.copy2(source, paper_dir / source.name)
    representative: list[Path] = []
    for path in sorted(Path(outputs["figures_dir"]).glob("*.png")):  # type: ignore[index]
        if path.name == "segment_legend.png" or "connector_overlay" in path.name or "brush_width" in path.name:
            representative.append(path)
        if len(representative) >= 4:
            break
    copied_names = []
    for source in representative:
        dest = paper_dir / f"connector_brush_{source.name}"
        shutil.copy2(source, dest)
        copied_names.append(dest.name)
    index = paper_dir / "connector_brush_visual_diagnostics_index.md"
    index.write_text(
        "\n".join(
            [
                "# Connector / Brush Visual Diagnostics Index",
                "",
                f"- source_output_dir: `{result['output_dir']}`",
                "- scope: visual diagnostics only; no parameter tuning, no API, no CoppeliaSim, no robot SDK.",
                "",
                "| File | Content |",
                "|---|---|",
                "| `connector_brush_diagnostic_report.md` | connector/brush visual diagnostic report |",
                "| `connector_brush_diagnostic_cases.csv` | selected cases and metrics |",
                *[f"| `{name}` | representative diagnostic figure |" for name in copied_names],
                "",
                "人工看图仍是必要步骤；不能只看指标判断最终风格效果。",
            ]
        ),
        encoding="utf-8",
    )
    return index


def run_connector_brush_diagnostics(
    visual_audit_dir: Path = DEFAULT_VISUAL_AUDIT_DIR,
    diagnostic_dir: Path = DEFAULT_DIAGNOSTIC_DIR,
    output_dir: Path | None = None,
    copy_to_paper: bool = True,
) -> dict[str, object]:
    visual_audit_dir = Path(visual_audit_dir)
    diagnostic_dir = Path(diagnostic_dir)
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = diagnostic_dir.parent / f"connector_brush_visual_diagnostics_{timestamp}"
    output_dir = Path(output_dir)
    figures_dir = output_dir / "figures"
    selected_dir = output_dir / "selected_cases"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    selected_dir.mkdir(parents=True, exist_ok=True)

    candidates = _candidate_rows(visual_audit_dir)
    diagnostic_rows = _diagnostic_rows(diagnostic_dir)
    rows_by_key = {_sample_key(row): row for row in diagnostic_rows}
    for row in candidates:
        key = _sample_key(row)
        rows_by_key.setdefault(key, row)

    warnings: list[str] = []
    cases: list[dict[str, object]] = []
    manifest: list[dict[str, object]] = []

    for row in candidates:
        candidate_output_dir = _row_output_dir(row)
        if candidate_output_dir and not candidate_output_dir.exists():
            warning = (
                f"missing output_dir for candidate {_normal_char(row)}-{row.get('style', '')}: "
                f"{candidate_output_dir}"
            )
            warnings.append(warning)
            manifest.append(_manifest_row(row, "candidate_input", None, None, warning))
            continue
        execution_path = _execution_path(row)
        if candidate_output_dir and not execution_path.exists():
            warning = f"missing execution trajectory for candidate {_normal_char(row)}-{row.get('style', '')}: {execution_path}"
            warnings.append(warning)
            manifest.append(_manifest_row(row, "candidate_input", None, None, warning))

    legend = figures_dir / "segment_legend.png"
    _write_segment_legend(legend)
    selected_legend = _copy_selected(legend, selected_dir)
    manifest.append(
        {
            "char": "",
            "style": "",
            "figure_type": "segment_legend",
            "source_output_dir": "",
            "source_image": "",
            "generated_figure": str(legend),
            "selected_case_copy": str(selected_legend or ""),
            "warning": "",
        }
    )

    for char in CONNECTOR_CHARS:
        row = _find_row(rows_by_key, candidates, char, "xingkai")
        if not row:
            warnings.append(f"missing connector case for {char}-xingkai")
            continue
        figure = figures_dir / f"connector_overlay_u{ord(char):04x}_xingkai.png"
        ok = _plot_connector_overlay(row, figure, warnings)
        selected = _copy_selected(figure if ok else None, selected_dir)
        rows = _read_execution_rows(_execution_path(row))
        cases.append(
            _case_row(
                row,
                row.get("case_type") or "long_xingkai_connector",
                figure if ok else None,
                "Check whether xingkai connector is too long, too straight, or crossing components.",
                rows,
            )
        )
        manifest.append(_manifest_row(row, "connector_overlay", figure if ok else None, selected))

    brush_row = next(
        (
            row
            for row in candidates
            if row.get("style") == "xingkai" and _to_float(row.get("connector_draw_length")) > 0
        ),
        None,
    ) or _find_row(rows_by_key, candidates, "国", "xingkai")
    if brush_row:
        char = _normal_char(brush_row) or "sample"
        figure = figures_dir / f"brush_width_diagnostic_u{ord(char):04x}_xingkai.png"
        ok = _plot_width_diagnostic(brush_row, figure, warnings)
        selected = _copy_selected(figure if ok else None, selected_dir)
        rows = _read_execution_rows(_execution_path(brush_row))
        cases.append(
            _case_row(
                brush_row,
                "brush_width_diagnostic",
                figure if ok else None,
                "Compare stroke and connector width/pressure; check whether fixed render hides differences.",
                rows,
            )
        )
        manifest.append(_manifest_row(brush_row, "brush_width_diagnostic", figure if ok else None, selected))

    for char in SIDE_BY_SIDE_CHARS:
        figure = figures_dir / f"style_side_by_side_u{ord(char):04x}.png"
        ok = _plot_style_side_by_side(char, rows_by_key, figure, warnings)
        selected = _copy_selected(figure if ok else None, selected_dir)
        for style in STYLES:
            row = rows_by_key.get((char, style))
            if not row:
                continue
            rows = _read_execution_rows(_execution_path(row))
            cases.append(
                _case_row(
                    row,
                    "style_side_by_side",
                    figure if ok else None,
                    "Compare centerline, execution width, and connector-highlighted visual difference across styles.",
                    rows,
                )
            )
            manifest.append(_manifest_row(row, "style_side_by_side", figure if ok else None, selected))

    for char in LISHU_DEFORMATION_CHARS:
        figure = figures_dir / f"lishu_deformation_u{ord(char):04x}.png"
        ok = _plot_lishu_deformation(char, rows_by_key, figure, warnings)
        selected = _copy_selected(figure if ok else None, selected_dir)
        for style in ("kaishu", "lishu"):
            row = rows_by_key.get((char, style))
            if not row:
                continue
            rows = _read_execution_rows(_execution_path(row))
            cases.append(
                _case_row(
                    row,
                    "lishu_deformation",
                    figure if ok else None,
                    "Check whether lishu is mainly global horizontal widening / vertical compression.",
                    rows,
                )
            )
            manifest.append(_manifest_row(row, "lishu_deformation", figure if ok else None, selected))

    cases_csv = output_dir / "connector_brush_diagnostic_cases.csv"
    manifest_csv = output_dir / "connector_brush_image_manifest.csv"
    report_md = output_dir / "connector_brush_diagnostic_report.md"
    metrics_json = output_dir / "connector_brush_diagnostic_metrics.json"

    _write_csv(cases_csv, CASE_FIELDS, cases)
    _write_csv(manifest_csv, MANIFEST_FIELDS, manifest)
    _write_report(report_md, visual_audit_dir, diagnostic_dir, output_dir, cases, warnings)
    metrics = {
        "output_dir": str(output_dir),
        "case_count": len(cases),
        "figure_count": len(list(figures_dir.glob("*.png"))),
        "case_type_counts": dict(Counter(str(row.get("case_type", "")) for row in cases)),
        "warnings": warnings,
        "scope": "connector/brush visual diagnostics only; no parameter tuning, no API, no CoppeliaSim, no robot SDK",
    }
    metrics_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    paper_index = None
    if copy_to_paper:
        paper_index = _copy_to_paper_figures(
            {
                "output_dir": str(output_dir),
                "outputs": {
                    "report_md": report_md,
                    "cases_csv": cases_csv,
                    "figures_dir": figures_dir,
                },
            }
        )

    return {
        **metrics,
        "outputs": {
            "report_md": report_md,
            "cases_csv": cases_csv,
            "manifest_csv": manifest_csv,
            "metrics_json": metrics_json,
            "figures_dir": figures_dir,
            "selected_cases_dir": selected_dir,
            "segment_legend_png": legend,
            "paper_index": paper_index,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build connector/brush visual diagnostic package.")
    parser.add_argument("--visual-audit-dir", type=Path, default=DEFAULT_VISUAL_AUDIT_DIR)
    parser.add_argument("--diagnostic-dir", type=Path, default=DEFAULT_DIAGNOSTIC_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args()
    result = run_connector_brush_diagnostics(
        visual_audit_dir=args.visual_audit_dir,
        diagnostic_dir=args.diagnostic_dir,
        output_dir=args.out_dir,
        copy_to_paper=not args.no_copy_to_paper,
    )
    printable = {
        "output_dir": result["output_dir"],
        "case_count": result["case_count"],
        "figure_count": result["figure_count"],
        "case_type_counts": result["case_type_counts"],
        "report_md": str(result["outputs"]["report_md"]),  # type: ignore[index]
        "cases_csv": str(result["outputs"]["cases_csv"]),  # type: ignore[index]
        "manifest_csv": str(result["outputs"]["manifest_csv"]),  # type: ignore[index]
        "paper_index": str(result["outputs"]["paper_index"] or ""),  # type: ignore[index]
        "warnings": result["warnings"],
    }
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
