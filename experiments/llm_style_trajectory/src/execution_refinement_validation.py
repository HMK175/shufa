"""Validate candidate_default_v1 on a broader set of execution samples."""

from __future__ import annotations

import argparse
import csv
import json
import math
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
DEFAULT_SUMMARY_CSV = EXP_DIR / "outputs" / "style_diagnostics_20260617_200746" / "style_diagnostic_summary.csv"
DEFAULT_CANDIDATES_CSV = EXP_DIR / "outputs" / "style_visual_audit_20260617_224321" / "visual_audit_candidates.csv"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"

DEFAULT_TARGET_PAIRS = [
    ("国", "xingkai"),
    ("德", "xingkai"),
    ("福", "xingkai"),
    ("和", "xingkai"),
    ("中", "xingkai"),
    ("人", "xingkai"),
    ("明", "xingkai"),
    ("林", "xingkai"),
    ("人", "kaishu"),
    ("人", "lishu"),
    ("中", "kaishu"),
    ("中", "lishu"),
    ("好", "lishu"),
    ("风", "lishu"),
]

SUMMARY_FIELDS = [
    "char",
    "style",
    "source_output_dir",
    "baseline_execution_csv",
    "refined_execution_csv",
    "before_connection_count",
    "after_connection_count",
    "before_connector_draw_length",
    "after_connector_draw_length",
    "before_stroke_width_range",
    "after_stroke_width_range",
    "before_stroke_pressure_range",
    "after_stroke_pressure_range",
    "after_has_connector",
    "connector_reduction_ratio",
    "path_length_delta",
    "kaishu_lishu_connector_violation",
    "needs_user_review",
    "review_focus",
    "before_after_png",
    "connector_overlay_png",
    "width_pressure_png",
]

MANIFEST_FIELDS = [
    "char",
    "style",
    "figure_type",
    "figure_path",
    "source_output_dir",
    "needs_user_review",
    "review_focus",
]

FAILURE_FIELDS = ["char", "style", "reason", "source_output_dir"]


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
        parsed: dict[str, Any] = {}
        for key, value in row.items():
            parsed[key] = _safe_float(value) if key in numeric else value
        rows.append(parsed)
    return rows


def _case_id(char: str, style: str) -> str:
    return f"u{ord(char):04x}_{style}"


def load_candidate_default(profile_path: Path | str = DEFAULT_REFINEMENT_PROFILE) -> dict[str, Any]:
    profiles = load_refinement_profiles(profile_path)
    candidate = profiles["candidate_defaults"]["candidate_default_v1"]
    connector_rule_name = str(candidate["connector_rule"])
    stroke_profile_name = str(candidate["stroke_width_profile"])
    return {
        "name": "candidate_default_v1",
        "connector_rule_name": connector_rule_name,
        "stroke_width_profile_name": stroke_profile_name,
        "connector_rule": profiles["connector_rules"][connector_rule_name],
        "stroke_width_profile": profiles["stroke_width_profiles"][stroke_profile_name],
        "visualization": profiles.get("visualization", {}),
        "status": candidate.get("status", ""),
        "human_feedback": candidate.get("human_feedback", ""),
    }


def _summary_index(summary_csv: Path) -> dict[tuple[str, str], dict[str, str]]:
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in _read_csv(summary_csv):
        if str(row.get("success", "")).lower() not in {"true", "1", "yes"}:
            continue
        key = (row.get("char", ""), row.get("style", ""))
        if key[0] and key[1] and key not in out:
            out[key] = row
    return out


def _candidate_pairs(candidates_csv: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in _read_csv(candidates_csv):
        key = (row.get("char", ""), row.get("style", ""))
        if key[0] and key[1] and key not in seen:
            pairs.append(key)
            seen.add(key)
    return pairs


def select_validation_samples(
    *,
    summary_csv: Path = DEFAULT_SUMMARY_CSV,
    candidates_csv: Path = DEFAULT_CANDIDATES_CSV,
    target_pairs: Sequence[tuple[str, str]] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    index = _summary_index(summary_csv)
    ordered_pairs = list(target_pairs or DEFAULT_TARGET_PAIRS)
    for pair in _candidate_pairs(candidates_csv):
        if pair not in ordered_pairs and len(ordered_pairs) < 18:
            ordered_pairs.append(pair)

    selected: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    for char, style in ordered_pairs:
        row = index.get((char, style))
        if row is None:
            failures.append({"char": char, "style": style, "reason": "sample_not_found", "source_output_dir": ""})
            continue
        selected.append(row)
    return selected, failures


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
    ax.set_title(title, fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlim(0, 256)
    ax.set_ylim(256, 0)
    ax.set_facecolor(DEFAULT_BACKGROUND_COLOR)
    ax.grid(True, color="#d8d8d0", linewidth=0.35, alpha=0.7)
    ax.set_xticks([])
    ax.set_yticks([])
    seen: set[str] = set()
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
        ax.plot(x, y, color=color, linewidth=linewidth, alpha=alpha, linestyle=linestyle, solid_capstyle="round", label=label if label not in seen else None)
        seen.add(label)
    if seen:
        ax.legend(loc="lower right", fontsize=6, framealpha=0.86)


def _write_before_after(before: Sequence[dict[str, Any]], after: Sequence[dict[str, Any]], path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.8), dpi=160)
    fig.patch.set_facecolor(DEFAULT_BACKGROUND_COLOR)
    _draw_overlay(axes[0], before, "before")
    _draw_overlay(axes[1], after, f"after {title}")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_connector_overlay(after: Sequence[dict[str, Any]], path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(4.1, 4.1), dpi=160)
    fig.patch.set_facecolor(DEFAULT_BACKGROUND_COLOR)
    _draw_overlay(ax, after, title)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _value_range(rows: Sequence[dict[str, Any]], field: str) -> tuple[float, float]:
    values = [
        _safe_float(row.get(field))
        for row in rows
        if int(_safe_float(row.get("pen_down"))) == 1 and str(row.get("segment_type")) != "pen_up_move"
    ]
    if not values:
        return 0.0, 1.0
    low, high = min(values), max(values)
    if abs(high - low) < 1e-9:
        return low - 0.5, high + 0.5
    return low, high


def _review_focus(char: str, style: str, before: dict[str, Any], after: dict[str, Any], violation: bool) -> str:
    if style == "xingkai":
        if int(after["connection_count"]) == 0:
            return "人工看图：确认 candidate_default_v1 是否过于保守，connector 是否太少。"
        return "人工看图：确认 connector 是否从过多变为自然少量连接。"
    if violation:
        return "必须检查：kaishu/lishu 不应出现 connector。"
    return "人工看图：确认 stroke taper 是否可见，且非行楷仍无 connector。"


def _row_for_sample(
    *,
    sample: dict[str, str],
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    baseline_csv: Path,
    refined_csv: Path,
    before_after_png: Path,
    connector_overlay_png: Path,
    width_pressure_png: Path,
) -> dict[str, Any]:
    before = execution_refinement_metrics(before_rows)
    after = execution_refinement_metrics(after_rows)
    before_count = int(before["connection_count"])
    after_count = int(after["connection_count"])
    reduction_ratio = (before_count - after_count) / before_count if before_count else 0.0
    style = sample.get("style", "")
    violation = style in {"kaishu", "lishu"} and after_count > 0
    return {
        "char": sample.get("char", ""),
        "style": style,
        "source_output_dir": sample.get("output_dir", ""),
        "baseline_execution_csv": str(baseline_csv),
        "refined_execution_csv": str(refined_csv),
        "before_connection_count": before_count,
        "after_connection_count": after_count,
        "before_connector_draw_length": before["connector_draw_length"],
        "after_connector_draw_length": after["connector_draw_length"],
        "before_stroke_width_range": before["stroke_width_range"],
        "after_stroke_width_range": after["stroke_width_range"],
        "before_stroke_pressure_range": before["stroke_pressure_range"],
        "after_stroke_pressure_range": after["stroke_pressure_range"],
        "after_has_connector": after_count > 0,
        "connector_reduction_ratio": round(reduction_ratio, 6),
        "path_length_delta": round(float(after["path_length"]) - float(before["path_length"]), 3),
        "kaishu_lishu_connector_violation": violation,
        "needs_user_review": True,
        "review_focus": _review_focus(sample.get("char", ""), style, before, after, violation),
        "before_after_png": str(before_after_png),
        "connector_overlay_png": str(connector_overlay_png),
        "width_pressure_png": str(width_pressure_png),
    }


def _write_report(
    *,
    path: Path,
    output_dir: Path,
    rows: Sequence[dict[str, Any]],
    failures: Sequence[dict[str, Any]],
    candidate: dict[str, Any],
) -> None:
    xingkai = [row for row in rows if row["style"] == "xingkai"]
    non_xingkai = [row for row in rows if row["style"] in {"kaishu", "lishu"}]
    violations = [row for row in rows if str(row["kaishu_lishu_connector_violation"]) == "True" or row["kaishu_lishu_connector_violation"] is True]
    xingkai_with_connector = [row for row in xingkai if int(row["after_connection_count"]) > 0]
    avg_reduction = (
        sum(float(row["connector_reduction_ratio"]) for row in xingkai) / len(xingkai)
        if xingkai
        else 0.0
    )
    lines = [
        "# candidate_default_v1 多样本验证",
        "",
        "## 本轮目的",
        "",
        "本轮只验证 `candidate_default_v1`，不继续调参，不新增 balanced 档，不替换全局默认。",
        "目标是把已有人看图认可的 conservative connector + simple_taper 应用到更多样本，检查它是否适合作为后续默认 execution layer 候选。",
        "",
        "## 输入与输出",
        "",
        f"- output_dir: `{output_dir}`",
        f"- candidate_default: `{candidate['name']}`",
        f"- connector_rule: `{candidate['connector_rule_name']}`",
        f"- stroke_width_profile: `{candidate['stroke_width_profile_name']}`",
        f"- status: `{candidate.get('status')}`",
        "",
        "## 样本统计",
        "",
        f"- selected_count: `{len(rows) + len(failures)}`",
        f"- success_count: `{len(rows)}`",
        f"- failure_count: `{len(failures)}`",
        f"- xingkai_success_count: `{len(xingkai)}`",
        f"- non_xingkai_success_count: `{len(non_xingkai)}`",
        "",
        "## 核心判断",
        "",
        f"- xingkai connector 平均 reduction_ratio: `{round(avg_reduction, 6)}`",
        f"- xingkai after 仍保留 connector 的样本数: `{len(xingkai_with_connector)}` / `{len(xingkai)}`",
        f"- kaishu/lishu connector violation: `{len(violations)}`",
        "- stroke taper 是否生效：看 `after_stroke_width_range` 与 `after_stroke_pressure_range` 是否大于 before。",
        "",
        "## before/after 指标表",
        "",
        "| char | style | conn before | conn after | connector length before | connector length after | stroke width range before | stroke width range after | violation |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {char} | {style} | {bc} | {ac} | {bl} | {al} | {bw} | {aw} | {viol} |".format(
                char=row["char"],
                style=row["style"],
                bc=row["before_connection_count"],
                ac=row["after_connection_count"],
                bl=row["before_connector_draw_length"],
                al=row["after_connector_draw_length"],
                bw=row["before_stroke_width_range"],
                aw=row["after_stroke_width_range"],
                viol=row["kaishu_lishu_connector_violation"],
            )
        )
    lines.extend(["", "## 需要人工看图的样本", ""])
    for row in rows:
        lines.append(f"- {row['char']} / {row['style']}: `{row['before_after_png']}`；{row['review_focus']}")
    if failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- {row['char']} / {row['style']}: {row['reason']}" for row in failures)
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- candidate_default_v1 不是全局默认。",
            "- 本轮不继续调参，不新增 balanced 档。",
            "- 本轮不解决 lishu 真实风格来源问题。",
            "- 本轮不代表真实笔刷模型。",
            "- 本轮不调用 API，不连接 CoppeliaSim，不连接 AUBO i5，不调用 SDK，不发送机器人命令。",
            "",
            "## 下一步建议",
            "",
            "- 如果用户觉得 connector 太少，再设计 balanced 档。",
            "- 如果用户接受本轮多样本图，可以下一轮考虑把 candidate_default_v1 接入默认 execution 层或论文 refined baseline。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _copy_to_paper(result: dict[str, Any], paper_dir: Path = DEFAULT_PAPER_DIR) -> Path:
    paper_dir.mkdir(parents=True, exist_ok=True)
    for key in ["report_md", "summary_csv"]:
        source = Path(result[key])
        if source.exists():
            shutil.copy2(source, paper_dir / source.name)
    copied: list[str] = []
    for row in result["summary_rows"][:5]:
        source = Path(row["before_after_png"])
        if source.exists():
            dest = paper_dir / f"execution_refinement_validation_{source.name}"
            shutil.copy2(source, dest)
            copied.append(dest.name)
    index = paper_dir / "execution_refinement_validation_index.md"
    index.write_text(
        "\n".join(
            [
                "# Execution Refinement Validation Index",
                "",
                f"- source_output_dir: `{result['output_dir']}`",
                "- candidate: `candidate_default_v1`",
                "- scope: multi-sample validation only; no parameter tuning, no API, no CoppeliaSim, no AUBO i5.",
                "",
                "| File | Content |",
                "|---|---|",
                "| `execution_refinement_validation_report.md` | 多样本验证报告 |",
                "| `execution_refinement_validation_summary.csv` | before/after 指标汇总 |",
                *[f"| `{name}` | 代表性 before/after 图 |" for name in copied],
                "",
                "这些图等待人工看图反馈；candidate_default_v1 仍不是全局默认。",
            ]
        ),
        encoding="utf-8",
    )
    return index


def run_execution_refinement_validation(
    *,
    summary_csv: Path = DEFAULT_SUMMARY_CSV,
    candidates_csv: Path = DEFAULT_CANDIDATES_CSV,
    output_dir: Path | None = None,
    profile_path: Path = DEFAULT_REFINEMENT_PROFILE,
    target_pairs: Sequence[tuple[str, str]] | None = None,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT / f"execution_refinement_validation_{timestamp}"
    figures_dir = out_dir / "figures"
    cases_dir = out_dir / "cases"
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    cases_dir.mkdir(parents=True, exist_ok=True)

    candidate = load_candidate_default(profile_path)
    selected, failures = select_validation_samples(
        summary_csv=Path(summary_csv),
        candidates_csv=Path(candidates_csv),
        target_pairs=target_pairs,
    )
    visual_cfg = candidate.get("visualization", {})

    summary_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for sample in selected:
        char = sample.get("char", "")
        style = sample.get("style", "")
        source_execution = Path(sample.get("execution_trajectory_csv") or Path(sample.get("output_dir", "")) / "execution_trajectory.csv")
        if not source_execution.exists():
            failures.append(
                {
                    "char": char,
                    "style": style,
                    "reason": "execution_trajectory_not_found",
                    "source_output_dir": sample.get("output_dir", ""),
                }
            )
            continue
        before_rows = _read_execution_csv(source_execution)
        after_rows = refine_execution_rows(
            before_rows,
            style=style,
            style_modifiers={"connection_preference": "weak"},
            connector_rule=candidate["connector_rule"],
            stroke_width_profile=candidate["stroke_width_profile"],
        )

        sample_id = _case_id(char, style)
        sample_dir = cases_dir / sample_id
        baseline_csv = sample_dir / "baseline_execution_trajectory.csv"
        refined_csv = sample_dir / "candidate_default_v1_execution_trajectory.csv"
        write_execution_csv(before_rows, baseline_csv)
        write_execution_csv(after_rows, refined_csv)

        before_after = figures_dir / f"before_after_{sample_id}.png"
        overlay = figures_dir / f"connector_overlay_{sample_id}.png"
        width_pressure = figures_dir / f"width_pressure_{sample_id}.png"
        title_suffix = "candidate_default_v1"
        if style in {"kaishu", "lishu"}:
            title_suffix += " / no connector expected"
        _write_before_after(before_rows, after_rows, before_after, title_suffix)
        _write_connector_overlay(after_rows, overlay, title_suffix)
        render_width_pressure_figure(
            after_rows,
            width_pressure,
            value_mode="width",
            normalization="candidate_default_v1",
            value_range=_value_range(after_rows, "width"),
            title=f"candidate_default_v1 width {sample_id}",
            background_color=str(visual_cfg.get("background_color", DEFAULT_BACKGROUND_COLOR)),
            stroke_light_color=str(visual_cfg.get("stroke_light_color", DEFAULT_STROKE_LIGHT_COLOR)),
            stroke_dark_color=str(visual_cfg.get("stroke_dark_color", DEFAULT_STROKE_DARK_COLOR)),
            connector_light_color=str(visual_cfg.get("connector_light_color", DEFAULT_CONNECTOR_LIGHT_COLOR)),
            connector_dark_color=str(visual_cfg.get("connector_dark_color", DEFAULT_CONNECTOR_DARK_COLOR)),
            pen_up_color=str(visual_cfg.get("pen_up_color", DEFAULT_PEN_UP_COLOR)),
            min_alpha=float(visual_cfg.get("min_alpha", DEFAULT_MIN_ALPHA)),
            min_visible_linewidth=float(visual_cfg.get("min_visible_linewidth", DEFAULT_MIN_VISIBLE_LINEWIDTH)),
        )
        summary_row = _row_for_sample(
            sample=sample,
            before_rows=before_rows,
            after_rows=after_rows,
            baseline_csv=baseline_csv,
            refined_csv=refined_csv,
            before_after_png=before_after,
            connector_overlay_png=overlay,
            width_pressure_png=width_pressure,
        )
        summary_rows.append(summary_row)
        for figure_type, path in [
            ("before_after", before_after),
            ("connector_overlay", overlay),
            ("width_pressure", width_pressure),
        ]:
            manifest_rows.append(
                {
                    "char": char,
                    "style": style,
                    "figure_type": figure_type,
                    "figure_path": str(path),
                    "source_output_dir": sample.get("output_dir", ""),
                    "needs_user_review": True,
                    "review_focus": summary_row["review_focus"],
                }
            )

    summary_out = out_dir / "execution_refinement_validation_summary.csv"
    report_md = out_dir / "execution_refinement_validation_report.md"
    manifest_csv = out_dir / "execution_refinement_validation_manifest.csv"
    failures_csv = out_dir / "execution_refinement_validation_failures.csv"
    _write_csv(summary_out, summary_rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_csv(failures_csv, failures, FAILURE_FIELDS)
    _write_report(path=report_md, output_dir=out_dir, rows=summary_rows, failures=failures, candidate=candidate)

    result: dict[str, Any] = {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_out),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "failures_csv": str(failures_csv),
        "figures_dir": str(figures_dir),
        "success_count": len(summary_rows),
        "failure_count": len(failures),
        "summary_rows": summary_rows,
    }
    if copy_to_paper:
        result["paper_index"] = str(_copy_to_paper(result))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate candidate_default_v1 execution refinement on multiple samples.")
    parser.add_argument("--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV)
    parser.add_argument("--candidates-csv", type=Path, default=DEFAULT_CANDIDATES_CSV)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=DEFAULT_REFINEMENT_PROFILE)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    args = parser.parse_args()
    result = run_execution_refinement_validation(
        summary_csv=args.summary_csv,
        candidates_csv=args.candidates_csv,
        output_dir=args.out_dir,
        profile_path=args.profile,
        copy_to_paper=not args.no_copy_to_paper,
    )
    printable = {key: value for key, value in result.items() if key != "summary_rows"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
