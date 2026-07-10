"""Readonly Phase 1 style-profile estimator from font-outline statistics.

This script creates candidate style hints only. It does not alter
style_profiles.json, run_demo.py, trajectory generation, or any robot layer.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure


EXP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FONT_GAP_DIR = EXP_DIR / "outputs" / "font_style_gap_analysis_20260618_144838"
DEFAULT_STYLE_PROFILE = EXP_DIR / "configs" / "style_profiles.json"
DEFAULT_OUTPUT_ROOT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"

UNSUPPORTED_FROM_STATIC_FONT = [
    "connection_strength",
    "allow_interstroke_connections",
    "connector_trigger",
    "connector_shape",
    "pressure_curve",
    "speed_scale",
    "pen_up_height",
    "real_robot_dynamics",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(values: list[float], default: float = 0.0) -> float:
    clean = [v for v in values if math.isfinite(v)]
    return sum(clean) / len(clean) if clean else default


def _std(values: list[float]) -> float:
    clean = [v for v in values if math.isfinite(v)]
    if len(clean) < 2:
        return 0.0
    mean = _mean(clean)
    return math.sqrt(sum((v - mean) ** 2 for v in clean) / len(clean))


def _hint(value: float, source: str, confidence: str, notes: str, method: str) -> dict[str, Any]:
    return {
        "value": round(float(value), 6),
        "source": source,
        "method": method,
        "confidence": confidence,
        "notes": notes,
    }


def _style_rows(summary_rows: list[dict[str, str]], style: str) -> list[dict[str, str]]:
    return [
        row
        for row in summary_rows
        if row.get("style") == style and str(row.get("rendered_ok", "")).lower() in {"true", "1", "yes"}
    ]


def load_current_style_profiles(path: Path | str = DEFAULT_STYLE_PROFILE) -> dict[str, dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def _style_mean_lookup(style_means_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("style", ""): row for row in style_means_rows if row.get("style")}


def build_phase1_estimates(
    summary_rows: list[dict[str, str]],
    style_means_rows: list[dict[str, str]],
    current_profiles: dict[str, dict[str, Any]],
    source_name: str,
) -> dict[str, Any]:
    means = _style_mean_lookup(style_means_rows)
    kaishu_aspect = _to_float(means.get("kaishu", {}).get("mean_font_aspect_ratio"), 1.0)
    if kaishu_aspect <= 1e-9:
        kaishu_aspect = 1.0
    styles: dict[str, Any] = {}

    for style in sorted(current_profiles):
        rows = _style_rows(summary_rows, style)
        mean_row = means.get(style, {})
        font_aspect = _to_float(mean_row.get("mean_font_aspect_ratio"), _mean([_to_float(r.get("font_aspect_ratio")) for r in rows], 1.0))
        trajectory_aspect = _to_float(mean_row.get("mean_trajectory_aspect_ratio"), _mean([_to_float(r.get("trajectory_aspect_ratio")) for r in rows], 1.0))
        font_width_mean = _to_float(mean_row.get("mean_font_stroke_width"), _mean([_to_float(r.get("font_stroke_width_mean")) for r in rows], 0.0))
        trajectory_width = _to_float(mean_row.get("mean_trajectory_mean_width"), _mean([_to_float(r.get("trajectory_mean_width")) for r in rows], 0.0))
        width_values = [_to_float(r.get("font_stroke_width_mean")) for r in rows if r.get("font_stroke_width_mean") not in ("", None)]
        width_std_values = [_to_float(r.get("font_stroke_width_std")) for r in rows if r.get("font_stroke_width_std") not in ("", None)]
        projection_h = [_to_float(r.get("font_horizontal_projection_spread")) for r in rows if r.get("font_horizontal_projection_spread") not in ("", None)]
        projection_v = [_to_float(r.get("font_vertical_projection_spread")) for r in rows if r.get("font_vertical_projection_spread") not in ("", None)]

        aspect_ratio_target = font_aspect
        # Keep separate scale hints conservative: aspect gives only a ratio, not two independent scales.
        ratio_vs_kaishu = font_aspect / kaishu_aspect if kaishu_aspect else 1.0
        horizontal_hint = math.sqrt(max(ratio_vs_kaishu, 1e-9))
        vertical_hint = 1.0 / horizontal_hint if horizontal_hint else 1.0
        confidence = "medium" if style in {"kaishu", "lishu"} else "low"
        if style == "xingkai":
            confidence = "low"

        width_std = _mean(width_std_values, _std(width_values))
        width_cv = width_std / font_width_mean if font_width_mean else 0.0
        current = current_profiles.get(style, {})

        styles[style] = {
            "aspect_ratio_target": _hint(
                aspect_ratio_target,
                "font_bbox/font_aspect",
                confidence,
                "Target aspect from static font outline; not a complete structure model.",
                "mean_font_aspect_ratio",
            ),
            "horizontal_scale_hint": _hint(
                horizontal_hint,
                "font_bbox/font_aspect",
                confidence,
                "Derived as sqrt(style_font_aspect / kaishu_font_aspect); aspect alone cannot uniquely determine X/Y scales.",
                "sqrt(mean_font_aspect_ratio / kaishu_mean_font_aspect_ratio)",
            ),
            "vertical_scale_hint": _hint(
                vertical_hint,
                "font_bbox/font_aspect",
                confidence,
                "Paired inverse of horizontal_scale_hint; use only as a readonly candidate.",
                "1 / horizontal_scale_hint",
            ),
            "base_width_hint": _hint(
                font_width_mean,
                "font_distance_transform",
                "medium",
                "Mean stroke width from font distance transform; needs visual normalization before use.",
                "mean_font_stroke_width",
            ),
            "stroke_width_distribution": {
                "mean": round(font_width_mean, 6),
                "std": round(width_std, 6),
                "cv": round(width_cv, 6),
                "source": "font_distance_transform",
                "method": "mean/std/cv of font_stroke_width statistics",
                "confidence": "medium",
                "notes": "Readonly style width distribution hint; not an execution taper model.",
            },
            "projection_summary": {
                "horizontal_projection_spread_mean": round(_mean(projection_h), 6),
                "horizontal_projection_spread_std": round(_std(projection_h), 6),
                "vertical_projection_spread_mean": round(_mean(projection_v), 6),
                "vertical_projection_spread_std": round(_std(projection_v), 6),
                "source": "font_projection_spread",
                "method": "summary spread only, not full distribution",
                "confidence": "medium",
                "notes": "Only spread hints are available in current font_style_gap_summary.csv.",
            },
            "current_profile_reference": {
                "horizontal_scale": current.get("horizontal_scale"),
                "vertical_scale": current.get("vertical_scale"),
                "trajectory_aspect_ratio": round(trajectory_aspect, 6),
                "trajectory_mean_width": round(trajectory_width, 6),
            },
        }

    if "lishu" in styles and "kaishu" in styles:
        lishu_target = styles["lishu"]["aspect_ratio_target"]["value"]
        kaishu_target = styles["kaishu"]["aspect_ratio_target"]["value"]
        flatness = lishu_target / kaishu_target if kaishu_target else 0.0
        styles["lishu"]["lishu_flatness"] = _hint(
            flatness,
            "font_bbox/font_aspect",
            "medium",
            "Flatness can be estimated globally, but real lishu needs component and stroke-level evidence.",
            "lishu_mean_font_aspect_ratio / kaishu_mean_font_aspect_ratio",
        )

    return {
        "_status": "readonly_estimate_not_used_by_default",
        "_source": source_name,
        "_warning": "not wired into generation pipeline",
        "_scope": "Phase 1 font-outline estimates only; no trajectory generation and no default profile replacement.",
        "styles": styles,
        "unsupported_from_static_font": UNSUPPORTED_FROM_STATIC_FONT,
    }


def build_parameter_comparison(estimates: dict[str, Any], current_profiles: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mapping = [
        ("horizontal_scale", "horizontal_scale_hint"),
        ("vertical_scale", "vertical_scale_hint"),
        ("base_width", "base_width_hint"),
    ]
    for style, style_est in estimates.get("styles", {}).items():
        current = current_profiles.get(style, {})
        for parameter, estimate_key in mapping:
            hint = style_est.get(estimate_key, {})
            current_value = current.get(parameter, "")
            phase1 = hint.get("value", "")
            current_numeric = _to_float(current_value, float("nan"))
            phase1_numeric = _to_float(phase1, float("nan"))
            delta = ""
            if math.isfinite(current_numeric) and math.isfinite(phase1_numeric):
                delta = round(phase1_numeric - current_numeric, 6)
            rows.append(
                {
                    "style": style,
                    "parameter": parameter,
                    "current_value": current_value,
                    "phase1_hint": phase1,
                    "delta": delta,
                    "source": hint.get("source", ""),
                    "confidence": hint.get("confidence", ""),
                    "use_recommendation": "readonly_review_only",
                    "notes": hint.get("notes", ""),
                }
            )
        distribution = style_est.get("stroke_width_distribution", {})
        rows.append(
            {
                "style": style,
                "parameter": "stroke_width_distribution",
                "current_value": "",
                "phase1_hint": json.dumps(
                    {
                        "mean": distribution.get("mean"),
                        "std": distribution.get("std"),
                        "cv": distribution.get("cv"),
                    },
                    ensure_ascii=False,
                ),
                "delta": "",
                "source": distribution.get("source", ""),
                "confidence": distribution.get("confidence", ""),
                "use_recommendation": "readonly_review_only",
                "notes": distribution.get("notes", ""),
            }
        )
        projection = style_est.get("projection_summary", {})
        for parameter, field in [
            ("horizontal_projection_distribution", "horizontal_projection_spread_mean"),
            ("vertical_projection_distribution", "vertical_projection_spread_mean"),
        ]:
            rows.append(
                {
                    "style": style,
                    "parameter": parameter,
                    "current_value": "",
                    "phase1_hint": projection.get(field, ""),
                    "delta": "",
                    "source": projection.get("source", ""),
                    "confidence": projection.get("confidence", ""),
                    "use_recommendation": "readonly_review_only",
                    "notes": projection.get("notes", ""),
                }
            )
        if style == "lishu" and "lishu_flatness" in style_est:
            hint = style_est["lishu_flatness"]
            rows.append(
                {
                    "style": style,
                    "parameter": "lishu_flatness",
                    "current_value": "",
                    "phase1_hint": hint.get("value", ""),
                    "delta": "",
                    "source": hint.get("source", ""),
                    "confidence": hint.get("confidence", ""),
                    "use_recommendation": "readonly_review_only",
                    "notes": hint.get("notes", ""),
                }
            )
    return rows


def build_warnings() -> list[dict[str, str]]:
    rows = []
    for parameter in UNSUPPORTED_FROM_STATIC_FONT:
        rows.append(
            {
                "parameter": parameter,
                "reason": "unsupported_from_static_font",
                "recommendation": "keep as manual/process prior; require trajectory, robot process data, or human feedback",
            }
        )
    return rows


def write_current_vs_phase1_scale(comparison_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = sorted({row["style"] for row in comparison_rows})
    parameters = ["horizontal_scale", "vertical_scale"]
    fig = Figure(figsize=(8, 4), dpi=150)
    ax = fig.add_subplot(111)
    x_positions = range(len(styles))
    width = 0.18
    offsets = [-1.5 * width, -0.5 * width, 0.5 * width, 1.5 * width]
    series = []
    for parameter in parameters:
        current_vals = []
        phase1_vals = []
        for style in styles:
            row = next((r for r in comparison_rows if r["style"] == style and r["parameter"] == parameter), None)
            current_vals.append(_to_float(row.get("current_value") if row else 0.0))
            phase1_vals.append(_to_float(row.get("phase1_hint") if row else 0.0))
        series.append((f"current {parameter}", current_vals))
        series.append((f"phase1 {parameter}", phase1_vals))
    colors = ["#9ecae1", "#08519c", "#fdae6b", "#a63603"]
    for offset, (label, vals), color in zip(offsets, series, colors):
        ax.bar([x + offset for x in x_positions], vals, width=width, label=label, color=color)
    ax.set_xticks(list(x_positions), styles)
    ax.set_ylabel("scale")
    ax.set_title("Current vs Phase 1 scale hints")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path)


def write_current_vs_phase1_width(comparison_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [row for row in comparison_rows if row["parameter"] == "base_width"]
    styles = [row["style"] for row in rows]
    phase1 = [_to_float(row["phase1_hint"]) for row in rows]
    fig = Figure(figsize=(6, 3.5), dpi=150)
    ax = fig.add_subplot(111)
    ax.bar(styles, phase1, color="#756bb1")
    ax.set_ylabel("font stroke width hint")
    ax.set_title("Phase 1 base width hints")
    fig.tight_layout()
    fig.savefig(path)


def write_projection_summary(comparison_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    styles = sorted({row["style"] for row in comparison_rows})
    horizontal = []
    vertical = []
    for style in styles:
        h = next((row for row in comparison_rows if row["style"] == style and row["parameter"] == "horizontal_projection_distribution"), None)
        v = next((row for row in comparison_rows if row["style"] == style and row["parameter"] == "vertical_projection_distribution"), None)
        horizontal.append(_to_float(h.get("phase1_hint") if h else 0.0))
        vertical.append(_to_float(v.get("phase1_hint") if v else 0.0))
    fig = Figure(figsize=(7, 3.6), dpi=150)
    ax = fig.add_subplot(111)
    x_positions = list(range(len(styles)))
    ax.bar([x - 0.18 for x in x_positions], horizontal, width=0.36, label="horizontal spread", color="#31a354")
    ax.bar([x + 0.18 for x in x_positions], vertical, width=0.36, label="vertical spread", color="#addd8e")
    ax.set_xticks(x_positions, styles)
    ax.set_ylabel("projection spread")
    ax.set_title("Phase 1 projection summary")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path)


def write_report(
    path: Path,
    estimates: dict[str, Any],
    comparison_rows: list[dict[str, Any]],
    font_gap_dir: Path,
    output_files: dict[str, str],
) -> None:
    scale_rows = [row for row in comparison_rows if row["parameter"] in {"horizontal_scale", "vertical_scale"}]
    width_rows = [row for row in comparison_rows if row["parameter"] == "base_width"]
    unsupported = estimates["unsupported_from_static_font"]
    lines = [
        "# Phase 1 font-outline style profile readonly estimator",
        "",
        "## 本轮目的",
        "",
        "本轮只读输入数据，产出候选 estimates 和报告；不接默认 style profile，不改变 `run_demo.py` 默认行为，本轮不生成新轨迹。",
        "",
        "## 输入文件",
        "",
        f"- font gap dir: `{font_gap_dir}`",
        "- `font_style_gap_summary.csv`",
        "- `font_style_gap_style_means.csv`",
        "- `style_profiles.json`",
        "",
        "## 输出文件",
        "",
        f"- estimates: `{output_files['estimates_json']}`",
        f"- comparison: `{output_files['comparison_csv']}`",
        f"- warnings: `{output_files['warnings_csv']}`",
        f"- figures: `{output_files['figures_dir']}`",
        "",
        "## 估计参数列表",
        "",
        "- `horizontal_scale_hint` / `vertical_scale_hint`",
        "- `base_width_hint`",
        "- `stroke_width_distribution`",
        "- `projection_summary`",
        "- `lishu_flatness`",
        "",
        "## Current vs Phase 1 关键差异",
        "",
        "| style | parameter | current | phase1_hint | delta | confidence |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in scale_rows + width_rows:
        lines.append(
            f"| {row['style']} | {row['parameter']} | {row['current_value']} | {row['phase1_hint']} | {row['delta']} | {row['confidence']} |"
        )
    lines.extend(
        [
            "",
            "## Lishu 结论",
            "",
            "flatness 可以从字体 aspect 统计中给出低风险提示；但当前 lishu 接近字体 aspect 只说明整体宽扁比例接近，真实隶书结构仍需要 component-level / 笔画级数据。",
            "",
            "## Xingkai 结论",
            "",
            "connectedness 不能直接等价为 connector 数量。connector_trigger、connector_shape 和 connector_width_scale 仍需要人工看图、轨迹数据或执行层反馈。",
            "",
            "## 不支持从静态字体估计的参数",
            "",
        ]
    )
    for parameter in unsupported:
        lines.append(f"- `{parameter}`")
    lines.extend(
        [
            "",
            "## 下一步建议",
            "",
            "- 用 phase1 estimates 生成一批非默认对比图。",
            "- 人工看图后再决定是否升级 style profile。",
            "- 先验证全局比例和宽度，再进入 component-level 结构适配。",
            "",
            "## 边界",
            "",
            "- 字体轮廓不等于真实书写轨迹。",
            "- 静态字体无法给真实速度/压力/抬笔。",
            "- 本轮不生成新轨迹。",
            "- 本轮不接默认，不替换 `style_profiles.json`，不调用 API，不连接 CoppeliaSim/AUBO i5。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_to_paper_figures(result: dict[str, str], output_dir: Path, paper_dir: Path = DEFAULT_PAPER_DIR) -> str:
    paper_dir.mkdir(parents=True, exist_ok=True)
    copies = {
        "style_profile_phase1_estimate_report.md": Path(result["report_md"]),
        "style_profile_phase1_parameter_comparison.csv": Path(result["comparison_csv"]),
        "style_profile_phase1_estimates.json": Path(result["estimates_json"]),
        "current_vs_phase1_scale.png": Path(result["figures_dir"]) / "current_vs_phase1_scale.png",
        "current_vs_phase1_width.png": Path(result["figures_dir"]) / "current_vs_phase1_width.png",
        "phase1_projection_summary.png": Path(result["figures_dir"]) / "phase1_projection_summary.png",
    }
    for name, src in copies.items():
        if src.exists():
            (paper_dir / name).write_bytes(src.read_bytes())
    index_path = paper_dir / "style_profile_phase1_estimates_index.md"
    lines = [
        "# Style Profile Phase 1 Estimates Index",
        "",
        f"- source_output_dir: `{output_dir}`",
        "- scope: readonly font-outline estimates only; no default profile replacement and no trajectory generation.",
        "",
        "| File | Content |",
        "|---|---|",
        "| `style_profile_phase1_estimate_report.md` | Phase 1 只读估计报告 |",
        "| `style_profile_phase1_parameter_comparison.csv` | current profile vs phase1 hints |",
        "| `style_profile_phase1_estimates.json` | readonly estimates JSON |",
        "| `current_vs_phase1_scale.png` | 当前 scale 与 Phase 1 scale hints 对比 |",
        "| `current_vs_phase1_width.png` | Phase 1 base width hints |",
        "| `phase1_projection_summary.png` | 投影 spread summary |",
        "",
        "`style_profile_phase1_estimates.json` 标记为 `readonly_estimate_not_used_by_default`，不接默认生成流程。",
    ]
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(index_path)


def run_style_profile_phase1_estimator(
    font_gap_dir: Path | str = DEFAULT_FONT_GAP_DIR,
    current_profile_path: Path | str = DEFAULT_STYLE_PROFILE,
    output_dir: Path | str | None = None,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    gap_dir = Path(font_gap_dir)
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = DEFAULT_OUTPUT_ROOT / f"style_profile_phase1_estimates_{timestamp}"
    else:
        out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = _read_csv(gap_dir / "font_style_gap_summary.csv")
    style_means_rows = _read_csv(gap_dir / "font_style_gap_style_means.csv")
    current_profiles = load_current_style_profiles(current_profile_path)
    estimates = build_phase1_estimates(summary_rows, style_means_rows, current_profiles, source_name=gap_dir.name)
    comparison_rows = build_parameter_comparison(estimates, current_profiles)
    warning_rows = build_warnings()

    estimates_path = out_dir / "style_profile_phase1_estimates.json"
    comparison_path = out_dir / "style_profile_phase1_parameter_comparison.csv"
    report_path = out_dir / "style_profile_phase1_estimate_report.md"
    warnings_path = out_dir / "style_profile_phase1_estimate_warnings.csv"
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    estimates_path.write_text(json.dumps(estimates, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(comparison_rows, comparison_path)
    _write_csv(warning_rows, warnings_path)
    write_current_vs_phase1_scale(comparison_rows, figures_dir / "current_vs_phase1_scale.png")
    write_current_vs_phase1_width(comparison_rows, figures_dir / "current_vs_phase1_width.png")
    write_projection_summary(comparison_rows, figures_dir / "phase1_projection_summary.png")
    output_files = {
        "estimates_json": str(estimates_path),
        "comparison_csv": str(comparison_path),
        "warnings_csv": str(warnings_path),
        "figures_dir": str(figures_dir),
    }
    write_report(report_path, estimates, comparison_rows, gap_dir, output_files)

    result: dict[str, Any] = {
        "output_dir": str(out_dir),
        "estimates_json": str(estimates_path),
        "comparison_csv": str(comparison_path),
        "report_md": str(report_path),
        "warnings_csv": str(warnings_path),
        "figures_dir": str(figures_dir),
        "style_count": len(estimates.get("styles", {})),
        "comparison_count": len(comparison_rows),
        "unsupported_count": len(warning_rows),
    }
    if copy_to_paper:
        result["paper_index"] = copy_to_paper_figures(result, out_dir)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create readonly Phase 1 style-profile estimates from font outlines.")
    parser.add_argument("--font-gap-dir", default=str(DEFAULT_FONT_GAP_DIR))
    parser.add_argument("--current-profile", default=str(DEFAULT_STYLE_PROFILE))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--no-paper-copy", action="store_true")
    args = parser.parse_args()

    result = run_style_profile_phase1_estimator(
        font_gap_dir=args.font_gap_dir,
        current_profile_path=args.current_profile,
        output_dir=args.out_dir,
        copy_to_paper=not args.no_paper_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
