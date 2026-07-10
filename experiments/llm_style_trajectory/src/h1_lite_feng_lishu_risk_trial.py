"""Single-sample H1-lite risk trial for 风/lishu.

This trial reuses the H1-lite bounded adaptation constraints, but only for a
single more complex lishu sample. It adds a known positive reference compare
for 山/lishu so the visual audit can compare the risk sample against an already
accepted lishu example.
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
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from constraint_bounded_adaptation_h1_lite import (
    DEFAULT_H2_CONSTRAINTS_JSON,
    _draw_strokes,
    _load_median,
    _write_csv,
    run_constraint_bounded_adaptation_h1_lite,
)


ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_OUTPUT = EXP_DIR / "outputs"
DEFAULT_PAPER_DIR = EXP_DIR / "outputs" / "paper_figures"
DEFAULT_REFERENCE_DIR = (
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


def _write_trial_reference_compare(
    path: Path,
    trial_median: Sequence[np.ndarray],
    trial_conservative: Sequence[np.ndarray],
    trial_balanced: Sequence[np.ndarray],
    reference_compare_png: Path,
    image_size: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 4, figsize=(13.0, 3.6), dpi=150)
    _draw_strokes(axes[0], trial_median, "风/lishu original median", "#444444")
    _draw_strokes(axes[1], trial_conservative, "风/lishu conservative", "#d62728")
    _draw_strokes(axes[2], trial_balanced, "风/lishu balanced", "#2ca02c")
    axes[3].set_title("known positive reference: 山/lishu", fontsize=8)
    axes[3].set_xticks([])
    axes[3].set_yticks([])
    axes[3].set_xlim(0, image_size)
    axes[3].set_ylim(image_size, 0)
    if reference_compare_png.exists():
        axes[3].imshow(mpimg.imread(reference_compare_png), extent=[0, image_size, image_size, 0])
    else:
        axes[3].text(8, 28, "reference compare missing", fontsize=7)
    fig.suptitle("H1-lite risk trial: 风/lishu with 山/lishu reference", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(path)
    plt.close(fig)


def _write_report(path: Path, output_dir: Path, row: dict[str, Any], gap: dict[str, Any], contrast_png: Path) -> None:
    lines = [
        "# H1-lite single-sample risk trial: 风/lishu",
        "",
        "This is a trial-only diagnostic for a more complex lishu character.",
        "",
        "## Boundary",
        "",
        "- trial-only / not_used_by_default。",
        "- 只使用 H2 中 `usable_for_adaptation` 的 bounded constraints。",
        "- 不使用 raw skeleton path，不使用 unordered skeleton segments，不做最近点吸附。",
        "- 保留 stroke_count / stroke_order / stroke_breaks。",
        "- 不生成正式 trajectory.csv，不生成 execution/workspace/robot 文件，不接默认 pipeline。",
        "",
        f"- output_dir: `{output_dir}`",
        f"- contrast_png: `{contrast_png}`",
        "",
        "## Results",
        "",
        f"- 风/lishu bbox aspect: {row['bbox_aspect_median']} -> {row['bbox_aspect_conservative']} / {row['bbox_aspect_balanced']}",
        f"- 风/lishu lower-half width: {row['lower_half_width_median']} -> {row['lower_half_width_conservative']} / {row['lower_half_width_balanced']}",
        f"- 风/lishu max shift: {row['max_point_shift_px_conservative']} / {row['max_point_shift_px_balanced']} px",
        f"- 风/lishu path ratio: {row['path_length_ratio_conservative']} / {row['path_length_ratio_balanced']}",
        "",
        "## Reference compare",
        "",
        f"- known positive reference compare: `{gap['reference_compare_png']}`",
        f"- 山/lishu reference source: {gap['reference_source_role']}",
        "",
        "## Manual visual audit questions",
        "",
        "- 风/lishu 是否仍保持可写性？",
        "- H1-lite 是否还能保持隶书宽底感？",
        "- 与山/lishu 相比是否明显更难处理？",
        "- 是否说明 H1-lite 适合简单/中等复杂度 lishu，但对复杂字开始接近边界？",
        "- 是否仍建议继续扩展，还是应优先做 component-level / section-level constraint refinement？",
        "",
        "## Interpretation",
        "",
        "If 风/lishu stays readable and the balanced variant preserves a visible lishu broad-bottom cue without large point shifts, H1-lite remains viable for some complex lishu samples. "
        "If the shape gets visibly fragile, that is a sign to stop expanding and return to component-level refinement instead of pushing stronger bounded adaptation.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_paper_index(index_path: Path, output_dir: Path, row: dict[str, Any], gap: dict[str, Any], contrast_png: Path) -> None:
    lines = [
        "# H1-lite feng lishu risk trial index",
        "",
        f"- source_output_dir: `{output_dir}`",
        "- Status: trial-only, not used by default.",
        "- Boundary: no raw skeleton path, no nearest-point pulling, no formal trajectory.csv, no execution/workspace/robot outputs.",
        "",
        f"- sample compare: `{row['compare_png']}`",
        f"- reference compare: `{gap['reference_compare_png']}`",
        f"- risk contrast png: `{contrast_png}`",
        "",
        f"- bbox_aspect: {row['bbox_aspect_median']} -> {row['bbox_aspect_conservative']} / {row['bbox_aspect_balanced']}",
        f"- lower_half_width: {row['lower_half_width_median']} -> {row['lower_half_width_conservative']} / {row['lower_half_width_balanced']}",
        f"- max_point_shift_px: {row['max_point_shift_px_conservative']} / {row['max_point_shift_px_balanced']}",
        f"- path_length_ratio: {row['path_length_ratio_conservative']} / {row['path_length_ratio_balanced']}",
    ]
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_h1_lite_feng_lishu_risk_trial(
    output_dir: Path | str | None = None,
    constraints_json_path: Path | str = DEFAULT_H2_CONSTRAINTS_JSON,
    reference_dir: Path | str = DEFAULT_REFERENCE_DIR,
    image_size: int = 256,
    copy_to_paper: bool = True,
) -> dict[str, Any]:
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"h1_lite_feng_lishu_risk_trial_{timestamp}"
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_result = run_constraint_bounded_adaptation_h1_lite(
        output_dir=out_dir,
        constraints_json_path=constraints_json_path,
        sample_specs=[("风", "lishu")],
        image_size=image_size,
        copy_to_paper=False,
    )

    sample_dir = out_dir / "u98ce_lishu"
    summary = _read_json(sample_dir / "h1_lite_summary.json")
    reference_dir = Path(reference_dir)
    reference_summary = _read_json(reference_dir / "h1_lite_summary.json")
    reference_compare_png = reference_dir / "h1_lite_compare.png"
    if not reference_compare_png.exists():
        raise FileNotFoundError(f"Missing reference compare image: {reference_compare_png}")

    contrast_dir = out_dir / "contrast"
    contrast_dir.mkdir(parents=True, exist_ok=True)
    contrast_png = contrast_dir / "h1_lite_u98ce_lishu_risk_contrast.png"
    _write_trial_reference_compare(
        contrast_png,
        trial_median=_load_median("风", image_size=image_size),
        trial_conservative=_read_trial_csv(sample_dir / "h1_lite_conservative.csv"),
        trial_balanced=_read_trial_csv(sample_dir / "h1_lite_balanced.csv"),
        reference_compare_png=reference_compare_png,
        image_size=image_size,
    )

    shutil.copy2(reference_compare_png, contrast_dir / "h1_lite_u5c71_lishu_reference_compare.png")

    gap_summary = {
        "status": "trial_not_used_by_default",
        "source": "h1_lite_feng_lishu_risk_trial",
        "char": "风",
        "char_id": "u98ce",
        "style": "lishu",
        "reference_char": "山",
        "reference_char_id": "u5c71",
        "reference_style": "lishu",
        "reference_source_role": "existing_h1_lite_positive_reference",
        "feng_vs_reference_bbox_aspect_gap": {
            "before": round(abs(summary["bbox_aspect_median"] - reference_summary["bbox_aspect_median"]), 6),
            "conservative": round(abs(summary["bbox_aspect_conservative"] - reference_summary["bbox_aspect_conservative"]), 6),
            "balanced": round(abs(summary["bbox_aspect_balanced"] - reference_summary["bbox_aspect_balanced"]), 6),
        },
        "feng_vs_reference_lower_half_width_gap": {
            "before": round(abs(summary["lower_half_width_median"] - reference_summary["lower_half_width_median"]), 6),
            "conservative": round(abs(summary["lower_half_width_conservative"] - reference_summary["lower_half_width_conservative"]), 6),
            "balanced": round(abs(summary["lower_half_width_balanced"] - reference_summary["lower_half_width_balanced"]), 6),
        },
        "risk_note": "风/lishu is more complex than 山/lishu, so this is a single-sample risk trial only.",
        "recommended_for_visual_followup": True,
        "reference_compare_png": str(reference_compare_png),
        "boundary": "trial-only; not_used_by_default; no formal trajectory.csv; no execution/workspace/robot outputs",
    }
    gap_summary_path = contrast_dir / "h1_lite_u98ce_lishu_reference_gap_summary.json"
    gap_summary_path.write_text(json.dumps(gap_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    row = _summary_row(summary, sample_dir, "generated_this_run")
    summary_csv = out_dir / "h1_lite_feng_lishu_risk_trial_summary.csv"
    report_md = out_dir / "h1_lite_feng_lishu_risk_trial_report.md"
    manifest_csv = out_dir / "h1_lite_feng_lishu_risk_trial_manifest.csv"

    _write_csv(summary_csv, [row], SUMMARY_FIELDS)
    manifest_rows = [
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
        {
            "char": "山",
            "char_id": "u5c71",
            "style": "lishu",
            "artifact_type": "reference_compare_png",
            "path": str(contrast_dir / "h1_lite_u5c71_lishu_reference_compare.png"),
            "source_role": "existing_h1_lite_positive_reference",
            "note": "known positive lishu reference",
        },
        {
            "char": "风",
            "char_id": "u98ce",
            "style": "lishu",
            "artifact_type": "risk_contrast_png",
            "path": str(contrast_png),
            "source_role": "contrast",
            "note": "风/lishu risk trial against 山/lishu reference",
        },
        {
            "char": "风",
            "char_id": "u98ce",
            "style": "lishu",
            "artifact_type": "gap_summary_json",
            "path": str(gap_summary_path),
            "source_role": "contrast",
            "note": "",
        },
    ]
    _write_csv(manifest_csv, manifest_rows, MANIFEST_FIELDS)
    _write_report(report_md, out_dir, row, gap_summary, contrast_png)

    paper_index = ""
    if copy_to_paper:
        DEFAULT_PAPER_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(summary_csv, DEFAULT_PAPER_DIR / "h1_lite_feng_lishu_risk_trial_summary.csv")
        shutil.copy2(report_md, DEFAULT_PAPER_DIR / "h1_lite_feng_lishu_risk_trial_report.md")
        index_path = DEFAULT_PAPER_DIR / "h1_lite_feng_lishu_risk_trial_index.md"
        _write_paper_index(index_path, out_dir, row, gap_summary, contrast_png)
        paper_index = str(index_path)

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "report_md": str(report_md),
        "manifest_csv": str(manifest_csv),
        "paper_index": paper_index,
        "contrast_png": str(contrast_png),
        "reference_compare_png": str(contrast_dir / "h1_lite_u5c71_lishu_reference_compare.png"),
        "gap_summary_json": str(gap_summary_path),
        "rows": [row],
        "gap_summary": gap_summary,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--constraints-json", type=Path, default=DEFAULT_H2_CONSTRAINTS_JSON)
    parser.add_argument("--reference-dir", type=Path, default=DEFAULT_REFERENCE_DIR)
    parser.add_argument("--image-size", type=int, default=256)
    parser.add_argument("--no-copy-to-paper", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run_h1_lite_feng_lishu_risk_trial(
        output_dir=args.out_dir,
        constraints_json_path=args.constraints_json,
        reference_dir=args.reference_dir,
        image_size=args.image_size,
        copy_to_paper=not args.no_copy_to_paper,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
