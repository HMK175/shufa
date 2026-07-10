"""Registry-gated B-route probe.

This trial-only probe compares the registry-selected B-route gate against the
existing direct-pulling style references. It does not generate formal
trajectory.csv or robot outputs.
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

from b_route_constraint_registry import DEFAULT_OUTPUT, DEFAULT_PAPER_DIR, run_b_route_constraint_registry

ROOT = Path(__file__).resolve().parents[3]
EXP_DIR = ROOT / "experiments" / "llm_style_trajectory"
DEFAULT_H1_LITE_SHAN = EXP_DIR / "outputs" / "constraint_bounded_adaptation_h1_lite_20260619_231903" / "u5c71_lishu" / "h1_lite_summary.json"
DEFAULT_HYBRID_SECTION_FENG = EXP_DIR / "outputs" / "hybrid_section_refinement_20260620_215513" / "u98ce_lishu" / "hybrid_section_summary.json"
DEFAULT_COMPONENT_ALIGN_SHAN = EXP_DIR / "outputs" / "lishu_component_alignment_20260619_160805" / "u5c71_lishu" / "lishu_component_alignment_summary.json"
DEFAULT_H1_LITE_FENG = EXP_DIR / "outputs" / "h1_lite_feng_lishu_risk_trial_20260620_212829" / "u98ce_lishu" / "h1_lite_summary.json"

PROBE_ROWS = [
    {
        "char": chr(0x5C71),
        "style": "lishu",
        "trial_summary": DEFAULT_H1_LITE_SHAN,
        "fallback_summary": DEFAULT_COMPONENT_ALIGN_SHAN,
    },
    {
        "char": chr(0x98CE),
        "style": "lishu",
        "trial_summary": DEFAULT_HYBRID_SECTION_FENG,
        "fallback_summary": DEFAULT_H1_LITE_FENG,
    },
]
SUMMARY_FIELDS = [
    "char",
    "char_id",
    "style",
    "registry_strategy",
    "fallback_used",
    "used_constraints",
    "bbox_aspect_before",
    "bbox_aspect_after",
    "lower_half_width_before",
    "lower_half_width_after",
    "max_point_shift_px",
    "path_length_ratio",
    "stroke_count_preserved",
    "warning",
    "recommended_for_visual_followup",
    "trial_only",
]
MANIFEST_FIELDS = ["char", "char_id", "style", "artifact_type", "path", "note"]
REPORT_FILE = "b_route_registry_probe_report.md"
SUMMARY_FILE = "b_route_registry_probe_summary.csv"
MANIFEST_FILE = "b_route_registry_probe_manifest.csv"
INDEX_FILE = "b_route_constraint_registry_index.md"


def _char_id(char: str) -> str:
    return f"u{ord(char):04x}" if char else ""


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _select_value(summary: dict[str, Any], candidates: Sequence[str], default: float = 0.0) -> float:
    for key in candidates:
        value = summary.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return float(default)


def _select_max_shift(summary: dict[str, Any]) -> float:
    value = summary.get("max_point_shift_px")
    if isinstance(value, dict):
        for key in ("balanced", "stronger", "conservative", "component_conservative", "component_stronger"):
            nested = value.get(key)
            if isinstance(nested, (int, float)):
                return float(nested)
    if isinstance(value, (int, float)):
        return float(value)
    return _select_value(
        summary,
        [
            "max_point_shift_px_balanced",
            "max_point_shift_px_conservative",
            "max_point_shift_px_component_conservative",
            "max_point_shift_px_component_stronger",
        ],
        default=0.0,
    )


def _select_path_ratio(summary: dict[str, Any]) -> float:
    value = summary.get("path_length_ratio")
    if isinstance(value, dict):
        for key in ("balanced", "stronger", "conservative", "component_conservative", "component_stronger"):
            nested = value.get(key)
            if isinstance(nested, (int, float)):
                return float(nested)
    if isinstance(value, (int, float)):
        return float(value)
    return _select_value(
        summary,
        [
            "path_length_ratio_balanced",
            "path_length_ratio_conservative",
            "path_length_ratio_component_conservative",
            "path_length_ratio_component_stronger",
        ],
        default=1.0,
    )


def _summarize_row(spec: dict[str, Any], registry_entry: dict[str, Any]) -> dict[str, Any]:
    source_summary = _read_json(spec["trial_summary"])
    baseline_summary = _read_json(spec["fallback_summary"])
    registry_strategy = registry_entry["strategy_selected"]
    fallback_used = registry_entry["fallback_used"]

    bbox_before = _select_value(
        baseline_summary,
        [
            "bbox_aspect_median",
            "bbox_aspect_original",
            "bbox_aspect_font",
            "bbox_aspect_v2_stronger",
            "bbox_aspect_component_stronger",
        ],
    )
    bbox_after = _select_value(
        source_summary,
        [
            "bbox_aspect_balanced",
            "bbox_aspect_conservative",
            "bbox_aspect_v3_stronger",
            "bbox_aspect_component_conservative",
            "bbox_aspect_target",
            "bbox_aspect",
        ],
    )
    lower_before = _select_value(
        baseline_summary,
        [
            "lower_half_width_median",
            "lower_half_width_original",
            "lower_half_width_font",
            "lower_half_width_v2_stronger",
            "lower_half_width_component_stronger",
        ],
    )
    lower_after = _select_value(
        source_summary,
        [
            "lower_half_width_balanced",
            "lower_half_width_conservative",
            "lower_half_width_v3_stronger",
            "lower_half_width_component_conservative",
            "lower_half_width_target",
            "lower_half_width",
        ],
    )
    max_shift = _select_max_shift(source_summary)
    path_ratio = _select_path_ratio(source_summary)
    stroke_count_preserved = bool(source_summary.get("stroke_count_preserved", True))
    warning = str(source_summary.get("warning", ""))
    recommended = bool(source_summary.get("recommended_for_visual_followup", True))
    used_constraints = list(registry_entry["usable_constraints"])
    return {
        "char": spec["char"],
        "char_id": _char_id(spec["char"]),
        "style": spec["style"],
        "registry_strategy": registry_strategy,
        "fallback_used": fallback_used,
        "used_constraints": ";".join(used_constraints),
        "bbox_aspect_before": round(bbox_before, 6),
        "bbox_aspect_after": round(bbox_after, 6),
        "lower_half_width_before": round(lower_before, 6),
        "lower_half_width_after": round(lower_after, 6),
        "max_point_shift_px": round(max_shift, 6),
        "path_length_ratio": round(path_ratio, 6),
        "stroke_count_preserved": stroke_count_preserved,
        "warning": warning,
        "recommended_for_visual_followup": recommended,
        "trial_only": True,
    }


def _render_compare(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(1, 1, figsize=(4.8, 4.2), dpi=150)
    ax.set_title(f"{row['char']}/{row['style']} registry probe", fontsize=9)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.08, 0.62), 0.84, 0.20, fill=False, edgecolor="#1f77b4", linewidth=1.4))
    ax.add_patch(plt.Rectangle((0.08, 0.36), 0.84, 0.20, fill=False, edgecolor="#2ca02c", linewidth=1.4))
    ax.add_patch(plt.Rectangle((0.08, 0.10), 0.84, 0.18, fill=False, edgecolor="#d62728", linewidth=1.4))
    ax.text(0.12, 0.88, f"registry: {row['registry_strategy']}", fontsize=8)
    ax.text(0.12, 0.74, f"before aspect={row['bbox_aspect_before']:.3f}", fontsize=8)
    ax.text(0.12, 0.68, f"after aspect={row['bbox_aspect_after']:.3f}", fontsize=8)
    ax.text(0.12, 0.48, f"before lower-half={row['lower_half_width_before']:.3f}", fontsize=8)
    ax.text(0.12, 0.42, f"after lower-half={row['lower_half_width_after']:.3f}", fontsize=8)
    ax.text(0.12, 0.20, f"max shift={row['max_point_shift_px']:.2f}px", fontsize=8)
    ax.text(0.12, 0.02, "trial-only / not_used_by_default", fontsize=7, color="#444444")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _write_report(path: Path, output_dir: Path, rows: Sequence[dict[str, Any]]) -> None:
    lines = [
        "# B-route registry-gated probe",
        "",
        "This trial-only probe compares the registry-selected B-route gate against the existing direct-pulling style references.",
        "It is registry-gated adaptation, not direct pulling.",
        "It does not generate formal trajectory.csv or robot outputs.",
        "",
        f"- output_dir: `{output_dir}`",
        "- status: `trial_only_not_used_by_default`",
        "- registry strategy is chosen from a read-only constraint registry",
        "",
        "## Summary",
        "",
        "| sample | registry_strategy | fallback_used | before aspect | after aspect | before lower-half | after lower-half | max shift | path ratio |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['char']}/{row['style']} | {row['registry_strategy']} | {row['fallback_used']} | {row['bbox_aspect_before']:.3f} | {row['bbox_aspect_after']:.3f} | {row['lower_half_width_before']:.3f} | {row['lower_half_width_after']:.3f} | {row['max_point_shift_px']:.2f} | {row['path_length_ratio']:.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- 山/lishu is expected to use component-first safe gating when the component bbox is stable.",
            "- 风/lishu should remain fallback-first reference-only because its section evidence is less stable.",
            "- The registry-gated route is meant to be more controlled than direct pulling, not more aggressive.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_index(path: Path, output_dir: Path, registry_result: dict[str, Any], summary_csv: Path, report_md: Path, manifest_csv: Path) -> None:
    lines = [
        "# B-route constraint registry index",
        "",
        f"- source_output_dir: `{output_dir}`",
        "- status: `trial_only_not_used_by_default`",
        "",
        "## Artifacts",
        "",
        f"- registry json: `{registry_result['summary_json']}`",
        f"- registry csv: `{registry_result['summary_csv']}`",
        f"- registry report: `{registry_result['report_md']}`",
        f"- probe summary: `{summary_csv}`",
        f"- probe report: `{report_md}`",
        f"- probe manifest: `{manifest_csv}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_b_route_registry_gated_probe(output_dir: Path | str | None = None, copy_to_paper: bool = True) -> dict[str, Any]:
    registry_result = run_b_route_constraint_registry(
        output_dir=DEFAULT_OUTPUT / f"b_route_constraint_registry_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        copy_to_paper=False,
    )
    registry_summary = _read_json(Path(registry_result["summary_json"]))
    registry_map = {(entry["char"], entry["style"]): entry for entry in registry_summary["entries"]}

    if output_dir is None:
        output_dir = DEFAULT_OUTPUT / f"b_route_registry_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for spec in PROBE_ROWS:
        registry_entry = registry_map[(spec["char"], spec["style"])]
        row = _summarize_row(spec, registry_entry)
        rows.append(row)
        figure_path = figures_dir / f"registry_probe_u{ord(spec['char']):04x}_{spec['style']}.png"
        _render_compare(figure_path, row)
        manifest_rows.append(
            {
                "char": spec["char"],
                "char_id": _char_id(spec["char"]),
                "style": spec["style"],
                "artifact_type": "figure",
                "path": str(figure_path),
                "note": row["registry_strategy"],
            }
        )

    summary_csv_path = out_dir / SUMMARY_FILE
    _write_csv(summary_csv_path, rows, SUMMARY_FIELDS)
    manifest_csv_path = out_dir / MANIFEST_FILE
    manifest_rows.extend(
        [
            {
                "char": "",
                "char_id": "",
                "style": "",
                "artifact_type": "summary_csv",
                "path": str(summary_csv_path),
                "note": "probe summary",
            },
            {
                "char": "",
                "char_id": "",
                "style": "",
                "artifact_type": "registry_json",
                "path": registry_result["summary_json"],
                "note": "registry source",
            },
        ]
    )
    _write_csv(manifest_csv_path, manifest_rows, MANIFEST_FIELDS)
    report_md_path = out_dir / REPORT_FILE
    _write_report(report_md_path, out_dir, rows)

    index_path = DEFAULT_PAPER_DIR / INDEX_FILE
    _write_index(index_path, out_dir, registry_result, summary_csv_path, report_md_path, manifest_csv_path)

    if copy_to_paper:
        paper_dir = DEFAULT_PAPER_DIR
        paper_dir.mkdir(parents=True, exist_ok=True)
        for src in [summary_csv_path, report_md_path, manifest_csv_path]:
            shutil.copy2(src, paper_dir / src.name)
        for figure in figures_dir.glob("*.png"):
            shutil.copy2(figure, paper_dir / figure.name)

    return {
        "output_dir": str(out_dir),
        "summary_csv": str(summary_csv_path),
        "report_md": str(report_md_path),
        "manifest_csv": str(manifest_csv_path),
        "index_md": str(index_path),
        "registry_result": registry_result,
    }


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a registry-gated B-route probe.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--no-paper-copy", action="store_true")
    return parser


def main() -> int:
    args = _build_argparser().parse_args()
    result = run_b_route_registry_gated_probe(output_dir=args.output_dir, copy_to_paper=not args.no_paper_copy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
