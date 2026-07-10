"""Build a fixed mini-paper figure/table pack from existing outputs.

This module only copies, renames, and indexes existing experiment artifacts.
It does not run generation experiments, call APIs, connect simulators, or touch
robot SDKs.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PAPER_FIGURES_DIR = (
    REPO_ROOT / "experiments" / "llm_style_trajectory" / "outputs" / "paper_figures"
)
DEFAULT_OUT_DIR = DEFAULT_PAPER_FIGURES_DIR / "mini_paper_figures"


@dataclass(frozen=True)
class FigureSpec:
    figure_id: str
    filename: str
    source_candidates: tuple[str, ...]
    source_experiment: str
    paper_section: str
    caption_draft: str
    needs_manual_check: str
    notes: str
    supplementary: bool = False


@dataclass(frozen=True)
class TableSpec:
    table_id: str
    filename: str
    source_path: str
    paper_section: str
    caption_draft: str
    notes: str


FIGURE_SPECS = [
    FigureSpec(
        "fig2a",
        "fig2_modifier_control_connection.png",
        (
            "batch_20260613_154131/modifier_ablation_u5c71.png",
            "batch_20260613_092733/modifier_ablation_u5c71.png",
            "batch_20260611_210502/modifier_ablation_u5c71.png",
        ),
        "modifier connection ablation",
        "自然语言约束有效性",
        "Modifier connection control: none / weak / normal for xingkai 山.",
        "yes",
        "重点人工看 weak / normal connector 是否自然。",
    ),
    FigureSpec(
        "fig2b",
        "fig2_modifier_control_shape.png",
        ("batch_20260613_085440/modifier_ablation_shape_u4e2d.png",),
        "modifier shape ablation",
        "自然语言约束有效性",
        "Modifier shape control: normal / flatter / wider for lishu 中.",
        "yes",
        "重点人工看 lishu 是否只是横向拉宽。",
    ),
    FigureSpec(
        "fig2c",
        "fig2_modifier_control_smoothness.png",
        ("batch_20260613_085440/modifier_ablation_smoothness_u6c38.png",),
        "modifier smoothness ablation",
        "自然语言约束有效性",
        "Modifier smoothness control for kaishu/yong and conservative xingkai.",
        "yes",
        "mean_turning 不够敏感，人工看转折和整体观感。",
    ),
    FigureSpec(
        "fig3a",
        "fig3_xingkai_connector_levels_u56fd.png",
        ("xingkai_balanced_experiment_20260618_141424/figures/compare_connector_levels_u56fd_xingkai.png",),
        "xingkai balanced connector experiment",
        "行楷 connector rule ablation",
        "Xingkai 国 connector levels: all-adjacent baseline, conservative v1, balanced v2.",
        "yes",
        "重点人工看 all-adjacent 是否过多、balanced 是否折中。",
    ),
    FigureSpec(
        "fig3b",
        "fig3_xingkai_connector_levels_u5fb7.png",
        ("xingkai_balanced_experiment_20260618_141424/figures/compare_connector_levels_u5fb7_xingkai.png",),
        "xingkai balanced connector experiment",
        "行楷 connector rule ablation",
        "Xingkai 德 connector levels: all-adjacent baseline, conservative v1, balanced v2.",
        "yes",
        "德是 connector 数量变化明显样本，建议重点看。",
    ),
    FigureSpec(
        "fig3c",
        "fig3_xingkai_connector_levels_u660e.png",
        ("xingkai_balanced_experiment_20260618_141424/figures/compare_connector_levels_u660e_xingkai.png",),
        "xingkai balanced connector experiment",
        "行楷 connector rule ablation",
        "Xingkai 明 connector levels: all-adjacent baseline, conservative v1, balanced v2.",
        "yes",
        "明在 balanced 中从清零恢复少量 connector，建议重点看。",
    ),
    FigureSpec(
        "fig4",
        "fig4_execution_width_pressure.png",
        (
            "xingkai_balanced_experiment_20260618_141424/figures/width_pressure_balanced_u56fd_xingkai.png",
            "width_pressure_visualization_20260618_101349/figures/width_global_u56fd_xingkai.png",
        ),
        "execution width / pressure visualization",
        "二维执行层表达",
        "Execution-layer width/pressure visualization for xingkai 国.",
        "yes",
        "重点人工看 stroke taper 与 connector thinner 是否可见。",
    ),
    FigureSpec(
        "supp1",
        "supplementary/supp_font_style_grid.png",
        ("font_style_gap_analysis_20260618_144838/figures/font_style_grid.png",),
        "font style gap analysis",
        "补充材料",
        "Font style grid for kaishu/xingkai/lishu source fonts.",
        "yes",
        "用于说明真实字体轮廓与当前参数化轨迹之间的差距。",
        True,
    ),
    FigureSpec(
        "supp2",
        "supplementary/supp_font_vs_trajectory_aspect_ratio.png",
        ("font_style_gap_analysis_20260618_144838/figures/font_vs_trajectory_aspect_ratio.png",),
        "font style gap analysis",
        "补充材料",
        "Font aspect ratio vs trajectory aspect ratio.",
        "no",
        "仅作为补充指标图。",
        True,
    ),
    FigureSpec(
        "supp3",
        "supplementary/supp_lishu_flatness_gap.png",
        ("font_style_gap_analysis_20260618_144838/figures/lishu_flatness_gap.png",),
        "font style gap analysis",
        "补充材料",
        "Lishu flatness gap between source font and current trajectory.",
        "yes",
        "重点人工看 lishu 是否仍像压扁楷书。",
        True,
    ),
    FigureSpec(
        "supp4",
        "supplementary/supp_phase1_current_vs_scale.png",
        ("style_profile_phase1_estimates_20260618_152952/figures/current_vs_phase1_scale.png",),
        "Phase 1 readonly estimates",
        "补充材料",
        "Current profile scale vs Phase 1 readonly hints.",
        "no",
        "readonly estimate，不接默认流程。",
        True,
    ),
]


TABLE_SPECS = [
    TableSpec(
        "table1",
        "table1_retiming_before_after.md",
        "batch_20260613_154131/u5c71_xingkai_20260613_154132_009898/target_pose_retiming_summary.json",
        "motion continuity and retiming",
        "Raw vs smoothed target pose continuity metrics.",
        "retiming 修复时间单调性、加速度和 jerk 的 conservative dry-run gate。",
    ),
    TableSpec(
        "table2",
        "table2_robot_precheck_summary.md",
        "paper_figures/aubo_i5_ik_feasibility_smoothed_summary.json",
        "robot-interface precheck chain",
        "Robot-interface dry-run precheck summary.",
        "只说明 dry-run precheck，不是真实机器人控制。",
    ),
    TableSpec(
        "table3",
        "table3_external_functional_comparison.md",
        "configs/mini_paper_experiment_matrix.json",
        "external functional comparison",
        "Functional comparison with representative trajectory/style-generation method types.",
        "功能维度对比，不编造外部数值结果。",
    ),
]


def _outputs_dir(paper_figures_dir: Path) -> Path:
    return paper_figures_dir.parent


def _resolve_source(
    spec: FigureSpec,
    paper_figures_dir: Path,
    source_overrides: dict[str, Path] | None,
) -> Path | None:
    if source_overrides and spec.figure_id in source_overrides:
        path = Path(source_overrides[spec.figure_id])
        return path if path.exists() else None

    outputs_dir = _outputs_dir(paper_figures_dir)
    for candidate in spec.source_candidates:
        path = outputs_dir / candidate
        if path.exists():
            return path
    return None


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_pipeline_figure(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    steps = [
        "Natural\nlanguage",
        "Planner\n(mock/API/local)",
        "Validation",
        "Style\nmodifiers",
        "Style\nprofile",
        "Trajectory\n(local tools)",
        "Execution\nwidth/pressure",
        "Workspace\nmapping",
        "Retiming",
        "Precheck\n dry-run",
    ]
    fig, ax = plt.subplots(figsize=(15, 4.6))
    ax.axis("off")
    y = 0.52
    for idx, label in enumerate(steps):
        x = 0.05 + idx * 0.1
        ax.text(
            x,
            y,
            label,
            ha="center",
            va="center",
            fontsize=9,
            bbox={
                "boxstyle": "round,pad=0.35",
                "facecolor": "#f6f2e8",
                "edgecolor": "#4d4d4d",
                "linewidth": 1.0,
            },
        )
        if idx < len(steps) - 1:
            ax.annotate(
                "",
                xy=(x + 0.055, y),
                xytext=(x + 0.04, y),
                arrowprops={"arrowstyle": "->", "lw": 1.3, "color": "#333333"},
            )
    ax.text(
        0.5,
        0.15,
        "LLM only outputs a structured plan; CSV trajectories are generated by local deterministic tools.",
        ha="center",
        va="center",
        fontsize=10,
        color="#333333",
    )
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _write_missing_placeholder(path: Path, figure_id: str, caption: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.axis("off")
    ax.text(0.5, 0.62, "Missing source", ha="center", va="center", fontsize=16)
    ax.text(0.5, 0.43, figure_id, ha="center", va="center", fontsize=12)
    ax.text(0.5, 0.27, "See missing_sources.csv for expected source paths.", ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _markdown_table(headers: list[str], rows: Iterable[Iterable[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines) + "\n"


def _write_retiming_table(out_dir: Path) -> None:
    rows = [
        ["point_count", 275, 271],
        ["duration_s", 13.0528205, 22.039876274],
        ["dt_nonpositive_count", 4, 0],
        ["max_speed_m_s", 0.04, 0.01792],
        ["max_accel_m_s2", 0.533536284, 0.274132141],
        ["max_jerk_m_s3", 11.386446091, 4.193553547],
        ["recommended_for_ik_dry_run", "false", "true"],
    ]
    md = "# Table 1. Retiming before/after\n\n" + _markdown_table(
        ["metric", "raw target poses", "smoothed target poses"], rows
    )
    (out_dir / "table1_retiming_before_after.md").write_text(md, encoding="utf-8")
    _write_csv(
        out_dir / "table1_retiming_before_after.csv",
        [{"metric": r[0], "raw_target_poses": r[1], "smoothed_target_poses": r[2]} for r in rows],
        ["metric", "raw_target_poses", "smoothed_target_poses"],
    )


def _write_robot_precheck_table(out_dir: Path) -> None:
    rows = [
        ["workspace mapping", "out_of_bounds", "false", "120mm paper workspace"],
        ["CoppeliaSim standard scene", "recommended_playback", "true", "pen-tip/sphere playback only"],
        ["AUBO command adapter", "recommended_for_sdk_dry_run", "true", "offline command plan only"],
        ["IK feasibility", "recommended_for_real_ik_check", "true", "geometric envelope hint, not real IK"],
    ]
    md = "# Table 2. Robot-interface precheck summary\n\n" + _markdown_table(
        ["layer", "gate", "result", "scope"], rows
    )
    (out_dir / "table2_robot_precheck_summary.md").write_text(md, encoding="utf-8")
    _write_csv(
        out_dir / "table2_robot_precheck_summary.csv",
        [{"layer": r[0], "gate": r[1], "result": r[2], "scope": r[3]} for r in rows],
        ["layer", "gate", "result", "scope"],
    )


def _write_external_comparison_table(out_dir: Path) -> None:
    rows = [
        ["传统图像骨架提取法", "否", "否", "否", "通常否", "否", "否", "受输入图像和骨架质量限制"],
        ["示教轨迹学习法", "是", "否", "通常否", "是", "可扩展", "可扩展", "受示教数据覆盖限制"],
        ["强化学习局部优化法", "可选", "否", "通常否", "可输出", "需额外设计", "可扩展", "受奖励函数和初始轨迹限制"],
        ["字体/图像风格迁移法", "否或弱", "否", "通常否", "通常否", "否", "否", "静态视觉强，书写过程弱"],
        ["本文方法", "否", "是", "是", "是", "是", "dry-run", "受 median strokes 与参数化 profile 限制"],
    ]
    headers = [
        "方法类型",
        "需要示教数据",
        "自然语言输入",
        "可解释 modifier",
        "execution trajectory",
        "retiming/motion gate",
        "robot-interface dry-run",
        "风格真实性上限",
    ]
    md = "# Table 3. External functional comparison\n\n" + _markdown_table(headers, rows)
    (out_dir / "table3_external_functional_comparison.md").write_text(md, encoding="utf-8")
    _write_csv(
        out_dir / "table3_external_functional_comparison.csv",
        [dict(zip(headers, row)) for row in rows],
        headers,
    )


def _write_index(
    out_dir: Path,
    figure_rows: list[dict[str, object]],
    table_rows: list[dict[str, object]],
    missing_rows: list[dict[str, object]],
) -> None:
    figure_overview = _markdown_table(
        ["figure_id", "filename", "section", "needs_manual_check", "status"],
        [
            [
                row["figure_id"],
                row["filename"],
                row["paper_section"],
                row["needs_manual_check"],
                row["status"],
            ]
            for row in figure_rows
        ],
    )
    table_overview = _markdown_table(
        ["table_id", "filename", "section", "status"],
        [[row["table_id"], row["filename"], row["paper_section"], row["status"]] for row in table_rows],
    )
    manual_figures = [
        row for row in figure_rows if str(row["needs_manual_check"]).lower() == "yes"
    ]
    manual_overview = _markdown_table(
        ["figure_id", "filename", "manual focus"],
        [[row["figure_id"], row["filename"], row["notes"]] for row in manual_figures],
    )
    missing_text = "无 missing source。\n"
    if missing_rows:
        missing_text = _markdown_table(
            ["figure_id", "target", "expected_sources"],
            [[row["figure_id"], row["filename"], row["expected_sources"]] for row in missing_rows],
        )

    text = f"""# Mini-paper fixed figure/table pack

## 小论文建议主线

```text
自然语言约束驱动的书法机器人参数化轨迹生成与执行前检查方法
```

本图表包只整理、复制、重命名和汇总已有结果。Figure 1 是基于既有文档重画的方法示意图；其余图表来自已有输出或缺源占位。

## 图表总览

{figure_overview}

## 表格总览

{table_overview}

## 推荐标题与 caption 草稿

- Figure 1: System pipeline. LLM/mock planner only emits structured plans; trajectories are generated by local deterministic tools.
- Figure 2: Natural-language modifier controllability. Connection, shape, and smoothness constraints map to local style parameters.
- Figure 3: Xingkai connector rule ablation. All-adjacent is dense, conservative is sparse, and balanced is the accepted candidate_default_v2.
- Figure 4: Execution-layer width/pressure visualization. Execution trajectories carry width, pressure, and connector state beyond centerline geometry.
- Table 1: Target pose retiming before/after. Retiming removes non-positive dt and reduces conservative acceleration/jerk metrics.
- Table 2: Robot-interface precheck chain. Workspace, CoppeliaSim, command adapter, and IK feasibility remain dry-run checks.
- Table 3: External functional comparison. The table compares capabilities only, not reproduced numeric results.

## 需要用户人工重点看的图

{manual_overview}

## 补充材料

`supplementary/` 中的 style gap / Phase 1 图仅用于说明当前风格仍是参数化控制，真实风格学习和 component/stroke-level profile 数据化是后续方向。

## Missing sources

{missing_text}

## 边界说明

- 当前不是完整真实书法风格学习。
- CoppeliaSim/AUBO 均是 dry-run/precheck，不是真实机械臂 IK 或实机控制。
- 外部方法表是功能维度对比，不是外部方法数值复现。
- 数值指标不能替代人工看图，尤其是 connector 自然度、笔画粗细、布局自然度和风格区分度。
"""
    (out_dir / "mini_paper_figure_index.md").write_text(text, encoding="utf-8")


def build_figure_pack(
    paper_figures_dir: Path = DEFAULT_PAPER_FIGURES_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    source_overrides: dict[str, Path] | None = None,
) -> dict[str, int]:
    paper_figures_dir = Path(paper_figures_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "supplementary").mkdir(parents=True, exist_ok=True)

    figure_rows: list[dict[str, object]] = []
    table_rows: list[dict[str, object]] = []
    missing_rows: list[dict[str, object]] = []

    fig1 = out_dir / "fig1_system_pipeline.png"
    _write_pipeline_figure(fig1)
    figure_rows.append(
        {
            "figure_id": "fig1",
            "filename": "fig1_system_pipeline.png",
            "source_path": "generated_from_docs",
            "source_experiment": "mini paper method overview",
            "paper_section": "系统总体方案",
            "caption_draft": "System pipeline from natural language to deterministic trajectory and dry-run precheck.",
            "status": "generated",
            "needs_manual_check": "no",
            "notes": "LLM 不直接生成轨迹；轨迹由本地确定性工具生成。",
        }
    )

    for spec in FIGURE_SPECS:
        target = out_dir / spec.filename
        source = _resolve_source(spec, paper_figures_dir, source_overrides)
        if source is None:
            _write_missing_placeholder(target, spec.figure_id, spec.caption_draft)
            status = "missing_source_placeholder"
            source_text = ""
            missing_rows.append(
                {
                    "figure_id": spec.figure_id,
                    "filename": spec.filename,
                    "expected_sources": "; ".join(spec.source_candidates),
                    "notes": spec.notes,
                }
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            status = "copied"
            source_text = str(source)
        figure_rows.append(
            {
                "figure_id": spec.figure_id,
                "filename": spec.filename,
                "source_path": source_text,
                "source_experiment": spec.source_experiment,
                "paper_section": spec.paper_section,
                "caption_draft": spec.caption_draft,
                "status": status,
                "needs_manual_check": spec.needs_manual_check,
                "notes": spec.notes,
            }
        )

    _write_retiming_table(out_dir)
    _write_robot_precheck_table(out_dir)
    _write_external_comparison_table(out_dir)
    for spec in TABLE_SPECS:
        table_rows.append(
            {
                "table_id": spec.table_id,
                "filename": spec.filename,
                "source_path": spec.source_path,
                "paper_section": spec.paper_section,
                "caption_draft": spec.caption_draft,
                "status": "generated",
                "notes": spec.notes,
            }
        )

    _write_csv(
        out_dir / "mini_paper_figure_manifest.csv",
        figure_rows,
        [
            "figure_id",
            "filename",
            "source_path",
            "source_experiment",
            "paper_section",
            "caption_draft",
            "status",
            "needs_manual_check",
            "notes",
        ],
    )
    _write_csv(
        out_dir / "mini_paper_table_manifest.csv",
        table_rows,
        ["table_id", "filename", "source_path", "paper_section", "caption_draft", "status", "notes"],
    )
    _write_csv(
        out_dir / "missing_sources.csv",
        missing_rows,
        ["figure_id", "filename", "expected_sources", "notes"],
    )
    _write_index(out_dir, figure_rows, table_rows, missing_rows)

    summary = {
        "figure_count": len(figure_rows),
        "table_count": len(table_rows),
        "missing_count": len(missing_rows),
    }
    (out_dir / "mini_paper_figure_pack_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the fixed mini-paper figure/table pack.")
    parser.add_argument("--paper-figures-dir", type=Path, default=DEFAULT_PAPER_FIGURES_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_figure_pack(args.paper_figures_dir, args.out_dir)
    print(json.dumps({"out_dir": str(args.out_dir), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
