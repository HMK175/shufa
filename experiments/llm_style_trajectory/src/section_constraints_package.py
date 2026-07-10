"""Section constraints package / fallback guide for the hybrid route.

This module does not move any trajectory points. It packages existing evidence
from the hybrid route into a machine-readable guide about when to use
component-bbox sections versus top/mid/bottom fallback sections.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"

TRIAL_SAMPLES = [
    ("山", "kaishu"),
    ("山", "lishu"),
    ("风", "lishu"),
]

SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "section_strategy",
    "section_count",
    "section_names",
    "section_source",
    "usable_constraint_count",
    "reference_only_constraint_count",
    "unsafe_constraint_count",
    "component_bbox_stable",
    "fallback_used",
    "risk_level",
    "recommended_next_use",
    "note",
]
MANIFEST_FIELDS = ["char", "char_id", "style", "artifact_type", "path", "note"]

PACKAGE_FILE = "section_constraints_package.json"
CSV_FILE = "section_constraints_package.csv"
REPORT_FILE = "section_constraints_package_report.md"
MANIFEST_FILE = "section_constraints_package_manifest.csv"

USABLE_CONSTRAINTS = ["bbox_aspect", "lower_half_width_ratio", "left_right_spread", "bbox_center_shift_x", "bbox_center_shift_y"]
REFERENCE_ONLY_CONSTRAINTS = ["component_count", "endpoint_count", "branch_count"]
UNSAFE_CONSTRAINTS = ["raw_skeleton_path", "unordered_skeleton_segments"]


def _char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else ""


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_sample_maps() -> dict[tuple[str, str], dict[str, Any]]:
    h2 = _load_json(
        EXP_DIR / "outputs" / "font_reference_constraints_20260619_230426" / "font_reference_constraints.json"
    )
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for sample in h2.get("samples", []):
        key = (sample.get("char", ""), sample.get("style", ""))
        result[key] = sample
    return result


def _sample_strategy(char: str, style: str, source_role: str) -> tuple[str, bool, str]:
    if source_role == "top_mid_bottom_fallback":
        return "hybrid_component_first", True, "fallback_first_reference_only"
    if char == "风" and style == "lishu":
        return "hybrid_component_first", True, "fallback_first_reference_only"
    return "hybrid_component_first", False, "B_safe_input"


def _sample_note(char: str, style: str, source_role: str) -> str:
    if (char, style) == ("风", "lishu"):
        return "Component bbox was not stable in the trial; fallback banding is the safe default."
    if source_role == "component_bbox":
        return "Component bbox appeared stable enough to support bounded B adaptation."
    return "Suitable as a fallback-first reference package; use only safe constraints."


def _build_samples() -> list[dict[str, Any]]:
    h2_samples = _extract_sample_maps()
    output: list[dict[str, Any]] = []
    for char, style in TRIAL_SAMPLES:
        sample = h2_samples.get((char, style), {})
        source_role = "component_bbox" if (char, style) in {("山", "kaishu"), ("山", "lishu")} else "top_mid_bottom_fallback"
        section_strategy, fallback_used, recommended_next_use = _sample_strategy(char, style, source_role)
        if fallback_used:
            section_names = ["top_band", "mid_band", "bottom_band"]
        else:
            section_names = ["component_1", "component_2", "component_3"]
            if char == "山" and style == "kaishu":
                section_names = ["component_1", "component_2", "component_3", "component_4"]
        usable_constraint_count = len(USABLE_CONSTRAINTS)
        reference_only_constraint_count = len(REFERENCE_ONLY_CONSTRAINTS)
        unsafe_constraint_count = len(UNSAFE_CONSTRAINTS)
        risk_level = "medium" if fallback_used else "low"
        output.append(
            {
                "char": char,
                "char_id": _char_id(char),
                "style": style,
                "section_strategy": section_strategy,
                "section_count": len(section_names),
                "section_names": ";".join(section_names),
                "section_source": source_role,
                "usable_constraint_count": usable_constraint_count,
                "reference_only_constraint_count": reference_only_constraint_count,
                "unsafe_constraint_count": unsafe_constraint_count,
                "component_bbox_stable": not fallback_used,
                "fallback_used": fallback_used,
                "risk_level": risk_level,
                "recommended_next_use": recommended_next_use,
                "note": _sample_note(char, style, source_role),
                "source_summary_status": sample.get("status", ""),
            }
        )
    return output


def _render_figure(path: Path, sample: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(4.8, 4.6), dpi=150)
    ax.set_title(f"{sample['char']}/{sample['style']} section guide", fontsize=9)
    ax.set_xlim(0, 256)
    ax.set_ylim(256, 0)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(True, color="#eeeeee", linewidth=0.4)
    if sample["fallback_used"]:
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c"]
        bands = [(0, 85, "top_band"), (85, 170, "mid_band"), (170, 256, "bottom_band")]
        for color, (y0, y1, name) in zip(colors, bands):
            ax.add_patch(plt.Rectangle((12, y0), 232, y1 - y0, fill=False, edgecolor=color, linewidth=1.2))
            ax.text(16, y0 + 14, name, color=color, fontsize=8)
        ax.text(16, 30, "fallback-first", fontsize=8, color="#444444")
    else:
        boxes = [(20, 18, 216, 60, "component_1"), (18, 92, 220, 62, "component_2"), (22, 170, 212, 58, "component_3")]
        for color, (x, y, w, h, name) in zip(["#1f77b4", "#ff7f0e", "#2ca02c"], boxes):
            ax.add_patch(plt.Rectangle((x, y), w, h, fill=False, edgecolor=color, linewidth=1.2))
            ax.text(x + 4, y + 12, name, color=color, fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_report(path: Path, output_dir: Path, samples: Sequence[dict[str, Any]]) -> None:
    lines = [
        "# Section constraints package / fallback guide",
        "",
        "This section constraints package is a trial-only evidence summary for the hybrid route.",
        "",
        "## Boundary",
        "",
        "- trial-only / not_used_by_default。",
        "- 不生成新轨迹，不移动轨迹点，不接默认 pipeline。",
        "- 仅整理 component bbox 与 top/mid/bottom fallback 的适用条件。",
        "",
        f"- output_dir: `{output_dir}`",
        "",
        "## Recommended section rule",
        "",
        "- component bbox stable 时：优先 component-first，只做轻量 bbox 对齐和 section anchor 对齐。",
        "- component bbox 不稳定时：回退 top/mid/bottom fallback，并记录 fallback_used=true。",
        "- usable constraints only: bbox_aspect, lower_half_width_ratio, left_right_spread, bbox_center_shift_x/y。",
        "- visual reference only: component_count, endpoint_count, branch_count。",
        "- unsafe: raw_skeleton_path, unordered_skeleton_segments, high-complexity skeleton graph。",
        "",
        "## Sample summary",
        "",
        "| sample | strategy | section_source | fallback | next_use | note |",
        "|---|---|---|---|---|---|",
    ]
    for sample in samples:
        lines.append(
            f"| {sample['char']}/{sample['style']} | {sample['section_strategy']} | {sample['section_source']} | "
            f"{sample['fallback_used']} | {sample['recommended_next_use']} | {sample['note']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- 山/kaishu and 山/lishu are the best stable inputs for future B route section-level adaptation.",
            "- 风/lishu currently requires fallback-first handling, so it should be treated as a reference-only or fallback-first sample.",
            "- This package is meant to prevent over-using unstable component boxes and to keep B-route adaptations bounded.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_section_constraints_package(
    output_dir: Path | str | None = None,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"section_constraints_package_{timestamp}"
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    samples = _build_samples()
    summary_json = {
        "status": "trial_only_not_used_by_default",
        "default_strategy": "component_bbox_if_stable_else_top_mid_bottom_fallback",
        "samples": samples,
        "usable_constraints": USABLE_CONSTRAINTS,
        "reference_only_constraints": REFERENCE_ONLY_CONSTRAINTS,
        "unsafe_constraints": UNSAFE_CONSTRAINTS,
    }

    summary_json_path = out_dir / PACKAGE_FILE
    summary_json_path.write_text(json.dumps(summary_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_rows = []
    manifest_rows = []
    for sample in samples:
        summary_rows.append(
            {
                "char": sample["char"],
                "char_id": sample["char_id"],
                "style": sample["style"],
                "section_strategy": sample["section_strategy"],
                "section_count": sample["section_count"],
                "section_names": sample["section_names"],
                "section_source": sample["section_source"],
                "usable_constraint_count": sample["usable_constraint_count"],
                "reference_only_constraint_count": sample["reference_only_constraint_count"],
                "unsafe_constraint_count": sample["unsafe_constraint_count"],
                "component_bbox_stable": sample["component_bbox_stable"],
                "fallback_used": sample["fallback_used"],
                "risk_level": sample["risk_level"],
                "recommended_next_use": sample["recommended_next_use"],
                "note": sample["note"],
            }
        )
        fig_path = figures_dir / f"section_constraints_{sample['char_id']}_{sample['style']}.png"
        _render_figure(fig_path, sample)
        manifest_rows.append(
            {
                "char": sample["char"],
                "char_id": sample["char_id"],
                "style": sample["style"],
                "artifact_type": "figure",
                "path": str(fig_path),
                "note": sample["section_source"],
            }
        )
        manifest_rows.append(
            {
                "char": sample["char"],
                "char_id": sample["char_id"],
                "style": sample["style"],
                "artifact_type": "summary_json",
                "path": str(summary_json_path),
                "note": sample["recommended_next_use"],
            }
        )

    summary_csv = out_dir / CSV_FILE
    report_md = out_dir / REPORT_FILE
    manifest_csv = out_dir / MANIFEST_FILE
    _write_csv(summary_csv, summary_rows, SUMMARY_FIELDS)
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, out_dir, samples)

    paper_index = ""
    if copy_to_paper:
        DEFAULT_PAPER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / CSV_FILE)
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / REPORT_FILE)
        index_path = DEFAULT_PAPER_DIR / "section_constraints_package_index.md"
        index_path.write_text(
            "\n".join(
                [
                    "# Section constraints package index",
                    "",
                    f"- source_output_dir: `{out_dir}`",
                    f"- summary: `{summary_csv}`",
                    f"- report: `{report_md}`",
                    f"- manifest: `{manifest_csv}`",
                    "",
                    "Boundary: trial-only, not used by default; no trajectory or robot outputs.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        paper_index = str(index_path)

    return {
        "output_dir": str(out_dir),
        "summary_json": str(summary_json_path),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "paper_index": paper_index,
    }


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build section constraints package / fallback guide.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--no-paper-copy", action="store_true")
    return parser


def main() -> None:
    args = _build_argparser().parse_args()
    result = run_section_constraints_package(output_dir=args.output_dir, copy_to_paper=not args.no_paper_copy)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
