from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb
    from matplotlib.cm import ScalarMappable
except Exception:  # pragma: no cover - plotting dependency fallback
    plt = None
    LineCollection = None
    LinearSegmentedColormap = None
    Normalize = None
    to_rgb = None
    ScalarMappable = None


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES_CSV = (
    ROOT
    / "experiments"
    / "llm_style_trajectory"
    / "outputs"
    / "connector_brush_visual_diagnostics_20260618_093510"
    / "connector_brush_diagnostic_cases.csv"
)
DEFAULT_PAPER_DIR = ROOT / "experiments" / "llm_style_trajectory" / "outputs" / "paper_figures"

NUMERIC_FIELDS = {
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
}

MANIFEST_FIELDS = [
    "char",
    "style",
    "source_execution_csv",
    "figure_path",
    "value_mode",
    "normalization",
    "stroke_width_min",
    "stroke_width_max",
    "connector_width_min",
    "connector_width_max",
    "stroke_pressure_min",
    "stroke_pressure_max",
    "connector_pressure_min",
    "connector_pressure_max",
    "stroke_width_nearly_constant",
    "connector_width_nearly_constant",
    "needs_user_review",
]

DEFAULT_BACKGROUND_COLOR = "#f7f7f2"
DEFAULT_STROKE_LIGHT_COLOR = "#6baed6"
DEFAULT_STROKE_DARK_COLOR = "#08306b"
DEFAULT_CONNECTOR_LIGHT_COLOR = "#b07d62"
DEFAULT_CONNECTOR_DARK_COLOR = "#5a2a1a"
DEFAULT_PEN_UP_COLOR = "#bdbdbd"
DEFAULT_MIN_ALPHA = 0.55
DEFAULT_MIN_VISIBLE_LINEWIDTH = 1.2


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


def _sample_char_from_output_dir(path: str) -> str:
    match = re.match(r"u([0-9a-fA-F]{4,6})_", Path(path).name)
    if not match:
        return ""
    try:
        return chr(int(match.group(1), 16))
    except ValueError:
        return ""


def _case_char(row: dict[str, str]) -> str:
    return _sample_char_from_output_dir(row.get("source_output_dir", "")) or row.get("char", "")


def _execution_csv_for_case(row: dict[str, str]) -> Path:
    source_dir = Path(row.get("source_output_dir", ""))
    return source_dir / "execution_trajectory.csv"


def _read_execution_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            parsed: dict[str, object] = {}
            for key, value in row.items():
                parsed[key] = _to_float(value) if key in NUMERIC_FIELDS else value
            rows.append(parsed)
    return rows


def _group_segments(rows: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    groups: list[list[dict[str, object]]] = []
    current_id: object = None
    current: list[dict[str, object]] = []
    for row in rows:
        segment_id = row.get("segment_id")
        if current and segment_id != current_id:
            groups.append(current)
            current = []
        current.append(row)
        current_id = segment_id
    if current:
        groups.append(current)
    return groups


def _values(rows: Iterable[dict[str, object]], segment_type: str, field: str) -> list[float]:
    return [
        _to_float(row.get(field))
        for row in rows
        if str(row.get("segment_type")) == segment_type and int(_to_float(row.get("pen_down"))) == 1
    ]


def _range(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    return min(values), max(values)


def _nearly_constant(values: list[float], eps: float = 1e-6) -> bool:
    if len(values) <= 1:
        return bool(values)
    return max(values) - min(values) <= eps


def _sample_stats(rows: list[dict[str, object]]) -> dict[str, object]:
    stroke_widths = _values(rows, "stroke", "width")
    connector_widths = _values(rows, "connector", "width")
    stroke_pressures = _values(rows, "stroke", "pressure")
    connector_pressures = _values(rows, "connector", "pressure")
    sw_min, sw_max = _range(stroke_widths)
    cw_min, cw_max = _range(connector_widths)
    sp_min, sp_max = _range(stroke_pressures)
    cp_min, cp_max = _range(connector_pressures)
    return {
        "stroke_width_min": sw_min,
        "stroke_width_max": sw_max,
        "connector_width_min": cw_min,
        "connector_width_max": cw_max,
        "stroke_pressure_min": sp_min,
        "stroke_pressure_max": sp_max,
        "connector_pressure_min": cp_min,
        "connector_pressure_max": cp_max,
        "stroke_width_nearly_constant": _nearly_constant(stroke_widths),
        "connector_width_nearly_constant": _nearly_constant(connector_widths),
        "connector_thinner_than_stroke": bool(connector_widths and stroke_widths and max(connector_widths) < min(stroke_widths)),
        "connector_lower_pressure_than_stroke": bool(
            connector_pressures and stroke_pressures and max(connector_pressures) < min(stroke_pressures)
        ),
    }


def _finite(values: Iterable[float | None]) -> list[float]:
    return [float(value) for value in values if value is not None and not math.isnan(float(value))]


def _global_ranges(samples: list[dict[str, object]]) -> dict[str, object]:
    rows_by_style: dict[str, list[dict[str, object]]] = defaultdict(list)
    rows_by_segment: dict[str, list[dict[str, object]]] = defaultdict(list)
    all_rows: list[dict[str, object]] = []
    for sample in samples:
        rows = sample["rows"]  # type: ignore[index]
        all_rows.extend(rows)
        for row in rows:
            rows_by_style[str(sample["style"])].append(row)
            rows_by_segment[str(row.get("segment_type"))].append(row)

    width_values = [
        _to_float(row.get("width"))
        for row in all_rows
        if int(_to_float(row.get("pen_down"))) == 1 and str(row.get("segment_type")) != "pen_up_move"
    ]
    pressure_values = [
        _to_float(row.get("pressure"))
        for row in all_rows
        if int(_to_float(row.get("pen_down"))) == 1 and str(row.get("segment_type")) != "pen_up_move"
    ]
    width_min, width_max = _range(width_values)
    pressure_min, pressure_max = _range(pressure_values)
    result: dict[str, object] = {
        "global_width_min": width_min,
        "global_width_max": width_max,
        "global_pressure_min": pressure_min,
        "global_pressure_max": pressure_max,
        "per_style": {},
        "per_segment_type": {},
    }
    per_style: dict[str, dict[str, float | None]] = {}
    for style, rows in rows_by_style.items():
        per_style[style] = {
            "width_min": _range([_to_float(row.get("width")) for row in rows if int(_to_float(row.get("pen_down"))) == 1])[0],
            "width_max": _range([_to_float(row.get("width")) for row in rows if int(_to_float(row.get("pen_down"))) == 1])[1],
            "pressure_min": _range([_to_float(row.get("pressure")) for row in rows if int(_to_float(row.get("pen_down"))) == 1])[0],
            "pressure_max": _range([_to_float(row.get("pressure")) for row in rows if int(_to_float(row.get("pen_down"))) == 1])[1],
        }
    per_segment: dict[str, dict[str, float | None]] = {}
    for segment_type, rows in rows_by_segment.items():
        per_segment[segment_type] = {
            "width_min": _range([_to_float(row.get("width")) for row in rows])[0],
            "width_max": _range([_to_float(row.get("width")) for row in rows])[1],
            "pressure_min": _range([_to_float(row.get("pressure")) for row in rows])[0],
            "pressure_max": _range([_to_float(row.get("pressure")) for row in rows])[1],
        }
    result["per_style"] = per_style
    result["per_segment_type"] = per_segment
    return result


def _mode_list(mode: str) -> list[str]:
    if mode == "both":
        return ["width", "pressure"]
    return [mode]


def _norm_list(normalization: str) -> list[str]:
    if normalization == "both":
        return ["global", "per-image"]
    return [normalization]


def _expand_range(min_value: float | None, max_value: float | None) -> tuple[float, float]:
    if min_value is None or max_value is None:
        return 0.0, 1.0
    if abs(max_value - min_value) < 1e-9:
        pad = max(0.5, abs(max_value) * 0.05)
        return min_value - pad, max_value + pad
    return min_value, max_value


def _hex_distance_from_white(color: str) -> float:
    if to_rgb is None:
        return 0.0
    r, g, b = to_rgb(color)
    return math.sqrt((1.0 - r) ** 2 + (1.0 - g) ** 2 + (1.0 - b) ** 2)


def visual_color_diagnostics(
    *,
    background_color: str = DEFAULT_BACKGROUND_COLOR,
    stroke_light_color: str = DEFAULT_STROKE_LIGHT_COLOR,
    connector_light_color: str = DEFAULT_CONNECTOR_LIGHT_COLOR,
    min_alpha: float = DEFAULT_MIN_ALPHA,
    min_visible_linewidth: float = DEFAULT_MIN_VISIBLE_LINEWIDTH,
) -> dict[str, object]:
    return {
        "background_color": background_color,
        "stroke_light_color": stroke_light_color,
        "connector_light_color": connector_light_color,
        "stroke_light_distance_from_white": round(_hex_distance_from_white(stroke_light_color), 6),
        "connector_light_distance_from_white": round(_hex_distance_from_white(connector_light_color), 6),
        "background_distance_from_white": round(_hex_distance_from_white(background_color), 6),
        "min_alpha": float(min_alpha),
        "min_visible_linewidth": float(min_visible_linewidth),
    }


def _build_cmap(name: str, light_color: str, dark_color: str):
    if plt is None or LinearSegmentedColormap is None:
        return None
    if name not in {"blue", "gray", "orange-gray", "custom"} and not name.startswith("#"):
        try:
            return plt.get_cmap(name)
        except ValueError:
            pass
    return LinearSegmentedColormap.from_list(f"{light_color}_{dark_color}", [light_color, dark_color])


def _line_color(
    segment_type: str,
    value: float,
    norm,
    stroke_cmap: str,
    connector_cmap: str,
    stroke_light_color: str,
    stroke_dark_color: str,
    connector_light_color: str,
    connector_dark_color: str,
):
    if plt is None:
        return "#111111"
    if segment_type == "connector":
        cmap = _build_cmap(connector_cmap, connector_light_color, connector_dark_color)
    else:
        cmap = _build_cmap(stroke_cmap, stroke_light_color, stroke_dark_color)
    return cmap(norm(value))


def render_width_pressure_figure(
    rows: list[dict[str, object]],
    out_path: Path,
    *,
    value_mode: str,
    normalization: str,
    value_range: tuple[float, float],
    title: str,
    stroke_cmap: str = "blue",
    connector_cmap: str = "gray",
    background_color: str = DEFAULT_BACKGROUND_COLOR,
    stroke_light_color: str = DEFAULT_STROKE_LIGHT_COLOR,
    stroke_dark_color: str = DEFAULT_STROKE_DARK_COLOR,
    connector_light_color: str = DEFAULT_CONNECTOR_LIGHT_COLOR,
    connector_dark_color: str = DEFAULT_CONNECTOR_DARK_COLOR,
    pen_up_color: str = DEFAULT_PEN_UP_COLOR,
    min_alpha: float = DEFAULT_MIN_ALPHA,
    min_visible_linewidth: float = DEFAULT_MIN_VISIBLE_LINEWIDTH,
    draw_pen_up: bool = False,
    image_size: int = 256,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if plt is None or LineCollection is None or Normalize is None or ScalarMappable is None:
        out_path.write_text("matplotlib unavailable", encoding="utf-8")
        return
    norm = Normalize(vmin=value_range[0], vmax=value_range[1])
    fig, ax = plt.subplots(figsize=(4.4, 4.4), dpi=160)
    fig.patch.set_facecolor(background_color)
    ax.set_facecolor(background_color)
    ax.set_xlim(0, image_size)
    ax.set_ylim(image_size, 0)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title(title, fontsize=8)
    ax.grid(True, linewidth=0.25, alpha=0.25)
    ax.set_xticks([])
    ax.set_yticks([])

    for group in _group_segments(rows):
        if len(group) < 2:
            continue
        segment_type = str(group[0].get("segment_type", "stroke"))
        if segment_type == "pen_up_move" and not draw_pen_up:
            continue
        points = [(float(row["x"]), float(row["y"])) for row in group]
        for left, right in zip(group, group[1:]):
            x0, y0 = float(left["x"]), float(left["y"])
            x1, y1 = float(right["x"]), float(right["y"])
            if segment_type == "pen_up_move":
                ax.plot(
                    [x0, x1],
                    [y0, y1],
                    color=pen_up_color,
                    linewidth=max(0.8, min_visible_linewidth * 0.7),
                    linestyle="--",
                    alpha=max(0.35, min_alpha * 0.7),
                )
                continue
            value = (_to_float(left.get(value_mode)) + _to_float(right.get(value_mode))) / 2.0
            width = (_to_float(left.get("width")) + _to_float(right.get("width"))) / 2.0
            pressure = (_to_float(left.get("pressure")) + _to_float(right.get("pressure"))) / 2.0
            color = _line_color(
                segment_type,
                value,
                norm,
                stroke_cmap,
                connector_cmap,
                stroke_light_color,
                stroke_dark_color,
                connector_light_color,
                connector_dark_color,
            )
            linewidth = max(min_visible_linewidth, min(6.0, width * 0.35))
            alpha = max(min_alpha, min(1.0, 0.45 + pressure * 0.55))
            ax.plot([x0, x1], [y0, y1], color=color, linewidth=linewidth, alpha=alpha, solid_capstyle="round")

    proxy_cmap = _build_cmap(stroke_cmap, stroke_light_color, stroke_dark_color)
    cbar = fig.colorbar(ScalarMappable(norm=norm, cmap=proxy_cmap), ax=ax, fraction=0.046, pad=0.03)
    cbar.ax.tick_params(labelsize=6)
    cbar.set_label(f"{value_mode} ({normalization})", fontsize=7)
    ax.text(
        0.02,
        0.02,
        "stroke=blue scale\nconnector=brown/orange scale\npen-up hidden unless requested",
        transform=ax.transAxes,
        fontsize=6.5,
        va="bottom",
        bbox={"facecolor": background_color, "alpha": 0.86, "edgecolor": "none"},
    )
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _case_id(char: str, style: str) -> str:
    if char:
        return f"u{ord(char):04x}_{style}"
    return f"sample_{style}"


def _manifest_row(
    *,
    sample: dict[str, object],
    figure_path: Path,
    value_mode: str,
    normalization: str,
    stats: dict[str, object],
) -> dict[str, object]:
    def fmt(value: object) -> str:
        return "" if value is None else str(value)

    return {
        "char": sample["char"],
        "style": sample["style"],
        "source_execution_csv": sample["execution_csv"],
        "figure_path": str(figure_path),
        "value_mode": value_mode,
        "normalization": normalization,
        "stroke_width_min": fmt(stats["stroke_width_min"]),
        "stroke_width_max": fmt(stats["stroke_width_max"]),
        "connector_width_min": fmt(stats["connector_width_min"]),
        "connector_width_max": fmt(stats["connector_width_max"]),
        "stroke_pressure_min": fmt(stats["stroke_pressure_min"]),
        "stroke_pressure_max": fmt(stats["stroke_pressure_max"]),
        "connector_pressure_min": fmt(stats["connector_pressure_min"]),
        "connector_pressure_max": fmt(stats["connector_pressure_max"]),
        "stroke_width_nearly_constant": str(bool(stats["stroke_width_nearly_constant"])).lower(),
        "connector_width_nearly_constant": str(bool(stats["connector_width_nearly_constant"])).lower()
        if stats["connector_width_min"] is not None
        else "",
        "needs_user_review": "true",
    }


def _load_samples(cases_csv: Path, max_cases: int | None) -> tuple[list[dict[str, object]], list[str]]:
    warnings: list[str] = []
    samples: list[dict[str, object]] = []
    seen: set[tuple[Path, str]] = set()
    for row in _read_csv(cases_csv):
        execution_csv = _execution_csv_for_case(row)
        style = row.get("style", "")
        key = (execution_csv, style)
        if key in seen:
            continue
        seen.add(key)
        rows = _read_execution_rows(execution_csv)
        if not rows:
            warnings.append(f"missing or empty execution trajectory: {execution_csv}")
            continue
        char = _case_char(row)
        samples.append(
            {
                "char": char,
                "style": style,
                "case_type": row.get("case_type", ""),
                "source_output_dir": row.get("source_output_dir", ""),
                "execution_csv": str(execution_csv),
                "rows": rows,
                "stats": _sample_stats(rows),
            }
        )
        if max_cases is not None and len(samples) >= max_cases:
            break
    return samples, warnings


def _write_report(
    path: Path,
    *,
    cases_csv: Path,
    samples: list[dict[str, object]],
    manifest_rows: list[dict[str, object]],
    ranges: dict[str, object],
    visual_settings: dict[str, object],
    warnings: list[str],
) -> None:
    connector_thinner = [
        sample for sample in samples if bool(sample["stats"]["connector_thinner_than_stroke"])  # type: ignore[index]
    ]
    connector_lower_pressure = [
        sample for sample in samples if bool(sample["stats"]["connector_lower_pressure_than_stroke"])  # type: ignore[index]
    ]
    constant_stroke = [
        sample for sample in samples if bool(sample["stats"]["stroke_width_nearly_constant"])  # type: ignore[index]
    ]
    mode_counts = Counter(row["value_mode"] for row in manifest_rows)
    norm_counts = Counter(row["normalization"] for row in manifest_rows)

    def label(sample: dict[str, object]) -> str:
        char = str(sample["char"])
        style = str(sample["style"])
        char_id = f"u{ord(char):04x}" if char else "sample"
        return f"{char_id}/{style}"

    lines = [
        "# 宽度 / 压力渐变可视化诊断",
        "",
        "## 本轮目的",
        "",
        "本轮用颜色深浅和适度线宽显示 `execution_trajectory.csv` 中的 `width` / `pressure`。"
        "目标是让人工看图时能直观看到主体 stroke 与 connector 的粗细、压力差异。",
        "",
        "本轮不调参数，不修改 `execution_trajectory.csv`，不改 planner，不调用 API，不连接 CoppeliaSim 或机器人接口。"
        "这些图不是最终书法效果图，只是执行层诊断图；不能只看指标，仍需要人工看图。",
        "",
        "## 输入与输出",
        "",
        f"- cases_csv: `{cases_csv}`",
        f"- sample_count: `{len(samples)}`",
        f"- generated_figure_count: `{len(manifest_rows)}`",
        "",
        "## global normalization 与 per-image normalization",
        "",
        "- `global`：所有样本共用同一组 width/pressure 范围，适合跨字、跨风格比较。",
        "- `per-image`：每张图内部独立归一化，适合观察单个样本内部是否有细微变化。",
        "",
        "## 全局范围",
        "",
        f"- global_width_min/max: `{ranges.get('global_width_min')}` / `{ranges.get('global_width_max')}`",
        f"- global_pressure_min/max: `{ranges.get('global_pressure_min')}` / `{ranges.get('global_pressure_max')}`",
        "",
        "## 可视化颜色设置",
        "",
        "本轮颜色只为可读性，不代表真实墨色或真实笔刷浓淡。浅色端不再使用接近白色的颜色，避免 connector 在浅色背景上消失。",
        "",
        f"- background_color: `{visual_settings.get('background_color')}`",
        f"- stroke_light_color: `{visual_settings.get('stroke_light_color')}`",
        f"- connector_light_color: `{visual_settings.get('connector_light_color')}`",
        f"- stroke_light_distance_from_white: `{visual_settings.get('stroke_light_distance_from_white')}`",
        f"- connector_light_distance_from_white: `{visual_settings.get('connector_light_distance_from_white')}`",
        f"- min_alpha: `{visual_settings.get('min_alpha')}`",
        f"- min_visible_linewidth: `{visual_settings.get('min_visible_linewidth')}`",
        "",
        "## 输出统计",
        "",
        f"- value_mode_counts: `{dict(mode_counts)}`",
        f"- normalization_counts: `{dict(norm_counts)}`",
        "",
        "## 初步观察",
        "",
        f"- connector 明显更细的样本数：`{len(connector_thinner)}`。样本：`{', '.join(label(s) for s in connector_thinner[:12])}`",
        f"- connector 明显更低压的样本数：`{len(connector_lower_pressure)}`。样本：`{', '.join(label(s) for s in connector_lower_pressure[:12])}`",
        f"- stroke width nearly constant 的样本数：`{len(constant_stroke)}`。样本：`{', '.join(label(s) for s in constant_stroke[:12])}`",
        "",
        "如果某个样本的主体笔画整段颜色差不多，说明当前数据中的 stroke 内部宽度/压力变化不足；这不是可视化失败，而是 execution 数据本身变化较少。",
        "旧 selected_images 之所以肉眼看不出粗细差异，主要是因为固定墨迹渲染会把低压、细线、透明度和抗锯齿效果混在一起。",
        "",
        "## 人工看图说明",
        "",
        "建议先看 `global width` 图判断跨样本粗细差异，再看 `per-image width` 图判断单个样本内部变化；"
        "随后看 pressure 图判断 connector 是否低压。不要把颜色深浅当作最终书法视觉效果，它只是诊断编码。",
        "",
        "## 边界",
        "",
        "- 本轮不调参数。",
        "- 本轮不修改 `execution_trajectory.csv`。",
        "- 本轮不代表真实笔刷模型。",
        "- 本轮不调用 API，不连接 CoppeliaSim，不连接 AUBO i5，不调用 SDK，不发送机器人命令。",
    ]
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    path.write_text("\n".join(lines), encoding="utf-8")


def _copy_to_paper_figures(result: dict[str, object], paper_dir: Path = DEFAULT_PAPER_DIR) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    outputs = result["outputs"]  # type: ignore[index]
    for key in ("report_md", "manifest_csv"):
        source = Path(outputs[key])  # type: ignore[index]
        if source.exists():
            shutil.copy2(source, paper_dir / source.name)
    figures_dir = Path(outputs["figures_dir"])  # type: ignore[index]
    preferred_names = [
        "width_global_u56fd_xingkai.png",
        "pressure_global_u56fd_xingkai.png",
        "width_per_image_u56fd_xingkai.png",
        "width_global_u4eba_xingkai.png",
    ]
    preferred = [figures_dir / name for name in preferred_names if (figures_dir / name).exists()]
    fallback = [path for path in sorted(figures_dir.glob("*.png")) if path not in preferred]
    copied: list[str] = []
    for source in (preferred + fallback)[:4]:
        dest = paper_dir / f"width_pressure_{source.name}"
        shutil.copy2(source, dest)
        copied.append(dest.name)
    index = paper_dir / "width_pressure_visualization_index.md"
    index.write_text(
        "\n".join(
            [
                "# Width / Pressure Visualization Index",
                "",
                f"- source_output_dir: `{result['output_dir']}`",
                "- scope: visualization diagnostics only; no parameter tuning, no API, no CoppeliaSim, no robot SDK.",
                "",
                "| File | Content |",
                "|---|---|",
                "| `width_pressure_visualization_report.md` | 宽度/压力渐变可视化诊断报告 |",
                "| `width_pressure_visualization_manifest.csv` | 图像清单与范围统计 |",
                *[f"| `{name}` | 代表性渐变诊断图 |" for name in copied],
                "",
                "人工看图仍是必要步骤；不能只看指标判断最终书法效果。",
            ]
        ),
        encoding="utf-8",
    )
    return index


def run_width_pressure_visualization(
    *,
    cases_csv: Path = DEFAULT_CASES_CSV,
    output_dir: Path | None = None,
    value_mode: str = "both",
    normalization: str = "both",
    stroke_cmap: str = "blue",
    connector_cmap: str = "gray",
    background_color: str = DEFAULT_BACKGROUND_COLOR,
    stroke_light_color: str = DEFAULT_STROKE_LIGHT_COLOR,
    stroke_dark_color: str = DEFAULT_STROKE_DARK_COLOR,
    connector_light_color: str = DEFAULT_CONNECTOR_LIGHT_COLOR,
    connector_dark_color: str = DEFAULT_CONNECTOR_DARK_COLOR,
    pen_up_color: str = DEFAULT_PEN_UP_COLOR,
    min_alpha: float = DEFAULT_MIN_ALPHA,
    min_visible_linewidth: float = DEFAULT_MIN_VISIBLE_LINEWIDTH,
    draw_pen_up: bool = False,
    max_cases: int | None = None,
    copy_to_paper: bool = True,
) -> dict[str, object]:
    cases_csv = Path(cases_csv)
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = ROOT / "experiments" / "llm_style_trajectory" / "outputs" / f"width_pressure_visualization_{timestamp}"
    output_dir = Path(output_dir)
    figures_dir = output_dir / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    samples, warnings = _load_samples(cases_csv, max_cases)
    ranges = _global_ranges(samples)
    manifest_rows: list[dict[str, object]] = []

    for sample in samples:
        rows = sample["rows"]  # type: ignore[index]
        stats = sample["stats"]  # type: ignore[index]
        char = str(sample["char"])
        style = str(sample["style"])
        sample_id = _case_id(char, style)
        for mode in _mode_list(value_mode):
            for norm_name in _norm_list(normalization):
                if norm_name == "global":
                    min_value = ranges[f"global_{mode}_min"]
                    max_value = ranges[f"global_{mode}_max"]
                else:
                    values = [
                        _to_float(row.get(mode))
                        for row in rows
                        if int(_to_float(row.get("pen_down"))) == 1
                        and str(row.get("segment_type")) != "pen_up_move"
                    ]
                    min_value, max_value = _range(values)
                figure = figures_dir / f"{mode}_{norm_name.replace('-', '_')}_{sample_id}.png"
                render_width_pressure_figure(
                    rows,
                    figure,
                    value_mode=mode,
                    normalization=norm_name,
                    value_range=_expand_range(min_value, max_value),
                    title=f"{mode} {norm_name} {sample_id}",
                    stroke_cmap=stroke_cmap,
                    connector_cmap=connector_cmap,
                    background_color=background_color,
                    stroke_light_color=stroke_light_color,
                    stroke_dark_color=stroke_dark_color,
                    connector_light_color=connector_light_color,
                    connector_dark_color=connector_dark_color,
                    pen_up_color=pen_up_color,
                    min_alpha=min_alpha,
                    min_visible_linewidth=min_visible_linewidth,
                    draw_pen_up=draw_pen_up,
                )
                manifest_rows.append(
                    _manifest_row(
                        sample=sample,
                        figure_path=figure,
                        value_mode=mode,
                        normalization=norm_name,
                        stats=stats,
                    )
                )

    manifest_csv = output_dir / "width_pressure_visualization_manifest.csv"
    ranges_json = output_dir / "width_pressure_value_ranges.json"
    report_md = output_dir / "width_pressure_visualization_report.md"
    _write_csv(manifest_csv, MANIFEST_FIELDS, manifest_rows)
    ranges_json.write_text(json.dumps(ranges, ensure_ascii=False, indent=2), encoding="utf-8")
    visual_settings = visual_color_diagnostics(
        background_color=background_color,
        stroke_light_color=stroke_light_color,
        connector_light_color=connector_light_color,
        min_alpha=min_alpha,
        min_visible_linewidth=min_visible_linewidth,
    )
    _write_report(
        report_md,
        cases_csv=cases_csv,
        samples=samples,
        manifest_rows=manifest_rows,
        ranges=ranges,
        visual_settings=visual_settings,
        warnings=warnings,
    )

    paper_index = None
    if copy_to_paper:
        paper_index = _copy_to_paper_figures(
            {
                "output_dir": str(output_dir),
                "outputs": {
                    "report_md": report_md,
                    "manifest_csv": manifest_csv,
                    "figures_dir": figures_dir,
                },
            }
        )

    return {
        "output_dir": str(output_dir),
        "sample_count": len(samples),
        "figure_count": len(manifest_rows),
        "warnings": warnings,
        "ranges": ranges,
        "visual_settings": visual_settings,
        "outputs": {
            "report_md": report_md,
            "manifest_csv": manifest_csv,
            "value_ranges_json": ranges_json,
            "figures_dir": figures_dir,
            "paper_index": paper_index,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render width/pressure gradient diagnostics from execution trajectories.")
    parser.add_argument("--cases-csv", type=Path, default=DEFAULT_CASES_CSV)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--value-mode", choices=["width", "pressure", "both"], default="both")
    parser.add_argument("--normalization", choices=["global", "per-image", "both"], default="both")
    parser.add_argument("--stroke-cmap", default="blue")
    parser.add_argument("--connector-cmap", default="gray")
    parser.add_argument("--background-color", default=DEFAULT_BACKGROUND_COLOR)
    parser.add_argument("--stroke-light-color", default=DEFAULT_STROKE_LIGHT_COLOR)
    parser.add_argument("--stroke-dark-color", default=DEFAULT_STROKE_DARK_COLOR)
    parser.add_argument("--connector-light-color", default=DEFAULT_CONNECTOR_LIGHT_COLOR)
    parser.add_argument("--connector-dark-color", default=DEFAULT_CONNECTOR_DARK_COLOR)
    parser.add_argument("--pen-up-color", default=DEFAULT_PEN_UP_COLOR)
    parser.add_argument("--min-alpha", type=float, default=DEFAULT_MIN_ALPHA)
    parser.add_argument("--min-visible-linewidth", type=float, default=DEFAULT_MIN_VISIBLE_LINEWIDTH)
    parser.add_argument("--draw-pen-up", action="store_true")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args()

    result = run_width_pressure_visualization(
        cases_csv=args.cases_csv,
        output_dir=args.out_dir,
        value_mode=args.value_mode,
        normalization=args.normalization,
        stroke_cmap=args.stroke_cmap,
        connector_cmap=args.connector_cmap,
        background_color=args.background_color,
        stroke_light_color=args.stroke_light_color,
        stroke_dark_color=args.stroke_dark_color,
        connector_light_color=args.connector_light_color,
        connector_dark_color=args.connector_dark_color,
        pen_up_color=args.pen_up_color,
        min_alpha=args.min_alpha,
        min_visible_linewidth=args.min_visible_linewidth,
        draw_pen_up=args.draw_pen_up,
        max_cases=args.max_cases,
        copy_to_paper=not args.no_copy_to_paper,
    )
    printable = {
        "output_dir": result["output_dir"],
        "sample_count": result["sample_count"],
        "figure_count": result["figure_count"],
        "report_md": str(result["outputs"]["report_md"]),  # type: ignore[index]
        "manifest_csv": str(result["outputs"]["manifest_csv"]),  # type: ignore[index]
        "value_ranges_json": str(result["outputs"]["value_ranges_json"]),  # type: ignore[index]
        "paper_index": str(result["outputs"]["paper_index"] or ""),  # type: ignore[index]
        "warnings": result["warnings"],
    }
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
