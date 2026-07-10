"""Small H1-lite style contrast expansion for 山/kaishu vs 山/lishu.

This diagnostic layer generates only a trial H1-lite result for 山/kaishu and
compares it with the existing 山/lishu H1-lite reference. It does not create a
formal trajectory.csv, execution/workspace/robot files, or default pipeline
outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from constraint_bounded_adaptation_h1_lite import (
    DEFAULT_H2_CONSTRAINTS_JSON,
    _draw_strokes,
    _load_median,
    _path_length,
    _write_csv,
    run_constraint_bounded_adaptation_h1_lite,
)


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
DEFAULT_LISHU_H1_DIR = (
    DEFAULT_OUTPUT
    / "constraint_bounded_adaptation_h1_lite_20260619_231903"
    / "u5c71_lishu"
)

SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "source_role",
    "sample_dir",
    "summary_json",
    "compare_png",
    "stroke_count",
    "point_count",
    "bbox_aspect_median",
    "bbox_aspect_conservative",
    "bbox_aspect_balanced",
    "lower_half_width_median",
    "lower_half_width_conservative",
    "lower_half_width_balanced",
    "left_right_spread_median",
    "left_right_spread_conservative",
    "left_right_spread_balanced",
    "max_point_shift_px_conservative",
    "max_point_shift_px_balanced",
    "path_length_ratio_conservative",
    "path_length_ratio_balanced",
    "stroke_count_preserved",
    "recommended_for_visual_followup",
]

MANIFEST_FIELDS = [
    "char",
    "char_id",
    "style",
    "artifact_type",
    "path",
    "source_role",
    "note",
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_trial_csv(path: Path) -> list[np.ndarray]:
    strokes: list[list[list[float]]] = []
    current: list[list[float]] = []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row.get("is_break") == "1":
                if current:
                    strokes.append(current)
                    current = []
                continue
            current.append([float(row["y"]), float(row["x"])])
    if current:
        strokes.append(current)
    return [np.asarray(stroke, dtype=float) for stroke in strokes]


def _summary_row(summary: dict[str, Any], sample_dir: Path, source_role: str) -> dict[str, Any]:
    max_shift = summary.get("max_point_shift_px", {})
    path_ratio = summary.get("path_length_ratio", {})
    return {
        "char": summary.get("char", ""),
        "char_id": summary.get("char_id", ""),
        "style": summary.get("style", ""),
        "source_role": source_role,
        "sample_dir": str(sample_dir),
        "summary_json": str(sample_dir / "h1_lite_summary.json"),
        "compare_png": str(sample_dir / "h1_lite_compare.png"),
        "stroke_count": summary.get("stroke_count", ""),
        "point_count": summary.get("point_count", ""),
        "bbox_aspect_median": summary.get("bbox_aspect_median", ""),
        "bbox_aspect_conservative": summary.get("bbox_aspect_conservative", ""),
        "bbox_aspect_balanced": summary.get("bbox_aspect_balanced", ""),
        "lower_half_width_median": summary.get("lower_half_width_median", ""),
        "lower_half_width_conservative": summary.get("lower_half_width_conservative", ""),
        "lower_half_width_balanced": summary.get("lower_half_width_balanced", ""),
        "left_right_spread_median": summary.get("left_right_spread_median", ""),
        "left_right_spread_conservative": summary.get("left_right_spread_conservative", ""),
        "left_right_spread_balanced": summary.get("left_right_spread_balanced", ""),
        "max_point_shift_px_conservative": max_shift.get("conservative", ""),
        "max_point_shift_px_balanced": max_shift.get("balanced", ""),
        "path_length_ratio_conservative": path_ratio.get("conservative", ""),
        "path_length_ratio_balanced": path_ratio.get("balanced", ""),
        "stroke_count_preserved": summary.get("stroke_count_preserved", ""),
        "recommended_for_visual_followup": summary.get("recommended_for_visual_followup", ""),
    }


def _style_gap(a: float, b: float) -> float:
    return round(abs(float(a) - float(b)), 6)


def _make_gap_summary(kaishu: dict[str, Any], lishu: dict[str, Any]) -> dict[str, Any]:
    aspect_before = _style_gap(kaishu["bbox_aspect_median"], lishu["bbox_aspect_median"])
    aspect_after_cons = _style_gap(kaishu["bbox_aspect_conservative"], lishu["bbox_aspect_conservative"])
    aspect_after_bal = _style_gap(kaishu["bbox_aspect_balanced"], lishu["bbox_aspect_balanced"])
    lower_before = _style_gap(kaishu["lower_half_width_median"], lishu["lower_half_width_median"])
    lower_after_cons = _style_gap(kaishu["lower_half_width_conservative"], lishu["lower_half_width_conservative"])
    lower_after_bal = _style_gap(kaishu["lower_half_width_balanced"], lishu["lower_half_width_balanced"])
    return {
        "status": "trial_not_used_by_default",
        "source": "h1_lite_style_contrast_expansion",
        "char": "山",
        "char_id": "u5c71",
        "styles": ["kaishu", "lishu"],
        "kaishu_source": "generated_this_run",
        "lishu_source": "existing_h1_lite_reference",
        "kaishu_lishu_style_gap_before": {
            "bbox_aspect_gap": aspect_before,
            "lower_half_width_gap": lower_before,
        },
        "kaishu_lishu_style_gap_after_conservative": {
            "bbox_aspect_gap": aspect_after_cons,
            "lower_half_width_gap": lower_after_cons,
        },
        "kaishu_lishu_style_gap_after_balanced": {
            "bbox_aspect_gap": aspect_after_bal,
            "lower_half_width_gap": lower_after_bal,
        },
        "gap_delta_balanced_minus_before": {
            "bbox_aspect_gap": round(aspect_after_bal - aspect_before, 6),
            "lower_half_width_gap": round(lower_after_bal - lower_before, 6),
        },
        "kaishu_stroke_count_preserved": bool(kaishu.get("stroke_count_preserved")),
        "lishu_stroke_count_preserved": bool(lishu.get("stroke_count_preserved")),
        "recommended_for_visual_followup": True,
        "boundary": "trial-only; not_used_by_default; no formal trajectory.csv; no execution/workspace/robot outputs",
    }


def _write_contrast_figure(path: Path, kaishu_dir: Path, lishu_dir: Path, image_size: int) -> None:
    kaishu_median = _load_median("山", image_size=image_size)
    lishu_median = _load_median("山", image_size=image_size)
    kaishu_cons = _read_trial_csv(kaishu_dir / "h1_lite_conservative.csv")
    kaishu_bal = _read_trial_csv(kaishu_dir / "h1_lite_balanced.csv")
    lishu_cons = _read_trial_csv(lishu_dir / "h1_lite_conservative.csv")
    lishu_bal = _read_trial_csv(lishu_dir / "h1_lite_balanced.csv")

    panels = [
        ("kaishu original median", kaishu_median, "#555555"),
        ("kaishu H1-lite conservative", kaishu_cons, "#1f77b4"),
        ("kaishu H1-lite balanced", kaishu_bal, "#0b4f9c"),
        ("lishu original median", lishu_median, "#555555"),
        ("lishu H1-lite conservative", lishu_cons, "#c06014"),
        ("lishu H1-lite balanced", lishu_bal, "#8f2d0d"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(10.5, 7.0))
    for ax, (title, strokes, color) in zip(axes.flat, panels):
        _draw_strokes(ax, strokes, title, color)
        ax.set_xlim(0, image_size)
        ax.set_ylim(image_size, 0)
    fig.suptitle("H1-lite style contrast: 山 / kaishu vs lishu", fontsize=13)
    fig.tight_layout(rect=[0.0, 0.0, 1.0, 0.94])
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def _write_report(path: Path, output_dir: Path, rows: Sequence[dict[str, Any]], gap: dict[str, Any], contrast_png: Path) -> None:
    lines = [
        "# H1-lite style contrast expansion: 山 / kaishu vs lishu",
        "",
        "This report compares the newly generated 山/kaishu H1-lite trial with the existing 山/lishu H1-lite reference.",
        "",
        "## Boundary",
        "",
        "- trial-only / not_used_by_default。",
        "- 只使用 H2 `usable_for_adaptation` 的 bounded constraints。",
        "- 不使用 raw skeleton path、不使用 unordered skeleton segments、不做最近点吸附。",
        "- 不生成正式 trajectory.csv，不生成 execution/workspace/robot 文件，不接默认 pipeline。",
        "",
        f"- output_dir: `{output_dir}`",
        f"- contrast_png: `{contrast_png}`",
        "",
        "## Sample metrics",
        "",
        "| style | source | aspect median | aspect cons | aspect balanced | lower median | lower cons | lower balanced | max shift cons | max shift balanced | path ratio balanced |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {style} | {source_role} | {bbox_aspect_median} | {bbox_aspect_conservative} | {bbox_aspect_balanced} | "
            "{lower_half_width_median} | {lower_half_width_conservative} | {lower_half_width_balanced} | "
            "{max_point_shift_px_conservative} | {max_point_shift_px_balanced} | {path_length_ratio_balanced} |".format(**row)
        )
    before = gap["kaishu_lishu_style_gap_before"]
    cons = gap["kaishu_lishu_style_gap_after_conservative"]
    bal = gap["kaishu_lishu_style_gap_after_balanced"]
    delta = gap["gap_delta_balanced_minus_before"]
    lines.extend(
        [
            "",
            "## Style gap",
            "",
            "| metric | before | after conservative | after balanced | balanced - before |",
            "|---|---:|---:|---:|---:|",
            f"| bbox_aspect_gap | {before['bbox_aspect_gap']} | {cons['bbox_aspect_gap']} | {bal['bbox_aspect_gap']} | {delta['bbox_aspect_gap']} |",
            f"| lower_half_width_gap | {before['lower_half_width_gap']} | {cons['lower_half_width_gap']} | {bal['lower_half_width_gap']} | {delta['lower_half_width_gap']} |",
            "",
            "## Manual visual audit questions",
            "",
            "- 山/kaishu 是否仍像楷书、没有被过度拉伸？",
            "- 山/lishu 是否比 kaishu 更宽底、更有隶书感？",
            "- 同字不同风格对照是否比原 style profile 更清楚？",
            "- balanced 是否比 conservative 更自然？",
            "",
            "## Interpretation",
            "",
            "If the balanced gap is larger while both styles preserve stroke_count and path shape, this supports expanding H1-lite carefully. "
            "If kaishu looks stretched or lishu still lacks visible style, the next step should be more visual audit rather than adding stronger constraints.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(index_path: Path, output_dir: Path, rows: Sequence[dict[str, Any]], gap: dict[str, Any], contrast_png: Path) -> None:
    lines = [
        "# H1-lite style contrast expansion index",
        "",
        f"- source_output_dir: `{output_dir}`",
        "- Status: trial-only, not used by default.",
        "- Boundary: no raw skeleton path, no nearest-point pulling, no formal trajectory.csv, no execution/workspace/robot outputs.",
        "",
        "| style | compare | summary |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['style']} | `{row['compare_png']}` | `{row['summary_json']}` |")
    lines.extend(
        [
            "",
            f"- contrast_png: `{contrast_png}`",
            f"- gap_summary: `{output_dir / 'contrast' / 'h1_lite_u5c71_style_gap_summary.json'}`",
            f"- bbox_aspect_gap before -> balanced: {gap['kaishu_lishu_style_gap_before']['bbox_aspect_gap']} -> {gap['kaishu_lishu_style_gap_after_balanced']['bbox_aspect_gap']}",
            f"- lower_half_width_gap before -> balanced: {gap['kaishu_lishu_style_gap_before']['lower_half_width_gap']} -> {gap['kaishu_lishu_style_gap_after_balanced']['lower_half_width_gap']}",
        ]
    )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_h1_lite_style_contrast_expansion(
    output_dir: Path | str | None = None,
    constraints_json: Path | str = DEFAULT_H2_CONSTRAINTS_JSON,
    lishu_reference_dir: Path | str = DEFAULT_LISHU_H1_DIR,
    image_size: int = 256,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    if output_dir is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"h1_lite_style_contrast_{stamp}"
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    h1_result = run_constraint_bounded_adaptation_h1_lite(
        output_dir=out_dir,
        constraints_json_path=constraints_json,
        sample_specs=[("山", "kaishu")],
        image_size=image_size,
        copy_to_paper=False,
    )

    kaishu_dir = out_dir / "u5c71_kaishu"
    lishu_dir = Path(lishu_reference_dir)
    if not (lishu_dir / "h1_lite_summary.json").exists():
        raise FileNotFoundError(f"Missing lishu H1-lite reference: {lishu_dir}")

    kaishu_summary = _read_json(kaishu_dir / "h1_lite_summary.json")
    lishu_summary = _read_json(lishu_dir / "h1_lite_summary.json")
    rows = [
        _summary_row(kaishu_summary, kaishu_dir, "generated_this_run"),
        _summary_row(lishu_summary, lishu_dir, "existing_h1_lite_reference"),
    ]

    contrast_dir = out_dir / "contrast"
    contrast_dir.mkdir(parents=True, exist_ok=True)
    contrast_png = contrast_dir / "h1_lite_u5c71_kaishu_lishu_contrast.png"
    _write_contrast_figure(contrast_png, kaishu_dir=kaishu_dir, lishu_dir=lishu_dir, image_size=image_size)

    gap_summary = _make_gap_summary(kaishu_summary, lishu_summary)
    gap_summary_path = contrast_dir / "h1_lite_u5c71_style_gap_summary.json"
    gap_summary_path.write_text(json.dumps(gap_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_csv = out_dir / "h1_lite_style_contrast_summary.csv"
    _write_csv(summary_csv, rows, SUMMARY_FIELDS)
    report_md = out_dir / "h1_lite_style_contrast_report.md"
    _write_report(report_md, out_dir, rows, gap_summary, contrast_png)

    manifest_rows: list[dict[str, Any]] = []
    for row in rows:
        manifest_rows.extend(
            [
                {
                    "char": row["char"],
                    "char_id": row["char_id"],
                    "style": row["style"],
                    "artifact_type": "summary_json",
                    "path": row["summary_json"],
                    "source_role": row["source_role"],
                    "note": "",
                },
                {
                    "char": row["char"],
                    "char_id": row["char_id"],
                    "style": row["style"],
                    "artifact_type": "compare_png",
                    "path": row["compare_png"],
                    "source_role": row["source_role"],
                    "note": "",
                },
            ]
        )
    manifest_rows.extend(
        [
            {
                "char": "山",
                "char_id": "u5c71",
                "style": "kaishu_vs_lishu",
                "artifact_type": "contrast_png",
                "path": str(contrast_png),
                "source_role": "contrast",
                "note": "same-character style contrast",
            },
            {
                "char": "山",
                "char_id": "u5c71",
                "style": "kaishu_vs_lishu",
                "artifact_type": "gap_summary_json",
                "path": str(gap_summary_path),
                "source_role": "contrast",
                "note": "style gap before/after",
            },
        ]
    )
    manifest_csv = out_dir / "h1_lite_style_contrast_manifest.csv"
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)

    paper_index = DEFAULT_PAPER_DIR / "h1_lite_style_contrast_index.md"
    if copy_to_paper:
        DEFAULT_PAPER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "h1_lite_style_contrast_report.md")
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "h1_lite_style_contrast_summary.csv")
        _write_paper_index(paper_index, out_dir, rows, gap_summary, contrast_png)

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "contrast_png": str(contrast_png),
        "gap_summary_json": str(gap_summary_path),
        "kaishu_h1_result": h1_result,
        "paper_index": str(paper_index) if copy_to_paper else "",
        "rows": rows,
        "gap_summary": gap_summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--constraints-json", type=Path, default=DEFAULT_H2_CONSTRAINTS_JSON)
    parser.add_argument("--lishu-reference-dir", type=Path, default=DEFAULT_LISHU_H1_DIR)
    parser.add_argument("--image-size", type=int, default=256)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_h1_lite_style_contrast_expansion(
        output_dir=args.out_dir,
        constraints_json=args.constraints_json,
        lishu_reference_dir=args.lishu_reference_dir,
        image_size=args.image_size,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
