"""Balanced connector and local xingkai-style execution diagnostics.

This script stays entirely in the deterministic execution layer. It does not
call APIs, CoppeliaSim, robot SDKs, IK, or real robot commands.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
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
    DEFAULT_PEN_UP_COLOR,
    render_width_pressure_figure,
)


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_CASES_DIR = EXP_DIR / "outputs" / "execution_refinement_validation_20260618_120238" / "cases"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"

XINGKAI_TARGETS = [
    ("国", "xingkai"),
    ("德", "xingkai"),
    ("福", "xingkai"),
    ("和", "xingkai"),
    ("中", "xingkai"),
    ("人", "xingkai"),
    ("明", "xingkai"),
    ("林", "xingkai"),
]
SAFETY_TARGETS = [("人", "kaishu"), ("人", "lishu"), ("中", "kaishu"), ("中", "lishu")]
DEFAULT_TARGETS = XINGKAI_TARGETS + SAFETY_TARGETS

SUMMARY_FIELDS = [
    "char",
    "style",
    "variant",
    "source_case_dir",
    "execution_csv",
    "connection_count",
    "connector_draw_length",
    "connector_mean_width",
    "connector_mean_pressure",
    "stroke_width_range",
    "stroke_pressure_range",
    "path_length",
    "has_curved_connector",
    "connector_reduction_vs_baseline",
    "connector_increase_vs_conservative",
    "kaishu_lishu_connector_violation",
    "needs_user_review",
    "review_focus",
    "compare_png",
    "width_pressure_png",
]

MANIFEST_FIELDS = [
    "char",
    "style",
    "figure_type",
    "figure_path",
    "source_case_dir",
    "needs_user_review",
    "review_focus",
]

FAILURE_FIELDS = ["char", "style", "reason", "source_case_dir"]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _read_execution_csv(path: Path) -> list[dict[str, Any]]:
    numeric = {
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
    rows: list[dict[str, Any]] = []
    for row in _read_csv(path):
        rows.append({key: _safe_float(value) if key in numeric else value for key, value in row.items()})
    return rows


def _case_id(char: str, style: str) -> str:
    return f"u{ord(char):04x}_{style}"


def _case_dir(cases_dir: Path, char: str, style: str) -> Path:
    return cases_dir / _case_id(char, style)


def _baseline_csv(case_dir: Path) -> Path:
    for name in ["baseline_execution_trajectory.csv", "execution_trajectory.csv"]:
        path = case_dir / name
        if path.exists():
            return path
    return case_dir / "baseline_execution_trajectory.csv"


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


def _xy(group: Sequence[dict[str, Any]]) -> tuple[list[float], list[float]]:
    return [float(row["x"]) for row in group], [float(row["y"]) for row in group]


def _has_curved_connector(rows: Sequence[dict[str, Any]]) -> bool:
    for group in _group_segments(rows):
        if not group or str(group[0].get("segment_type")) != "connector" or len(group) < 3:
            continue
        pts = [(float(row["y"]), float(row["x"])) for row in group]
        start = pts[0]
        end = pts[-1]
        mid = pts[len(pts) // 2]
        line_mid = ((start[0] + end[0]) * 0.5, (start[1] + end[1]) * 0.5)
        if math.hypot(mid[0] - line_mid[0], mid[1] - line_mid[1]) > 0.1:
            return True
    return False


def _draw_variant(ax, rows: Sequence[dict[str, Any]], title: str) -> None:
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlim(0, 256)
    ax.set_ylim(256, 0)
    ax.set_facecolor(DEFAULT_BACKGROUND_COLOR)
    ax.grid(True, color="#dddddd", linewidth=0.35, alpha=0.65)
    ax.set_xticks([])
    ax.set_yticks([])
    seen: set[str] = set()
    for group in _group_segments(rows):
        if not group:
            continue
        x, y = _xy(group)
        segment_type = str(group[0].get("segment_type"))
        if segment_type == "connector":
            color, linewidth, alpha, linestyle, label = "#d95f02", 2.2, 0.9, "-", "connector"
        elif segment_type == "pen_up_move":
            color, linewidth, alpha, linestyle, label = DEFAULT_PEN_UP_COLOR, 1.0, 0.45, "--", "pen-up"
        else:
            color, linewidth, alpha, linestyle, label = "#1f78b4", 1.7, 0.9, "-", "stroke"
        ax.plot(
            x,
            y,
            color=color,
            linewidth=linewidth,
            alpha=alpha,
            linestyle=linestyle,
            solid_capstyle="round",
            label=label if label not in seen else None,
        )
        seen.add(label)
    if seen:
        ax.legend(loc="lower right", fontsize=6, framealpha=0.86)


def _write_compare_figure(
    variants: dict[str, list[dict[str, Any]]],
    metrics: dict[str, dict[str, Any]],
    path: Path,
    *,
    char: str,
    style: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    labels = ["baseline", "conservative", "balanced"]
    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.6), dpi=150)
    for ax, label in zip(axes, labels):
        item = metrics[label]
        title = (
            f"{label}\n"
            f"conn={item['connection_count']} len={item['connector_draw_length']}\n"
            "diagnostic, not final writing"
        )
        _draw_variant(ax, variants[label], title)
    fig.suptitle(f"{char} / {style}: connector levels", fontsize=10)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.92])
    fig.savefig(path)
    plt.close(fig)


def _review_focus(char: str, style: str, metrics: dict[str, dict[str, Any]]) -> str:
    if style != "xingkai":
        return "人工看图：确认非行楷仍无 connector，且 expressive 改动没有误作用。"
    balanced_count = int(metrics["balanced"]["connection_count"])
    conservative_count = int(metrics["conservative"]["connection_count"])
    if balanced_count == conservative_count:
        return "人工看图：balanced 未比 conservative 增加 connector，确认是否仍偏保守。"
    return "人工看图：确认 balanced 是否比 conservative 更有行楷味，同时没有回到全连。"


def _row(
    *,
    char: str,
    style: str,
    variant: str,
    case_dir: Path,
    execution_csv: Path,
    metrics: dict[str, Any],
    baseline_metrics: dict[str, Any],
    conservative_metrics: dict[str, Any],
    compare_png: Path,
    width_pressure_png: Path | str,
    review_focus: str,
) -> dict[str, Any]:
    base_count = int(baseline_metrics["connection_count"])
    cons_count = int(conservative_metrics["connection_count"])
    current_count = int(metrics["connection_count"])
    return {
        "char": char,
        "style": style,
        "variant": variant,
        "source_case_dir": str(case_dir),
        "execution_csv": str(execution_csv),
        "connection_count": current_count,
        "connector_draw_length": metrics["connector_draw_length"],
        "connector_mean_width": metrics["connector_mean_width"],
        "connector_mean_pressure": metrics["connector_mean_pressure"],
        "stroke_width_range": metrics["stroke_width_range"],
        "stroke_pressure_range": metrics["stroke_pressure_range"],
        "path_length": metrics["path_length"],
        "has_curved_connector": bool(metrics["has_curved_connector"]),
        "connector_reduction_vs_baseline": base_count - current_count,
        "connector_increase_vs_conservative": current_count - cons_count,
        "kaishu_lishu_connector_violation": style in {"kaishu", "lishu"} and current_count > 0,
        "needs_user_review": True,
        "review_focus": review_focus,
        "compare_png": str(compare_png),
        "width_pressure_png": str(width_pressure_png),
    }


def _variant_rows(
    *,
    baseline_rows: list[dict[str, Any]],
    style: str,
    profiles: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    baseline = refine_execution_rows(
        baseline_rows,
        style=style,
        style_modifiers={"connection_preference": "weak"},
        connector_rule=profiles["connector_rules"]["baseline"],
        stroke_width_profile=profiles["stroke_width_profiles"]["flat"],
    )
    conservative = refine_execution_rows(
        baseline_rows,
        style=style,
        style_modifiers={"connection_preference": "weak"},
        connector_rule=profiles["connector_rules"]["conservative"],
        stroke_width_profile=profiles["stroke_width_profiles"]["simple_taper"],
    )
    balanced = refine_execution_rows(
        baseline_rows,
        style=style,
        style_modifiers={"connection_preference": "weak"},
        connector_rule=profiles["connector_rules"]["balanced"],
        stroke_width_profile=(
            profiles["stroke_width_profiles"]["xingkai_expressive_taper"]
            if style == "xingkai"
            else profiles["stroke_width_profiles"]["simple_taper"]
        ),
        connector_shape=profiles["connector_shapes"]["slight_curve"] if style == "xingkai" else profiles["connector_shapes"]["straight"],
    )
    return {"baseline": baseline, "conservative": conservative, "balanced": balanced}


def _metrics_by_variant(variants: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for label, rows in variants.items():
        metrics = dict(execution_refinement_metrics(rows))
        metrics["has_curved_connector"] = _has_curved_connector(rows)
        out[label] = metrics
    return out


def _write_report(
    path: Path,
    *,
    output_dir: Path,
    summary_rows: Sequence[dict[str, Any]],
    failures: Sequence[dict[str, Any]],
) -> None:
    xingkai_balanced = [row for row in summary_rows if row["style"] == "xingkai" and row["variant"] == "balanced"]
    between = [
        row
        for row in xingkai_balanced
        if int(row["connector_reduction_vs_baseline"]) > 0 and int(row["connector_increase_vs_conservative"]) >= 0
    ]
    zero_after = [row for row in xingkai_balanced if int(row["connection_count"]) == 0]
    violations = [
        row for row in summary_rows if str(row.get("kaishu_lishu_connector_violation", "")).lower() == "true"
    ]

    lines = [
        "# balanced connector + 行楷局部风格增强实验",
        "",
        "## 用户问题回顾",
        "",
        "- 当前 conservative connector 太少。",
        "- 行楷仍像“楷书骨架 + 少量连笔 + taper”。",
        "- 当前不适合直接进入仿真书写展示。",
        "",
        "## 本轮方法",
        "",
        "- 新增 `balanced` connector gate，位于旧 `baseline/all_adjacent` 与 `candidate_default_v1/conservative` 之间。",
        "- 对行楷 connector 使用 `slight_curve` 二次贝塞尔曲线，避免所有连接段都是直线。",
        "- 对行楷使用 `xingkai_expressive_taper`，略增强起收笔宽度/压力变化。",
        "- 不影响 kaishu / lishu；非行楷仍不允许 connector。",
        "",
        "## 输出目录",
        "",
        f"`{output_dir}`",
        "",
        "## 样本统计",
        "",
        f"- summary rows: `{len(summary_rows)}`",
        f"- failures: `{len(failures)}`",
        f"- xingkai balanced samples: `{len(xingkai_balanced)}`",
        f"- balanced between baseline/conservative count: `{len(between)}`",
        f"- xingkai balanced zero-connector samples: `{len(zero_after)}`",
        f"- kaishu/lishu connector violations: `{len(violations)}`",
        "",
        "## baseline / conservative / balanced 指标对比",
        "",
        "| char | style | variant | connection_count | connector_draw_length | stroke_width_range | has_curved_connector |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        lines.append(
            "| {char} | {style} | {variant} | {connection_count} | {connector_draw_length} | {stroke_width_range} | {has_curved_connector} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## 初步判断",
            "",
            "- balanced 的目标是避免回到全连，同时比 conservative 更少清零；是否真正更有行楷味，需要人工看图确认。",
            "- 对 `中/人/明/林` 等 conservative 清零样本，报告中已标注 balanced 是否仍清零；若仍清零，说明 gate 仍偏保守。",
            "- 楷书/隶书样本作为安全检查，不应产生 connector。",
            "",
            "## 人工看图清单",
            "",
        ]
    )
    for row in summary_rows:
        if row["variant"] == "balanced":
            lines.append(f"- {row['char']} / {row['style']}: `{row['compare_png']}`；{row['review_focus']}")

    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 本轮不是最终行楷模型。",
            "- 本轮不是真实书法学习。",
            "- 本轮不进入仿真书写，不连接 CoppeliaSim / AUBO i5。",
            "- 本轮不调用 API，不调用 SDK，不发送机器人命令。",
            "- 隶书当前仍主要是参数化横向拉宽问题，本轮不解决隶书真实风格来源问题。",
            "",
            "## 下一步建议",
            "",
            "- 如果 balanced 仍偏少，再稍放宽 gate。",
            "- 如果 balanced 过多，回到 conservative。",
            "- 如果视觉接受，再考虑作为 `candidate_default_v2`，而不是直接替换全局默认。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _paper_index(
    path: Path,
    *,
    source_output_dir: Path,
) -> None:
    lines = [
        "# Xingkai Balanced Experiment Index",
        "",
        f"- source_output_dir: `{source_output_dir}`",
        "- scope: balanced connector + local xingkai execution diagnostics only; no API, no CoppeliaSim, no AUBO i5.",
        "",
        "| File | Content |",
        "|---|---|",
        "| `xingkai_balanced_report.md` | balanced 实验报告 |",
        "| `xingkai_balanced_summary.csv` | baseline/conservative/balanced 指标汇总 |",
        "| `xingkai_balanced_compare_connector_levels_u56fd_xingkai.png` | 国 / 行楷三档对比图 |",
        "| `xingkai_balanced_compare_connector_levels_u5fb7_xingkai.png` | 德 / 行楷三档对比图 |",
        "| `xingkai_balanced_compare_connector_levels_u798f_xingkai.png` | 福 / 行楷三档对比图 |",
        "| `xingkai_balanced_compare_connector_levels_u548c_xingkai.png` | 和 / 行楷三档对比图 |",
        "| `xingkai_balanced_compare_connector_levels_u4e2d_xingkai.png` | 中 / 行楷三档对比图 |",
        "",
        "这些图需要人工看图判断 balanced 是否比 conservative 更像行楷，同时不过度连笔。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_xingkai_balanced_experiment(
    *,
    cases_dir: Path = DEFAULT_CASES_DIR,
    output_dir: Path | None = None,
    target_pairs: Sequence[tuple[str, str]] | None = None,
    profile_path: Path = DEFAULT_REFINEMENT_PROFILE,
    copy_to_paper: bool = True,
    paper_dir: Path = DEFAULT_PAPER_DIR,
) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"xingkai_balanced_experiment_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = out_dir / "figures"
    cases_out = out_dir / "cases"
    profiles = load_refinement_profiles(profile_path)

    summary_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    selected = list(target_pairs or DEFAULT_TARGETS)

    for char, style in selected:
        source_case = _case_dir(cases_dir, char, style)
        source_csv = _baseline_csv(source_case)
        if not source_csv.exists():
            failures.append({"char": char, "style": style, "reason": "baseline_execution_not_found", "source_case_dir": str(source_case)})
            continue

        baseline_rows = _read_execution_csv(source_csv)
        variants = _variant_rows(baseline_rows=baseline_rows, style=style, profiles=profiles)
        metrics = _metrics_by_variant(variants)
        case_name = _case_id(char, style)
        case_out = cases_out / case_name
        case_out.mkdir(parents=True, exist_ok=True)

        csv_paths: dict[str, Path] = {}
        for label, rows in variants.items():
            csv_path = case_out / f"{label}_execution_trajectory.csv"
            write_execution_csv(rows, csv_path)
            csv_paths[label] = csv_path

        compare_png = figures_dir / f"compare_connector_levels_{case_name}.png"
        _write_compare_figure(variants, metrics, compare_png, char=char, style=style)

        width_png: Path | str = ""
        if style == "xingkai":
            width_png = figures_dir / f"width_pressure_balanced_{case_name}.png"
            render_width_pressure_figure(
                variants["balanced"],
                width_png,
                value_mode="width",
                normalization="per_image",
                value_range=(0.0, 12.0),
                title=f"{char} / {style} balanced width-pressure",
            )

        focus = _review_focus(char, style, metrics)
        for label in ["baseline", "conservative", "balanced"]:
            summary_rows.append(
                _row(
                    char=char,
                    style=style,
                    variant=label,
                    case_dir=source_case,
                    execution_csv=csv_paths[label],
                    metrics=metrics[label],
                    baseline_metrics=metrics["baseline"],
                    conservative_metrics=metrics["conservative"],
                    compare_png=compare_png,
                    width_pressure_png=width_png,
                    review_focus=focus,
                )
            )
        manifest_rows.append(
            {
                "char": char,
                "style": style,
                "figure_type": "connector_levels",
                "figure_path": str(compare_png),
                "source_case_dir": str(source_case),
                "needs_user_review": True,
                "review_focus": focus,
            }
        )
        if width_png:
            manifest_rows.append(
                {
                    "char": char,
                    "style": style,
                    "figure_type": "width_pressure_balanced",
                    "figure_path": str(width_png),
                    "source_case_dir": str(source_case),
                    "needs_user_review": True,
                    "review_focus": "人工看图：确认 expressive taper 的宽度/压力变化是否可见且不过度。",
                }
            )

    summary_csv = out_dir / "xingkai_balanced_summary.csv"
    report_md = out_dir / "xingkai_balanced_report.md"
    manifest_csv = out_dir / "xingkai_balanced_manifest.csv"
    failures_csv = out_dir / "xingkai_balanced_failures.csv"
    _write_csv(summary_csv, summary_rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_csv(failures_csv, failures, FAILURE_FIELDS)
    _write_report(report_md, output_dir=out_dir, summary_rows=summary_rows, failures=failures)

    paper_index = ""
    if copy_to_paper:
        paper_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary_csv, paper_dir / "xingkai_balanced_summary.csv")
        shutil.copy2(report_md, paper_dir / "xingkai_balanced_report.md")
        for src in sorted(figures_dir.glob("compare_connector_levels_*_xingkai.png"))[:5]:
            shutil.copy2(src, paper_dir / f"xingkai_balanced_{src.name}")
        paper_index_path = paper_dir / "xingkai_balanced_experiment_index.md"
        _paper_index(paper_index_path, source_output_dir=out_dir)
        paper_index = str(paper_index_path)

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "failures_csv": str(failures_csv),
        "figures_dir": str(figures_dir),
        "success_count": len(selected) - len(failures),
        "failure_count": len(failures),
        "paper_index": paper_index,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run balanced xingkai execution diagnostics.")
    parser.add_argument("--cases-dir", type=Path, default=DEFAULT_CASES_DIR)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--no-paper-copy", action="store_true")
    args = parser.parse_args()

    result = run_xingkai_balanced_experiment(
        cases_dir=args.cases_dir,
        output_dir=args.out_dir,
        copy_to_paper=not args.no_paper_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
