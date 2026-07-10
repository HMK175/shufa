"""Plan a data-driven upgrade path for style profiles.

This module intentionally does not wire prototype estimates into generation.
It creates a parameter matrix and implementation plan from the recent
font-style-gap analysis so the next round can upgrade style profiles
deliberately instead of continuing ad-hoc connector/taper tuning.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib.figure import Figure


EXP_DIR = Path(__file__).resolve().parents[1]
ROOT = EXP_DIR.parents[1]
DEFAULT_SCHEMA = EXP_DIR / "configs" / "style_profile_parameter_schema.json"
DEFAULT_FONT_GAP_DIR = EXP_DIR / "outputs" / "font_style_gap_analysis_20260618_144838"
DEFAULT_OUTPUT_ROOT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"


def load_parameter_schema(path: Path | str = DEFAULT_SCHEMA) -> list[dict[str, Any]]:
    schema_path = Path(path)
    with schema_path.open(encoding="utf-8") as f:
        rows = json.load(f)
    required = {
        "name",
        "level",
        "current_source",
        "proposed_source",
        "can_estimate_now",
        "required_inputs",
        "priority",
        "implementation_phase",
        "risk",
        "notes",
    }
    for row in rows:
        missing = required - set(row)
        if missing:
            raise ValueError(f"schema row {row.get('name', '<unknown>')} missing {sorted(missing)}")
    return rows


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


def _bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def build_parameter_matrix(schema_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matrix: list[dict[str, Any]] = []
    for row in schema_rows:
        required_inputs = row.get("required_inputs", [])
        if isinstance(required_inputs, list):
            required_inputs_text = "; ".join(str(item) for item in required_inputs)
        else:
            required_inputs_text = str(required_inputs)
        matrix.append(
            {
                "parameter": row["name"],
                "level": row["level"],
                "current_source": row["current_source"],
                "proposed_source": row["proposed_source"],
                "can_estimate_now": _bool_text(row["can_estimate_now"]),
                "required_inputs": required_inputs_text,
                "priority": row["priority"],
                "implementation_phase": row["implementation_phase"],
                "risk": row["risk"],
                "notes": row["notes"],
            }
        )
    return matrix


def build_recommendations(schema_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_phase: dict[str, list[str]] = {"phase_1": [], "phase_2": [], "phase_3": []}
    for row in schema_rows:
        phase = str(row["implementation_phase"])
        if phase in by_phase:
            by_phase[phase].append(str(row["name"]))

    do_not = [
        str(row["name"])
        for row in schema_rows
        if row["proposed_source"] in {"process_prior", "unsupported"}
        or row["name"] in {"pen_up_height", "speed_scale", "pressure_curve"}
    ]
    do_not.extend(["real_robot_dynamics"])
    do_not_unique = sorted(dict.fromkeys(do_not))

    return {
        "phase_1": {
            "goal": "font-outline-derived global shape and width parameters",
            "parameters": by_phase["phase_1"],
        },
        "phase_2": {
            "goal": "char-level and component-level shape adaptation",
            "parameters": by_phase["phase_2"],
        },
        "phase_3": {
            "goal": "process priors from trajectories, robot constraints, or human feedback",
            "parameters": by_phase["phase_3"],
        },
        "do_not_estimate_from_static_font": do_not_unique,
    }


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_prototype_estimates(style_means_rows: list[dict[str, str]], source_name: str) -> dict[str, Any]:
    styles: dict[str, Any] = {}
    for row in style_means_rows:
        style = row.get("style", "")
        if not style:
            continue
        font_aspect = _to_float(row.get("mean_font_aspect_ratio"), 1.0)
        traj_aspect = _to_float(row.get("mean_trajectory_aspect_ratio"), 1.0)
        font_width = _to_float(row.get("mean_font_stroke_width"), 0.0)
        traj_width = _to_float(row.get("mean_trajectory_mean_width"), 0.0)
        font_components = _to_float(row.get("mean_font_connected_component_count"), 0.0)
        traj_connections = _to_float(row.get("mean_trajectory_connection_count"), 0.0)
        styles[style] = {
            "mean_font_aspect_ratio": round(font_aspect, 6),
            "mean_trajectory_aspect_ratio": round(traj_aspect, 6),
            "aspect_ratio_delta": round(font_aspect - traj_aspect, 6),
            "horizontal_scale_hint": round(font_aspect, 6),
            "vertical_scale_hint": round(1.0 / font_aspect if font_aspect else 0.0, 6),
            "mean_font_stroke_width": round(font_width, 6),
            "trajectory_mean_width": round(traj_width, 6),
            "stroke_width_ratio_hint": round(font_width / traj_width if traj_width else 0.0, 6),
            "connectedness_hint": {
                "mean_font_connected_component_count": round(font_components, 6),
                "mean_trajectory_connection_count": round(traj_connections, 6),
                "note": "weak correspondence only; do not map directly to connector_count",
            },
        }
    return {
        "_status": "prototype_not_used_by_default",
        "_source": source_name,
        "_warning": "not wired into generation pipeline",
        "styles": styles,
    }


def _phase_order(phase: str) -> int:
    return {"phase_1": 1, "phase_2": 2, "phase_3": 3}.get(phase, 99)


def write_parameter_source_matrix(matrix_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    phases = ["phase_1", "phase_2", "phase_3"]
    source_order = ["font_outline", "makemeahanzi_median", "visual_feedback", "process_prior", "unsupported"]
    counts: dict[tuple[str, str], int] = Counter(
        (str(row["implementation_phase"]), str(row["proposed_source"])) for row in matrix_rows
    )
    data = [[counts.get((phase, source), 0) for source in source_order] for phase in phases]

    fig = Figure(figsize=(8, 3.6), dpi=150)
    ax = fig.add_subplot(111)
    image = ax.imshow(data, cmap="Blues")
    ax.set_xticks(range(len(source_order)), labels=source_order, rotation=30, ha="right")
    ax.set_yticks(range(len(phases)), labels=phases)
    ax.set_title("Parameter source matrix")
    for y, row in enumerate(data):
        for x, value in enumerate(row):
            ax.text(x, y, str(value), ha="center", va="center", color="#111111")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path)


def write_upgrade_priority_chart(matrix_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    priority_order = ["high", "medium", "low"]
    phases = ["phase_1", "phase_2", "phase_3"]
    counts: dict[tuple[str, str], int] = Counter((str(row["implementation_phase"]), str(row["priority"])) for row in matrix_rows)

    fig = Figure(figsize=(7.5, 3.8), dpi=150)
    ax = fig.add_subplot(111)
    bottom = [0] * len(phases)
    colors = {"high": "#2b8cbe", "medium": "#a6bddb", "low": "#ece7f2"}
    for priority in priority_order:
        values = [counts.get((phase, priority), 0) for phase in phases]
        ax.bar(phases, values, bottom=bottom, color=colors[priority], label=priority)
        bottom = [a + b for a, b in zip(bottom, values)]
    ax.set_ylabel("parameter count")
    ax.set_title("Upgrade priority by phase")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path)


def write_report(
    path: Path,
    matrix_rows: list[dict[str, Any]],
    recommendations: dict[str, Any],
    prototype: dict[str, Any],
    font_gap_dir: Path,
) -> None:
    total = len(matrix_rows)
    now_count = sum(1 for row in matrix_rows if str(row["can_estimate_now"]).lower() == "true")
    by_level = Counter(str(row["level"]) for row in matrix_rows)
    by_phase = Counter(str(row["implementation_phase"]) for row in matrix_rows)
    phase_1 = recommendations["phase_1"]["parameters"]
    phase_2 = recommendations["phase_2"]["parameters"]
    phase_3 = recommendations["phase_3"]["parameters"]
    do_not = recommendations["do_not_estimate_from_static_font"]

    lines = [
        "# Style profile 数据化升级方案设计与参数分层表",
        "",
        "## 本轮目的",
        "",
        "本轮不是直接替换生成算法，而是基于 font style gap analysis 建立参数分层、数据来源、估计方法和后续实现计划。",
        "本轮不调 connector/taper，不替换默认 style profile，不改变 `run_demo.py` 默认行为。",
        "",
        "## 为什么不能继续只靠 MakeMeAHanzi + 全局参数细调",
        "",
        "- 当前行楷容易表现为“楷书骨架 + connector”。",
        "- 当前隶书容易表现为“楷书骨架 + 横向拉宽/纵向压扁”。",
        "- stroke taper 是 execution 层的视觉效果，不是真实字体风格来源。",
        "- font gap analysis 已提示：下一步应从字体/图像统计中系统估计风格参数，而不是继续盲调 connector/taper。",
        "",
        "## 输入依据",
        "",
        f"- font gap dir: `{font_gap_dir}`",
        "- `font_style_gap_summary.csv`",
        "- `font_style_gap_style_means.csv`",
        "- `style_profiles.json`",
        "- `style_sources.json`",
        "- `execution_refinement_profiles.json`",
        "",
        "## 参数分层概览",
        "",
        f"- total parameters: `{total}`",
        f"- can_estimate_now: `{now_count}`",
    ]
    for level, count in sorted(by_level.items()):
        lines.append(f"- {level}: `{count}`")
    lines.extend(["", "## 实现阶段概览", ""])
    for phase, count in sorted(by_phase.items(), key=lambda item: _phase_order(item[0])):
        lines.append(f"- {phase}: `{count}`")

    lines.extend(
        [
            "",
            "## 参数来源矩阵",
            "",
            "完整表见 `style_profile_parameter_matrix.csv`。核心字段包括：parameter、level、current_source、proposed_source、can_estimate_now、required_inputs、priority、implementation_phase、risk、notes。",
            "",
            "## 三阶段升级路线",
            "",
            "### Phase 1：现在就能做、风险较低",
            "",
            "目标：font-outline-derived global and width parameters。",
        ]
    )
    for param in phase_1:
        lines.append(f"- `{param}`")
    lines.extend(["", "### Phase 2：中等复杂度，需要设计映射", ""])
    for param in phase_2:
        lines.append(f"- `{param}`")
    lines.extend(["", "### Phase 3：静态字体难直接估计，需要轨迹或人工反馈", ""])
    for param in phase_3:
        lines.append(f"- `{param}`")
    lines.extend(["", "## 本轮不要再盲调的参数", ""])
    for param in ["connector_trigger", "connector_shape", "connector_width_scale", "stroke_start_width_scale", "stroke_mid_width_scale", "stroke_end_width_scale"]:
        lines.append(f"- `{param}`")
    lines.extend(["", "## 不能从静态字体直接估计", ""])
    for param in do_not:
        lines.append(f"- `{param}`")

    lines.extend(
        [
            "",
            "## Prototype estimates",
            "",
            "`prototype_style_profile_estimates.json` 只给出 style-level hints，例如 aspect ratio、stroke width 和 connectedness 的弱提示。",
            "prototype 不接入默认流程，不会被 `run_demo.py` 或当前生成链路读取。",
            f"- status: `{prototype.get('_status')}`",
            f"- warning: `{prototype.get('_warning')}`",
            "",
            "## 人工看图参与点",
            "",
            "- Phase 1 的全局比例和宽度估计需要配合字体网格图、gap 图人工看图确认。",
            "- Phase 2 的 component/char-level 参数必须经过代表样本和异常样本人工校验。",
            "- Phase 3 的 connector/taper/pressure/speed 不应只靠数值表，需要继续保留人工看图和执行层诊断。",
            "",
            "## 边界",
            "",
            "- 字体轮廓不等于真实书写轨迹。",
            "- 静态字体不能直接给速度、抬笔高度、真实压力或机器人动态控制。",
            "- prototype 不接入默认流程。",
            "- 本轮不调用 API，不连接 CoppeliaSim/AUBO i5，不做 IK/SDK/机器人命令。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def copy_to_paper_figures(result: dict[str, str], output_dir: Path, paper_dir: Path = DEFAULT_PAPER_DIR) -> str:
    paper_dir.mkdir(parents=True, exist_ok=True)
    copies = {
        "style_profile_upgrade_plan.md": Path(result["report_md"]),
        "style_profile_parameter_matrix.csv": Path(result["matrix_csv"]),
        "style_profile_upgrade_recommendations.json": Path(result["recommendations_json"]),
        "parameter_source_matrix.png": Path(result["figures_dir"]) / "parameter_source_matrix.png",
        "upgrade_priority_chart.png": Path(result["figures_dir"]) / "upgrade_priority_chart.png",
    }
    for name, src in copies.items():
        if src.exists():
            (paper_dir / name).write_bytes(src.read_bytes())
    index_path = paper_dir / "style_profile_upgrade_plan_index.md"
    index_lines = [
        "# Style Profile Upgrade Plan Index",
        "",
        f"- source_output_dir: `{output_dir}`",
        "- scope: parameter layering and data-source plan only; no default style profile replacement.",
        "",
        "| File | Content |",
        "|---|---|",
        "| `style_profile_upgrade_plan.md` | 数据化升级方案报告 |",
        "| `style_profile_parameter_matrix.csv` | 参数分层与来源矩阵 |",
        "| `style_profile_upgrade_recommendations.json` | 三阶段升级建议 |",
        "| `parameter_source_matrix.png` | 参数来源矩阵图 |",
        "| `upgrade_priority_chart.png` | 分阶段优先级图 |",
        "",
        "prototype estimates 若生成，只是候选提示，不接入默认流程。字体轮廓不等于真实书写轨迹，仍需人工看图校验。",
    ]
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    return str(index_path)


def run_style_profile_upgrade_plan(
    font_gap_dir: Path | str = DEFAULT_FONT_GAP_DIR,
    schema_path: Path | str = DEFAULT_SCHEMA,
    output_dir: Path | str | None = None,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    gap_dir = Path(font_gap_dir)
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = DEFAULT_OUTPUT_ROOT / f"style_profile_upgrade_plan_{timestamp}"
    else:
        out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_rows = load_parameter_schema(schema_path)
    matrix_rows = build_parameter_matrix(schema_rows)
    recommendations = build_recommendations(schema_rows)
    style_means_rows = _read_csv(gap_dir / "font_style_gap_style_means.csv")
    prototype = build_prototype_estimates(style_means_rows, source_name=gap_dir.name)

    matrix_path = out_dir / "style_profile_parameter_matrix.csv"
    recommendations_path = out_dir / "style_profile_upgrade_recommendations.json"
    prototype_path = out_dir / "prototype_style_profile_estimates.json"
    report_path = out_dir / "style_profile_upgrade_plan.md"
    figures_dir = out_dir / "figures"

    _write_csv(matrix_rows, matrix_path)
    recommendations_path.write_text(json.dumps(recommendations, ensure_ascii=False, indent=2), encoding="utf-8")
    prototype_path.write_text(json.dumps(prototype, ensure_ascii=False, indent=2), encoding="utf-8")
    write_parameter_source_matrix(matrix_rows, figures_dir / "parameter_source_matrix.png")
    write_upgrade_priority_chart(matrix_rows, figures_dir / "upgrade_priority_chart.png")
    write_report(report_path, matrix_rows, recommendations, prototype, gap_dir)

    result: dict[str, Any] = {
        "output_dir": str(out_dir),
        "matrix_csv": str(matrix_path),
        "recommendations_json": str(recommendations_path),
        "prototype_json": str(prototype_path),
        "report_md": str(report_path),
        "figures_dir": str(figures_dir),
        "parameter_count": len(matrix_rows),
        "can_estimate_now_count": sum(1 for row in matrix_rows if row["can_estimate_now"] == "true"),
        "phase_1_count": len(recommendations["phase_1"]["parameters"]),
        "phase_2_count": len(recommendations["phase_2"]["parameters"]),
        "phase_3_count": len(recommendations["phase_3"]["parameters"]),
    }
    if copy_to_paper:
        result["paper_index"] = copy_to_paper_figures(result, out_dir)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a style profile data-upgrade plan.")
    parser.add_argument("--font-gap-dir", default=str(DEFAULT_FONT_GAP_DIR))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--no-paper-copy", action="store_true")
    args = parser.parse_args()

    result = run_style_profile_upgrade_plan(
        font_gap_dir=args.font_gap_dir,
        schema_path=args.schema,
        output_dir=args.out_dir,
        copy_to_paper=not args.no_paper_copy,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
