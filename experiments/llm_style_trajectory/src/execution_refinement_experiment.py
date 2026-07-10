"""Before/after experiment for execution connector and taper refinements."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from execution_refinement import (
    DEFAULT_REFINEMENT_PROFILE,
    execution_refinement_metrics,
    load_refinement_profiles,
    refine_execution_rows,
)
from execution_tools import write_execution_csv
from width_pressure_visualization import (
    DEFAULT_BACKGROUND_COLOR,
    DEFAULT_CONNECTOR_DARK_COLOR,
    DEFAULT_CONNECTOR_LIGHT_COLOR,
    DEFAULT_MIN_ALPHA,
    DEFAULT_MIN_VISIBLE_LINEWIDTH,
    DEFAULT_PEN_UP_COLOR,
    DEFAULT_STROKE_DARK_COLOR,
    DEFAULT_STROKE_LIGHT_COLOR,
    render_width_pressure_figure,
    visual_color_diagnostics,
)


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_CASES_CSV = (
    EXP_DIR
    / "outputs"
    / "connector_brush_visual_diagnostics_20260618_093510"
    / "connector_brush_diagnostic_cases.csv"
)
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"

DEFAULT_TARGETS = [
    ("国", "xingkai"),
    ("德", "xingkai"),
    ("福", "xingkai"),
    ("人", "xingkai"),
    ("中", "xingkai"),
    ("和", "xingkai"),
    ("人", "kaishu"),
    ("人", "lishu"),
]

SUMMARY_FIELDS = [
    "char",
    "style",
    "source_output_dir",
    "baseline_execution_csv",
    "refined_execution_csv",
    "before_connection_count",
    "after_connection_count",
    "connection_count_delta",
    "before_connector_draw_length",
    "after_connector_draw_length",
    "connector_draw_length_delta",
    "before_connector_mean_width",
    "after_connector_mean_width",
    "before_connector_mean_pressure",
    "after_connector_mean_pressure",
    "before_stroke_width_min",
    "before_stroke_width_max",
    "before_stroke_width_range",
    "after_stroke_width_min",
    "after_stroke_width_max",
    "after_stroke_width_range",
    "before_stroke_pressure_min",
    "before_stroke_pressure_max",
    "before_stroke_pressure_range",
    "after_stroke_pressure_min",
    "after_stroke_pressure_max",
    "after_stroke_pressure_range",
    "before_mean_width",
    "after_mean_width",
    "before_path_length",
    "after_path_length",
    "visual_min_color_distance_from_white",
    "connector_compare_png",
    "width_pressure_refined_png",
    "needs_user_review",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _read_execution_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in _read_csv(path):
        parsed: dict[str, Any] = {}
        for key, value in row.items():
            if key in {
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
            }:
                try:
                    parsed[key] = float(value)
                except (TypeError, ValueError):
                    parsed[key] = 0.0
            else:
                parsed[key] = value
        rows.append(parsed)
    return rows


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _case_id(char: str, style: str) -> str:
    return f"u{ord(char):04x}_{style}"


def _load_style_modifiers(source_dir: Path) -> dict[str, str]:
    summary_json = source_dir / "summary.json"
    if not summary_json.exists():
        return {"connection_preference": "weak"}
    try:
        summary = json.loads(summary_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"connection_preference": "weak"}
    modifiers = summary.get("style_modifiers", {})
    return modifiers if isinstance(modifiers, dict) else {"connection_preference": "weak"}


def _choose_cases(cases_csv: Path, target_pairs: Sequence[tuple[str, str]] | None) -> list[dict[str, str]]:
    rows = _read_csv(cases_csv)
    seen: set[tuple[str, str]] = set()
    by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row.get("char", ""), row.get("style", ""))
        if key not in seen:
            seen.add(key)
            by_key[key] = row
    targets = list(target_pairs or DEFAULT_TARGETS)
    selected = [by_key[key] for key in targets if key in by_key]
    return selected or list(by_key.values())


def _group_segments(rows: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current_id: Any = object()
    for row in rows:
        segment_id = row.get("segment_id")
        if not groups or segment_id != current_id:
            groups.append([])
            current_id = segment_id
        groups[-1].append(row)
    return groups


def _points(group: Sequence[dict[str, Any]]) -> tuple[list[float], list[float]]:
    return [float(row["x"]) for row in group], [float(row["y"]) for row in group]


def _draw_overlay(ax, rows: Sequence[dict[str, Any]], title: str) -> None:
    ax.set_title(title, fontsize=9)
    ax.set_aspect("equal")
    ax.set_xlim(0, 256)
    ax.set_ylim(256, 0)
    ax.set_facecolor(DEFAULT_BACKGROUND_COLOR)
    ax.grid(True, color="#d8d8d0", linewidth=0.35, alpha=0.7)
    ax.set_xticks([])
    ax.set_yticks([])
    legend_seen: set[str] = set()
    for group in _group_segments(rows):
        if not group:
            continue
        x, y = _points(group)
        segment_type = str(group[0].get("segment_type"))
        if segment_type == "connector":
            color, linewidth, alpha, linestyle, label = "#d95f02", 2.0, 0.88, "-", "connector"
        elif segment_type == "pen_up_move":
            color, linewidth, alpha, linestyle, label = DEFAULT_PEN_UP_COLOR, 1.0, 0.55, "--", "pen-up"
        else:
            color, linewidth, alpha, linestyle, label = "#1f78b4", 1.8, 0.9, "-", "stroke"
        ax.plot(
            x,
            y,
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            linestyle=linestyle,
            solid_capstyle="round",
            label=label if label not in legend_seen else None,
        )
        legend_seen.add(label)
    if legend_seen:
        ax.legend(loc="lower right", fontsize=6, framealpha=0.86)


def _write_connector_compare(before_rows: Sequence[dict[str, Any]], after_rows: Sequence[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3.8), dpi=160)
    fig.patch.set_facecolor(DEFAULT_BACKGROUND_COLOR)
    _draw_overlay(axes[0], before_rows, "before: baseline")
    _draw_overlay(axes[1], after_rows, "after: conservative + taper")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _summary_row(
    *,
    char: str,
    style: str,
    source_dir: Path,
    baseline_csv: Path,
    refined_csv: Path,
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
    visual_settings: dict[str, object],
    connector_compare: Path,
    width_pressure_refined: Path,
) -> dict[str, Any]:
    visual_min_distance = min(
        float(visual_settings["stroke_light_distance_from_white"]),
        float(visual_settings["connector_light_distance_from_white"]),
    )
    return {
        "char": char,
        "style": style,
        "source_output_dir": str(source_dir),
        "baseline_execution_csv": str(baseline_csv),
        "refined_execution_csv": str(refined_csv),
        "before_connection_count": before_metrics["connection_count"],
        "after_connection_count": after_metrics["connection_count"],
        "connection_count_delta": int(after_metrics["connection_count"]) - int(before_metrics["connection_count"]),
        "before_connector_draw_length": before_metrics["connector_draw_length"],
        "after_connector_draw_length": after_metrics["connector_draw_length"],
        "connector_draw_length_delta": round(
            float(after_metrics["connector_draw_length"]) - float(before_metrics["connector_draw_length"]), 3
        ),
        "before_connector_mean_width": before_metrics["connector_mean_width"],
        "after_connector_mean_width": after_metrics["connector_mean_width"],
        "before_connector_mean_pressure": before_metrics["connector_mean_pressure"],
        "after_connector_mean_pressure": after_metrics["connector_mean_pressure"],
        "before_stroke_width_min": before_metrics["stroke_width_min"],
        "before_stroke_width_max": before_metrics["stroke_width_max"],
        "before_stroke_width_range": before_metrics["stroke_width_range"],
        "after_stroke_width_min": after_metrics["stroke_width_min"],
        "after_stroke_width_max": after_metrics["stroke_width_max"],
        "after_stroke_width_range": after_metrics["stroke_width_range"],
        "before_stroke_pressure_min": before_metrics["stroke_pressure_min"],
        "before_stroke_pressure_max": before_metrics["stroke_pressure_max"],
        "before_stroke_pressure_range": before_metrics["stroke_pressure_range"],
        "after_stroke_pressure_min": after_metrics["stroke_pressure_min"],
        "after_stroke_pressure_max": after_metrics["stroke_pressure_max"],
        "after_stroke_pressure_range": after_metrics["stroke_pressure_range"],
        "before_mean_width": before_metrics["mean_width"],
        "after_mean_width": after_metrics["mean_width"],
        "before_path_length": before_metrics["path_length"],
        "after_path_length": after_metrics["path_length"],
        "visual_min_color_distance_from_white": round(visual_min_distance, 6),
        "connector_compare_png": str(connector_compare),
        "width_pressure_refined_png": str(width_pressure_refined),
        "needs_user_review": True,
    }


def _write_report(
    *,
    output_dir: Path,
    summary_rows: Sequence[dict[str, Any]],
    report_md: Path,
    visual_settings: dict[str, object],
    connector_rule: dict[str, Any],
) -> None:
    style_counts = Counter(row["style"] for row in summary_rows)
    total_before = sum(int(row["before_connection_count"]) for row in summary_rows)
    total_after = sum(int(row["after_connection_count"]) for row in summary_rows)
    lines = [
        "# Execution Refinement Experiment",
        "",
        "## 用户问题回顾",
        "",
        "- connector 过多：旧执行层在行楷允许连接时容易把所有相邻笔画首尾依次相连。",
        "- stroke 内部粗细恒定：上一轮 width/pressure 渐变图显示 16 个样本的 stroke width nearly constant。",
        "- 浅色接近白底看不清：旧渐变图的浅色端对 connector 不够友好。",
        "- lishu 横向拉宽问题本轮暂不解决，只记录为后续真实风格来源问题。",
        "",
        "## 本轮改动",
        "",
        "- conservative connector gate：用距离、角度和 connect_every_n 收紧行楷 connector 触发。",
        "- simple stroke taper：只对 stroke 段施加起笔 / 中段 / 收笔 width 和 pressure 曲线。",
        "- non-white light color visualization：浅色端改为可见浅蓝和棕灰，背景为浅暖灰。",
        f"- connector gate 参数：`{json.dumps(connector_rule, ensure_ascii=False, sort_keys=True)}`。",
        "- `skip_if_crosses_bbox_center` 已在代码中实现，但本轮实验配置为 false；在当前样本上开启它会让 connector 几乎清零，不利于人工比较。",
        "",
        "本轮不是最终参数，本轮不是真实笔刷模型，本轮颜色只为可读性；仍需人工看图确认。",
        "",
        "## 输出目录",
        "",
        f"`{output_dir}`",
        "",
        "## 可视化颜色设置",
        "",
        f"- background_color: `{visual_settings['background_color']}`",
        f"- stroke_light_color: `{visual_settings['stroke_light_color']}`",
        f"- connector_light_color: `{visual_settings['connector_light_color']}`",
        f"- stroke_light_distance_from_white: `{visual_settings['stroke_light_distance_from_white']}`",
        f"- connector_light_distance_from_white: `{visual_settings['connector_light_distance_from_white']}`",
        f"- min_alpha: `{visual_settings['min_alpha']}`",
        f"- min_visible_linewidth: `{visual_settings['min_visible_linewidth']}`",
        "",
        "## 总体 before/after",
        "",
        f"- sample_count: `{len(summary_rows)}`",
        f"- style_counts: `{dict(style_counts)}`",
        f"- total_connection_count_before/after: `{total_before}` / `{total_after}`",
        "",
        "## 指标表",
        "",
        "| char | style | conn before | conn after | connector length before | connector length after | stroke width range before | stroke width range after | figure |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        lines.append(
            "| {char} | {style} | {bc} | {ac} | {bl} | {al} | {bw} | {aw} | `{fig}` |".format(
                char=row["char"],
                style=row["style"],
                bc=row["before_connection_count"],
                ac=row["after_connection_count"],
                bl=row["before_connector_draw_length"],
                al=row["after_connector_draw_length"],
                bw=row["before_stroke_width_range"],
                aw=row["after_stroke_width_range"],
                fig=Path(str(row["connector_compare_png"])).name,
            )
        )
    lines.extend(
        [
            "",
            "## 需要人工看图的图",
            "",
        ]
    )
    for row in summary_rows:
        lines.append(f"- {row['char']} / {row['style']}: `{row['connector_compare_png']}`")
        lines.append(f"- {row['char']} / {row['style']} width/pressure: `{row['width_pressure_refined_png']}`")
    lines.extend(
        [
            "",
            "## 初步结论",
            "",
            "- 如果 after connector 数量下降，说明 conservative gate 已经减轻“每笔必连”的问题。",
            "- 如果 after stroke width range 大于 before，说明 simple taper 已经让 stroke 内部粗细可见变化进入执行层。",
            "- connector 是否自然、stroke taper 是否像书写效果，仍必须人工看图判断；不能只看指标。",
            "",
            "## 边界",
            "",
            "- 本轮不是最终行楷规则。",
            "- 本轮不是真实笔刷模型。",
            "- 本轮不解决 lishu 的真实风格来源问题。",
            "- 本轮不调用 API，不连接 CoppeliaSim，不连接 AUBO i5，不调用 SDK，不发送机器人命令。",
        ]
    )
    report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _copy_to_paper(result: dict[str, Any], paper_dir: Path = DEFAULT_PAPER_DIR) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    for source_key in ["report_md", "summary_csv"]:
        source = Path(result[source_key])
        if source.exists():
            shutil.copy2(source, paper_dir / source.name)
    figures = [Path(row["connector_compare_png"]) for row in result["summary_rows"][:3]]
    figures += [Path(row["width_pressure_refined_png"]) for row in result["summary_rows"][:2]]
    copied: list[str] = []
    for source in figures:
        if source.exists():
            dest = paper_dir / f"execution_refinement_{source.name}"
            shutil.copy2(source, dest)
            copied.append(dest.name)
    index = paper_dir / "execution_refinement_index.md"
    index.write_text(
        "\n".join(
            [
                "# Execution Refinement Index",
                "",
                f"- source_output_dir: `{result['output_dir']}`",
                "- scope: connector trigger and stroke taper diagnostics only; no API, no CoppeliaSim, no robot SDK, no IK.",
                "",
                "| File | Content |",
                "|---|---|",
                "| `execution_refinement_report.md` | 实验报告 |",
                "| `execution_refinement_summary.csv` | before/after 指标 |",
                *[f"| `{name}` | 代表性 before/after 或 width/pressure 图 |" for name in copied],
                "",
                "这些图需要人工看图确认，不能只看指标判断最终书法效果。",
            ]
        ),
        encoding="utf-8",
    )
    return index


def run_execution_refinement_experiment(
    *,
    cases_csv: Path = DEFAULT_CASES_CSV,
    output_dir: Path | None = None,
    profile_path: Path = DEFAULT_REFINEMENT_PROFILE,
    target_pairs: Sequence[tuple[str, str]] | None = None,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = output_dir or DEFAULT_OUTPUT / f"execution_refinement_{timestamp}"
    out_dir = Path(out_dir)
    case_out_dir = out_dir / "cases"
    figures_dir = out_dir / "figures"
    case_out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    profiles = load_refinement_profiles(profile_path)
    connector_rule = profiles["connector_rules"]["conservative"]
    stroke_width_profile = profiles["stroke_width_profiles"]["simple_taper"]
    visual_cfg = profiles.get("visualization", {})
    visual_settings = visual_color_diagnostics(
        background_color=str(visual_cfg.get("background_color", DEFAULT_BACKGROUND_COLOR)),
        stroke_light_color=str(visual_cfg.get("stroke_light_color", DEFAULT_STROKE_LIGHT_COLOR)),
        connector_light_color=str(visual_cfg.get("connector_light_color", DEFAULT_CONNECTOR_LIGHT_COLOR)),
        min_alpha=float(visual_cfg.get("min_alpha", DEFAULT_MIN_ALPHA)),
        min_visible_linewidth=float(visual_cfg.get("min_visible_linewidth", DEFAULT_MIN_VISIBLE_LINEWIDTH)),
    )

    summary_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    for case in _choose_cases(cases_csv, target_pairs):
        char = case.get("char", "")
        style = case.get("style", "")
        source_dir = Path(case.get("source_output_dir", ""))
        source_execution = source_dir / "execution_trajectory.csv"
        if not source_execution.exists():
            continue
        before_rows = _read_execution_csv(source_execution)
        modifiers = _load_style_modifiers(source_dir)
        after_rows = refine_execution_rows(
            before_rows,
            style=style,
            style_modifiers=modifiers,
            connector_rule=connector_rule,
            stroke_width_profile=stroke_width_profile,
        )
        sample_id = _case_id(char, style)
        sample_dir = case_out_dir / sample_id
        baseline_csv = sample_dir / "baseline_execution_trajectory.csv"
        refined_csv = sample_dir / "refined_execution_trajectory.csv"
        write_execution_csv(before_rows, baseline_csv)
        write_execution_csv(after_rows, refined_csv)

        connector_compare = figures_dir / f"before_after_connector_{sample_id}.png"
        width_pressure_refined = figures_dir / (
            f"width_pressure_refined_{sample_id}.png" if style == "xingkai" else f"stroke_taper_{sample_id}.png"
        )
        _write_connector_compare(before_rows, after_rows, connector_compare)
        render_width_pressure_figure(
            after_rows,
            width_pressure_refined,
            value_mode="width",
            normalization="refined",
            value_range=(
                min(float(row.get("width", 0.0)) for row in after_rows if str(row.get("segment_type")) == "stroke"),
                max(float(row.get("width", 0.0)) for row in after_rows if str(row.get("segment_type")) == "stroke"),
            ),
            title=f"refined width {sample_id}",
            background_color=str(visual_cfg.get("background_color", DEFAULT_BACKGROUND_COLOR)),
            stroke_light_color=str(visual_cfg.get("stroke_light_color", DEFAULT_STROKE_LIGHT_COLOR)),
            stroke_dark_color=str(visual_cfg.get("stroke_dark_color", DEFAULT_STROKE_DARK_COLOR)),
            connector_light_color=str(visual_cfg.get("connector_light_color", DEFAULT_CONNECTOR_LIGHT_COLOR)),
            connector_dark_color=str(visual_cfg.get("connector_dark_color", DEFAULT_CONNECTOR_DARK_COLOR)),
            pen_up_color=str(visual_cfg.get("pen_up_color", DEFAULT_PEN_UP_COLOR)),
            min_alpha=float(visual_cfg.get("min_alpha", DEFAULT_MIN_ALPHA)),
            min_visible_linewidth=float(visual_cfg.get("min_visible_linewidth", DEFAULT_MIN_VISIBLE_LINEWIDTH)),
        )

        before_metrics = execution_refinement_metrics(before_rows)
        after_metrics = execution_refinement_metrics(after_rows)
        summary_rows.append(
            _summary_row(
                char=char,
                style=style,
                source_dir=source_dir,
                baseline_csv=baseline_csv,
                refined_csv=refined_csv,
                before_metrics=before_metrics,
                after_metrics=after_metrics,
                visual_settings=visual_settings,
                connector_compare=connector_compare,
                width_pressure_refined=width_pressure_refined,
            )
        )
        case_rows.append(
            {
                "char": char,
                "style": style,
                "source_output_dir": str(source_dir),
                "baseline_execution_csv": str(baseline_csv),
                "refined_execution_csv": str(refined_csv),
                "connector_compare_png": str(connector_compare),
                "width_pressure_refined_png": str(width_pressure_refined),
                "manual_check_focus": "connector 是否仍过多；stroke taper 是否自然；浅色 connector 是否可见",
                "needs_user_review": True,
            }
        )

    summary_csv = out_dir / "execution_refinement_summary.csv"
    report_md = out_dir / "execution_refinement_report.md"
    cases_out_csv = out_dir / "execution_refinement_cases.csv"
    _write_csv(summary_csv, summary_rows, SUMMARY_FIELDS)
    _write_csv(
        cases_out_csv,
        case_rows,
        [
            "char",
            "style",
            "source_output_dir",
            "baseline_execution_csv",
            "refined_execution_csv",
            "connector_compare_png",
            "width_pressure_refined_png",
            "manual_check_focus",
            "needs_user_review",
        ],
    )
    _write_report(
        output_dir=out_dir,
        summary_rows=summary_rows,
        report_md=report_md,
        visual_settings=visual_settings,
        connector_rule=connector_rule,
    )

    result: dict[str, Any] = {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "cases_csv": str(cases_out_csv),
        "figures_dir": str(figures_dir),
        "summary_rows": summary_rows,
        "visual_settings": visual_settings,
    }
    if copy_to_paper:
        result["paper_index"] = str(_copy_to_paper(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run execution refinement before/after diagnostics.")
    parser.add_argument("--cases-csv", type=Path, default=DEFAULT_CASES_CSV)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=DEFAULT_REFINEMENT_PROFILE)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args()
    result = run_execution_refinement_experiment(
        cases_csv=args.cases_csv,
        output_dir=args.out_dir,
        profile_path=args.profile,
        copy_to_paper=not args.no_copy_to_paper,
    )
    printable = {key: value for key, value in result.items() if key not in {"summary_rows"}}
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
